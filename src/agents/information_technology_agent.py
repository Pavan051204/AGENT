import json
from datetime import date

from groq import Groq
from src.settings import get_config
from src.agents.agent_base import AgentResult, BaseAgent
from src.tools import database


VALID_ASSET_TYPES = ["laptop", "monitor", "keyboard", "mouse", "vpn_token", "software_license"]

ASSET_TYPE_LABELS = {
    "laptop": "Laptop",
    "monitor": "Monitor",
    "keyboard": "Keyboard",
    "mouse": "Mouse",
    "vpn_token": "VPN Token",
    "software_license": "Software License",
}

PRIORITY_LABELS = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🔴 High",
    "critical": "🚨 Critical",
}


class ITAgent(BaseAgent):
    """IT Agent — handles support tickets, asset requests, and IT operations.

    Supports:
    - Intelligent ticket creation (checks maintenance, outages, duplicates)
    - Asset requests with approval workflow
    - Ticket tracking and management
    - IT RBAC (employees see own, IT team sees all)
    """

    name = "it"

    def __init__(self):
        super().__init__()
        config = get_config()
        self.groq_client = Groq(api_key=config.groq_api_key) if config.groq_api_key else None
        self.groq_model = config.groq_model
        self.model = self.groq_model

    def handle(self, state: dict) -> AgentResult:
        query = state.get("query", "")
        user_id = state.get("user_id", "")
        role = state.get("role", "")
        chat_history = state.get("chat_history", [])

        if not self.groq_client:
            return AgentResult(response="Groq client not configured for IT Agent.")

        # ── Agentic Tool Calling Loop ──────────────────────────────────

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "create_ticket",
                    "description": "Raise an IT support ticket. Use when user reports a problem (laptop, VPN, email, printer, network, software).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_type": {"type": "string", "enum": ["laptop", "vpn", "email", "printer", "network", "software", "password_reset", "general"],
                                           "description": "Category of the issue"},
                            "description": {"type": "string", "description": "Brief description of the problem"},
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"], "description": "Priority level"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "request_asset",
                    "description": "Request an IT asset (laptop, monitor, keyboard, mouse, VPN token, software license).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "asset_type": {"type": "string", "enum": ["laptop", "monitor", "keyboard", "mouse", "vpn_token", "software_license"]},
                            "justification": {"type": "string", "description": "Business justification for the request"}
                        },
                        "required": ["asset_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "view_my_tickets",
                    "description": "View the user's IT support tickets.",
                    "parameters": {"type": "object", "properties": {"dummy": {"type": "string", "description": "leave empty"}}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "view_all_tickets",
                    "description": "View all IT tickets across the organization. Only for IT team / admin.",
                    "parameters": {"type": "object", "properties": {"dummy": {"type": "string", "description": "leave empty"}}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_ticket_status",
                    "description": "Check the status of a specific ticket by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "The ticket ID to check"}
                        },
                        "required": ["ticket_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "assign_ticket",
                    "description": "Assign a ticket to an IT engineer. Only for IT team / admin.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "The ticket ID"},
                            "engineer": {"type": "string", "description": "Username of the engineer to assign to"}
                        },
                        "required": ["ticket_id", "engineer"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "resolve_ticket",
                    "description": "Mark a ticket as resolved. Only for IT team / admin.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "The ticket ID to resolve"}
                        },
                        "required": ["ticket_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "view_my_assets",
                    "description": "View the user's asset requests and their statuses.",
                    "parameters": {"type": "object", "properties": {"dummy": {"type": "string", "description": "leave empty"}}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_maintenance",
                    "description": "Check the planned maintenance schedule.",
                    "parameters": {"type": "object", "properties": {"dummy": {"type": "string", "description": "leave empty"}}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_outages",
                    "description": "Check current known outages and active incidents.",
                    "parameters": {"type": "object", "properties": {"dummy": {"type": "string", "description": "leave empty"}}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_inventory",
                    "description": "Check IT inventory stock for a specific asset type.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "asset_type": {"type": "string", "description": "Type of asset to check"}
                        },
                        "required": ["asset_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "approve_asset",
                    "description": "Approve or reject an asset request. IT team / manager / admin only.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "approval_id": {"type": "string", "description": "The approval record ID"},
                            "decision": {"type": "string", "enum": ["approved", "rejected"]}
                        },
                        "required": ["approval_id", "decision"]
                    }
                }
            },
        ]

        system_prompt = f"""You are Novi Pilot's IT Support Agent. You help employees with IT issues, ticket management, and asset requests.
Today's date is {date.today().isoformat()}.
The current user is: {user_id} with role: {role}

STRICT RULES:
1. Use the provided tools to perform actions. ALWAYS call a tool when the user wants an IT action.
2. For ticket creation: If the user doesn't provide enough details, call 'create_ticket' with NO parameters to trigger the ticket form. The system will automatically check for maintenance, outages, and duplicates before creating if details are provided.
3. For asset requests: call 'request_asset'. The system will check inventory and create an approval workflow.
4. RBAC enforcement:
   - Employees can ONLY view their own tickets and assets.
   - IT team and admin can view ALL tickets, assign tickets, and resolve tickets.
   - If an employee tries to use admin-only tools, politely inform them of access restrictions.
5. If a user asks to 'assign ticket' or 'resolve ticket' and they are NOT IT team/admin, deny access politely.
6. If the query is unrelated to IT support (cooking, sports, etc.), politely redirect and explain what you CAN help with.
7. NEVER make up data. Only use tool results.
8. Be professional, concise, and helpful."""

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add limited chat history for context
        for msg in chat_history[-5:]:
            if msg.get("query"):
                messages.append({"role": "user", "content": msg["query"]})
            if msg.get("response"):
                messages.append({"role": "assistant", "content": msg["response"]})

        messages.append({"role": "user", "content": query})

        try:
            res = self.groq_client.chat.completions.create(
                messages=messages,
                model=self.groq_model,
                tools=tools,
                tool_choice="auto",
                temperature=0.1
            )

            msg = res.choices[0].message

            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                func_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except Exception:
                    args = {}
                if args is None:
                    args = {}

                if func_name == "create_ticket":
                    return self._create_ticket(args, user_id)
                elif func_name == "request_asset":
                    return self._request_asset(args, user_id)
                elif func_name == "view_my_tickets":
                    return self._view_tickets(user_id, role)
                elif func_name == "view_all_tickets":
                    return self._view_all_tickets(user_id, role)
                elif func_name == "check_ticket_status":
                    return self._check_ticket_status(args.get("ticket_id"), user_id, role)
                elif func_name == "assign_ticket":
                    return self._assign_ticket(args.get("ticket_id"), args.get("engineer"), user_id, role)
                elif func_name == "resolve_ticket":
                    return self._resolve_ticket(args.get("ticket_id"), user_id, role)
                elif func_name == "view_my_assets":
                    return self._view_assets(user_id, role)
                elif func_name == "check_maintenance":
                    return self._check_maintenance()
                elif func_name == "check_outages":
                    return self._check_outages()
                elif func_name == "check_inventory":
                    return self._check_inventory(args.get("asset_type", ""))
                elif func_name == "approve_asset":
                    aid = args.get("approval_id")
                    try:
                        aid = int(aid) if aid is not None else None
                    except (ValueError, TypeError):
                        return AgentResult(response="❌ Invalid approval ID.")
                    return self._approve_asset(aid, args.get("decision"), user_id, role)

            return AgentResult(response=msg.content or "I'm not sure how to help with that. Can you rephrase?")

        except Exception as e:
            print(f"ITAgent Error: {e}")
            return AgentResult(response=f"I encountered an error: {e}")

    # ──────────────────────────────────────────────────────────────────
    #  Private helpers
    # ──────────────────────────────────────────────────────────────────

    def _create_ticket(self, args: dict, user_id: str) -> AgentResult:
        """Intelligent ticket creation — checks maintenance, outages, duplicates first."""
        issue_type = args.get("issue_type")
        description = args.get("description")
        priority = args.get("priority", "medium")

        if not issue_type or not description:
            # Missing details -> Return the adaptive card
            return AgentResult(
                response="📝 **Raise IT Ticket**\n\nPlease provide the details of your issue using the form below, or describe it in the chat (e.g., *'raise ticket for VPN with high priority because it keeps disconnecting'*).",
                tool_calls=[{
                    "type": "adaptive_card",
                    "card_type": "ticket_form",
                    "data": {
                        "issue_types": ["laptop", "vpn", "email", "printer", "network", "software", "password_reset", "general"]
                    }
                }]
            )

        issue_type = issue_type or "general"
        warnings = []

        # 1. Check planned maintenance
        maintenance = database.get_planned_maintenance()
        relevant_maint = [
            m for m in maintenance
            if issue_type.lower() in m["system_name"].lower()
            or issue_type.lower() in m["description"].lower()
        ]
        if relevant_maint:
            maint_info = "\n".join(
                f"  • **{m['system_name']}**: {m['description']} ({m['start_time'][:10]} to {m['end_time'][:10]})"
                for m in relevant_maint
            )
            warnings.append(f"⚠️ **Scheduled Maintenance Detected:**\n{maint_info}")

        # 2. Check known outages
        outages = database.get_active_outages()
        relevant_outages = [
            o for o in outages
            if issue_type.lower() in o["system_name"].lower()
            or issue_type.lower() in o["description"].lower()
            or any(kw in o["description"].lower() for kw in issue_type.split("_"))
        ]
        if relevant_outages:
            outage_info = "\n".join(
                f"  • **{o['system_name']}**: {o['description']} (Status: {o['status']})"
                for o in relevant_outages
            )
            warnings.append(f"🔴 **Known Outage Found:**\n{outage_info}")

        # 3. Check duplicate open tickets
        duplicates = database.check_duplicate_tickets(user_id, issue_type)
        if duplicates:
            dup_info = "\n".join(
                f"  • Ticket **#{d['id']}**: {d['issue_type']} — {d['status']} (Created: {d['created_at'][:10] if d['created_at'] else 'N/A'})"
                for d in duplicates
            )
            warnings.append(f"📋 **Existing Open Ticket Found:**\n{dup_info}\n\nYou already have an open ticket for this issue type. The new ticket is still created, but consider tracking the existing one.")

        # Create the ticket
        ticket_id = database.create_ticket(user_id, issue_type, priority, description)

        response = (
            f"✅ **IT Support Ticket Created**\n\n"
            f"• **Ticket ID:** #{ticket_id}\n"
            f"• **Issue Type:** {issue_type.replace('_', ' ').title()}\n"
            f"• **Priority:** {PRIORITY_LABELS.get(priority, priority)}\n"
            f"• **Description:** {description or 'Not specified'}\n"
            f"• **Status:** Open\n"
            f"• **Assigned Engineer:** Pending assignment"
        )

        if warnings:
            response += "\n\n---\n" + "\n\n".join(warnings)

        return AgentResult(response=response, approval_required=True)

    def _request_asset(self, args: dict, user_id: str) -> AgentResult:
        """Request an IT asset with inventory check and approval workflow."""
        asset_type = args.get("asset_type", "laptop")
        justification = args.get("justification", "")

        # Check inventory
        stock = database.check_inventory(asset_type)
        if stock["available"] <= 0:
            return AgentResult(
                response=f"❌ **Out of Stock**\n\n"
                f"Unfortunately, **{ASSET_TYPE_LABELS.get(asset_type, asset_type)}** is currently out of stock "
                f"(0/{stock['total']} available). Please try again later or contact IT directly."
            )

        asset_id = database.request_asset(user_id, asset_type, justification)

        response = (
            f"✅ **Asset Request Submitted**\n\n"
            f"• **Request ID:** #{asset_id}\n"
            f"• **Asset Type:** {ASSET_TYPE_LABELS.get(asset_type, asset_type)}\n"
            f"• **Justification:** {justification or 'Not specified'}\n"
            f"• **Inventory:** {stock['available']}/{stock['total']} available\n"
            f"• **Status:** Pending Approval\n\n"
            f"📋 **Approval Workflow:**\n"
            f"  1. Manager Approval → 2. IT Approval → 3. Inventory Validation → 4. Fulfillment"
        )

        return AgentResult(response=response, approval_required=True)

    def _view_tickets(self, user_id: str, role: str) -> AgentResult:
        """View tickets — employees see own, IT/admin see all."""
        if role in ("it", "admin"):
            return self._view_all_tickets(user_id, role)

        tickets = database.list_tickets(user_id)
        if not tickets:
            return AgentResult(response="📋 **Your IT Tickets**\n\nNo tickets found. Use *'raise a ticket'* to create one.")

        rows = []
        for t in tickets:
            status_icon = {"open": "🟡", "in_progress": "🔵", "resolved": "🟢"}.get(t["status"], "⚪")
            rows.append(
                f"| {t['id']} | {t['issue_type'].replace('_', ' ').title()} | "
                f"{PRIORITY_LABELS.get(t['priority'], t['priority'])} | "
                f"{status_icon} {t['status']} | {t['assigned_engineer'] or 'Unassigned'} |"
            )

        table = (
            "| ID | Issue | Priority | Status | Assigned To |\n"
            "|---|---|---|---|---|\n"
            + "\n".join(rows)
        )
        return AgentResult(response=f"📋 **Your IT Tickets ({len(tickets)})**\n\n{table}")

    def _view_all_tickets(self, user_id: str, role: str) -> AgentResult:
        """IT team view — all tickets across the organization."""
        if role not in ("it", "admin"):
            return AgentResult(response="🔒 **Access Denied** — Only IT team and admins can view all tickets.")

        tickets = database.get_all_tickets()
        if not tickets:
            return AgentResult(response="📋 **All IT Tickets (IT View)**\n\nNo tickets in the system.")

        rows = []
        for t in tickets:
            status_icon = {"open": "🟡", "in_progress": "🔵", "resolved": "🟢"}.get(t["status"], "⚪")
            rows.append(
                f"| {t['id']} | {t.get('user_id', 'N/A')} | {t['issue_type'].replace('_', ' ').title()} | "
                f"{PRIORITY_LABELS.get(t['priority'], t['priority'])} | "
                f"{status_icon} {t['status']} | {t['assigned_engineer'] or 'Unassigned'} |"
            )

        table = (
            "| ID | User | Issue | Priority | Status | Assigned |\n"
            "|---|---|---|---|---|---|\n"
            + "\n".join(rows)
        )
        return AgentResult(response=f"📋 **All IT Tickets — IT Admin View ({len(tickets)})**\n\n{table}")

    def _check_ticket_status(self, ticket_id: int, user_id: str, role: str) -> AgentResult:
        if ticket_id is None:
            return AgentResult(response="Please specify a ticket ID.")

        try:
            ticket_id = int(ticket_id)
        except (ValueError, TypeError):
            return AgentResult(response="❌ Invalid ticket ID.")

        ticket = database.get_ticket_by_id(ticket_id)
        if not ticket:
            return AgentResult(response=f"❌ Ticket #{ticket_id} not found.")

        # RBAC: employees can only see their own tickets
        if role not in ("it", "admin") and ticket["user_id"] != user_id:
            return AgentResult(response="🔒 You can only view your own tickets.")

        status_icon = {"open": "🟡", "in_progress": "🔵", "resolved": "🟢"}.get(ticket["status"], "⚪")

        return AgentResult(
            response=(
                f"📊 **Ticket #{ticket_id} Details**\n\n"
                f"• **Issue:** {ticket['issue_type'].replace('_', ' ').title()}\n"
                f"• **Description:** {ticket['description'] or 'Not specified'}\n"
                f"• **Priority:** {PRIORITY_LABELS.get(ticket['priority'], ticket['priority'])}\n"
                f"• **Status:** {status_icon} {ticket['status']}\n"
                f"• **Assigned Engineer:** {ticket['assigned_engineer'] or 'Unassigned'}\n"
                f"• **Created:** {ticket['created_at'][:10] if ticket['created_at'] else 'N/A'}\n"
                f"• **Resolved:** {ticket['resolved_at'][:10] if ticket['resolved_at'] else 'N/A'}"
            )
        )

    def _assign_ticket(self, ticket_id: int, engineer: str, user_id: str, role: str) -> AgentResult:
        if role not in ("it", "admin"):
            return AgentResult(response="🔒 **Access Denied** — Only IT team members can assign tickets.")

        if not ticket_id or not engineer:
            return AgentResult(response="Please provide both a ticket ID and an engineer username.")

        try:
            ticket_id = int(ticket_id)
        except (ValueError, TypeError):
            return AgentResult(response="❌ Invalid ticket ID.")

        result = database.assign_ticket(ticket_id, engineer)
        icon = "✅" if "assigned" in result.lower() else "❌"
        return AgentResult(response=f"{icon} {result}")

    def _resolve_ticket(self, ticket_id: int, user_id: str, role: str) -> AgentResult:
        if role not in ("it", "admin"):
            return AgentResult(response="🔒 **Access Denied** — Only IT team members can resolve tickets.")

        if not ticket_id:
            return AgentResult(response="Please provide a ticket ID to resolve.")

        try:
            ticket_id = int(ticket_id)
        except (ValueError, TypeError):
            return AgentResult(response="❌ Invalid ticket ID.")

        result = database.resolve_ticket(ticket_id, user_id)
        icon = "✅" if "resolved" in result.lower() else "❌"
        return AgentResult(response=f"{icon} {result}")

    def _view_assets(self, user_id: str, role: str) -> AgentResult:
        if role in ("it", "admin"):
            assets = database.get_all_assets()
            title = "🖥️ **All Asset Requests (IT View)**"
        else:
            assets = database.list_assets(user_id)
            title = "🖥️ **Your Asset Requests**"

        if not assets:
            return AgentResult(response=f"{title}\n\nNo asset requests found.")

        rows = []
        for a in assets:
            status_icon = {"pending": "🟡", "approved": "🟢", "rejected": "🔴", "fulfilled": "✅"}.get(a["status"], "⚪")
            user_col = f" | {a['user_id']}" if "user_id" in a else ""
            rows.append(
                f"| {a['id']} | {ASSET_TYPE_LABELS.get(a['asset_type'], a['asset_type'])} | "
                f"{status_icon} {a['status']} | {a.get('created_at', 'N/A')[:10] if a.get('created_at') else 'N/A'}{user_col} |"
            )

        header = "| ID | Asset | Status | Requested |"
        if role in ("it", "admin"):
            header = "| ID | Asset | Status | Requested | User |"
        separator = "|" + "|".join(["---"] * header.count("|")) + "|"
        table = "\n".join([header, separator] + rows)
        return AgentResult(response=f"{title}\n\n{table}")

    def _check_maintenance(self) -> AgentResult:
        maintenance = database.get_planned_maintenance()
        if not maintenance:
            return AgentResult(response="✅ **No scheduled maintenance at this time.**")

        rows = "\n".join(
            f"• **{m['system_name']}**: {m['description']}\n"
            f"  📅 {m['start_time'][:16].replace('T', ' ')} → {m['end_time'][:16].replace('T', ' ')}"
            for m in maintenance
        )
        return AgentResult(response=f"🔧 **Planned Maintenance Schedule**\n\n{rows}")

    def _check_outages(self) -> AgentResult:
        outages = database.get_active_outages()
        if not outages:
            return AgentResult(response="✅ **No active outages. All systems operational.**")

        rows = "\n".join(
            f"• 🔴 **{o['system_name']}**: {o['description']}\n"
            f"  Reported: {o['reported_at'][:16].replace('T', ' ') if o['reported_at'] else 'N/A'}"
            for o in outages
        )
        return AgentResult(response=f"⚠️ **Active Outages / Incidents**\n\n{rows}")

    def _check_inventory(self, asset_type: str) -> AgentResult:
        if not asset_type:
            # Show all inventory
            rows = []
            for key, label in ASSET_TYPE_LABELS.items():
                stock = database.check_inventory(key)
                bar_len = 10
                pct = stock["available"] / max(stock["total"], 1)
                filled = round(pct * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                status = "🟢" if pct > 0.3 else "🟡" if pct > 0.1 else "🔴"
                rows.append(f"| {label} | {stock['available']} | {stock['total']} | {status} {bar} |")

            table = (
                "| Asset | Available | Total | Stock Level |\n"
                "|---|---|---|---|\n"
                + "\n".join(rows)
            )
            return AgentResult(response=f"📦 **IT Inventory Status**\n\n{table}")

        stock = database.check_inventory(asset_type)
        label = ASSET_TYPE_LABELS.get(asset_type, asset_type)
        status = "In Stock ✅" if stock["available"] > 0 else "Out of Stock ❌"
        return AgentResult(
            response=f"📦 **Inventory: {label}**\n\n"
            f"• **Available:** {stock['available']}/{stock['total']}\n"
            f"• **Status:** {status}"
        )

    def _approve_asset(self, approval_id: int, decision: str, user_id: str, role: str) -> AgentResult:
        if role not in ("it", "manager", "admin"):
            return AgentResult(response="🔒 **Access Denied** — Only IT team, managers, and admins can approve asset requests.")

        if not approval_id:
            return AgentResult(response="Please provide the approval ID.")

        try:
            approval_id = int(approval_id)
        except (ValueError, TypeError):
            return AgentResult(response="❌ Invalid approval ID.")

        database.approve_request(approval_id, user_id, decision)

        # Sync asset status
        conn = database._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT request_type, request_id FROM approvals WHERE id = ?", (approval_id,))
        row = cur.fetchone()
        conn.close()

        if row and row[0] == "asset":
            database.update_asset_status(row[1], decision)

        status_icon = "🟢" if decision == "approved" else "🔴"
        return AgentResult(
            response=f"{status_icon} **Asset Request {decision.capitalize()}**\n\n"
            f"Approval #{approval_id} has been {decision} by {user_id}."
        )
