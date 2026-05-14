import re
from datetime import date, timedelta

import json
from groq import Groq
from src.settings import get_config
from src.agents.agent_base import AgentResult, BaseAgent
from src.tools import database


VALID_LEAVE_TYPES = ["casual", "sick", "earned", "comp_off"]

LEAVE_TYPE_LABELS = {
    "casual": "Casual Leave",
    "sick": "Sick Leave",
    "earned": "Earned Leave",
    "comp_off": "Compensatory Off",
}


class HRAgent(BaseAgent):
    """HR Agent — handles all leave management operations.

    Supports leave types (casual, sick, earned, comp_off) and HR assignment.
    When applying leave, the agent can render adaptive cards with dropdowns
    for leave type and HR selection.
    """

    name = "hr"

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

        # If LLM is available, use it to extract intent and entities with memory
        parsed = self._parse_with_llm(query, chat_history)

        intent = parsed.get("intent", "unknown")
        
        # ── Apply Leave ───────────────────────────────────────────────
        if intent == "apply_leave":
            return self._apply_leave_parsed(parsed, user_id, query)

        # ── Cancel Leave ──────────────────────────────────────────────
        if intent == "cancel_leave":
            return self._cancel_leave(query, user_id)

        # ── HR Approve/Reject ─────────────────────────────────────────
        if intent in ("approve_leave", "reject_leave", "approve_all_leaves"):
            return self._handle_hr_decision(intent, parsed, user_id, role)

        # ── Leave Balance ─────────────────────────────────────────────
        if intent == "leave_balance":
            return self._show_balance(user_id)

        # ── Leave History ─────────────────────────────────────────────
        if intent == "leave_history":
            return self._leave_history(user_id, role)

        # ── Pending Requests ──────────────────────────────────────────
        if intent == "pending_leaves":
            return self._pending_leaves(user_id, role)

        # ── Approval Status ───────────────────────────────────────────
        if intent == "approval_status":
            return self._approval_status(query, user_id)

        # ── Holiday Calendar ──────────────────────────────────────────
        if intent == "holiday_calendar":
            return self._holiday_calendar()

        # ── Fallback ──────────────────────────────────────────────────
        return AgentResult(
            response=(
                "🏢 **HR Assistant**\n\n"
                "I can help you with:\n"
                "• **Apply leave** — e.g. *Apply casual leave from 2026-05-10 to 2026-05-12 for vacation*\n"
                "• **Check leave balance** — shows all leave types\n"
                "• **View leave history**\n"
                "• **Check pending requests**\n"
                "• **Cancel leave** — e.g. *Cancel leave 5*\n"
                "• **Check approval status** — e.g. *Approval status of leave 3*\n"
                "• **Holiday calendar**\n\n"
                "**Leave Types:** Casual, Sick, Earned, Comp-Off\n\n"
                "How can I help you today?"
            )
        )

    # ──────────────────────────────────────────────────────────────────
    #  Private helpers
    # ──────────────────────────────────────────────────────────────────

    def _parse_with_llm(self, query: str, chat_history: list) -> dict:
        """Use LLM to extract intent and entities (dates, reason, hr) from context."""
        if not self.groq_client:
            # Fallback to simple matching if no LLM
            intent = "unknown"
            q = query.lower()
            if "apply" in q and "leave" in q: intent = "apply_leave"
            elif "cancel" in q and "leave" in q: intent = "cancel_leave"
            elif "balance" in q: intent = "leave_balance"
            elif "history" in q or "my leaves" in q: intent = "leave_history"
            elif "pending" in q: intent = "pending_leaves"
            elif "approval" in q or "status" in q: intent = "approval_status"
            elif "holiday" in q or "calendar" in q: intent = "holiday_calendar"
            
            return {
                "intent": intent,
                "start_date": _extract_dates(query)[0] if _extract_dates(query) else None,
                "end_date": _extract_dates(query)[1] if len(_extract_dates(query)) > 1 else None,
                "leave_type": _extract_leave_type(query),
                "reason": _extract_reason(query),
                "hr": _extract_hr(query)
            }

        sys_prompt = f"""You are an HR intent extraction system. 
You must analyze the user's latest query, considering the chat history, and output ONLY valid JSON.
Today's date is {date.today().isoformat()}.

Extract these fields:
- intent: strictly one of ["apply_leave", "cancel_leave", "approve_leave", "reject_leave", "approve_all_leaves", "leave_balance", "leave_history", "pending_leaves", "approval_status", "holiday_calendar", "unknown"]
- start_date: YYYY-MM-DD (if mentioned for leave application)
- end_date: YYYY-MM-DD (if mentioned. if only one day mentioned, end_date = start_date)
- leave_type: one of ["casual", "sick", "earned", "comp_off"]
- reason: brief string reason for leave
- hr: assigned HR username if mentioned
- leave_id: extract any mentioned leave/request ID as a number

Return ONLY a JSON object. No markdown, no intro/outro text.
If the user wants to approve/reject a leave, set the intent to "approve_leave" or "reject_leave" and extract the leave_id."""

        history_text = "\n".join([f"{msg['role']}: {msg['query']}" for msg in chat_history[-3:]])
        user_prompt = f"Chat History:\n{history_text}\n\nLatest Query: {query}"

        try:
            res = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.groq_model,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            print("LLM Parsing Error:", e)
            return {"intent": "unknown"}

    def _apply_leave_parsed(self, parsed: dict, user_id: str, query: str) -> AgentResult:
        start_date = parsed.get("start_date")
        end_date = parsed.get("end_date")
        leave_type = parsed.get("leave_type") or "casual"
        assigned_hr = parsed.get("hr") or ""
        reason = parsed.get("reason") or ""

        # For CONFIRM flows (adaptive-card submit button), prefer deterministic parsing
        # from the submitted text. This prevents losing the typed reason if the LLM
        # returns partial JSON.
        if query.strip().upper().startswith("CONFIRM"):
            dates = _extract_dates(query)
            if not start_date and dates:
                start_date = dates[0]
            if not end_date:
                end_date = dates[1] if len(dates) > 1 else start_date

            leave_type = _extract_leave_type(query) or leave_type

            extracted_reason = _extract_reason(query)
            if extracted_reason:
                reason = extracted_reason

            if not assigned_hr:
                assigned_hr = _extract_hr(query)

        if not start_date or not end_date or not query.strip().upper().startswith("CONFIRM"):
            # Return an adaptive card for leave application form (pre-filled if data exists)
            return self._render_leave_form(user_id, parsed)

        # ── Validate dates ────────────────────────────────────────
        validation_error = database.validate_leave_dates(start_date, end_date)
        if validation_error:
            return AgentResult(response=f"❌ **Cannot apply leave:** {validation_error}")

        # ── Check overlapping leaves ──────────────────────────────
        overlaps = database.check_overlapping_leaves(user_id, start_date, end_date)
        if overlaps:
            overlap_info = "\n".join(
                f"  • Leave #{o['id']}: {o['start_date']} to {o['end_date']} ({o['status']})"
                for o in overlaps
            )
            return AgentResult(
                response=f"❌ **Overlapping leave found:**\n{overlap_info}\n\n"
                "Please cancel the existing leave first or choose different dates."
            )

        # ── Check leave balance for the specific type ─────────────
        working_days = database.count_working_days(start_date, end_date)
        balance = database.get_leave_balance(user_id, leave_type)
        if isinstance(balance, dict):
            balance = balance.get(leave_type, {}).get("remaining", 0)
        if working_days > balance:
            return AgentResult(
                response=f"❌ **Insufficient {LEAVE_TYPE_LABELS.get(leave_type, leave_type)} balance.** "
                f"You need {working_days} working days but only have {balance} days remaining."
            )

        # ── If no HR assigned, show HR picker ─────────────────────
        if not assigned_hr:
            hr_users = database.get_hr_users()
            if hr_users:
                # Return adaptive card with HR dropdown
                return self._render_hr_picker(
                    start_date, end_date, leave_type, reason, hr_users, working_days
                )
            # No HR users exist — proceed without assignment
            assigned_hr = ""

        # ── Check holidays in range ───────────────────────────────
        holiday_note = _check_holidays_in_range(start_date, end_date)

        # ── Apply the leave ───────────────────────────────────────
        result = database.apply_leave(
            user_id, start_date, end_date, reason,
            leave_type=leave_type, assigned_hr=assigned_hr,
        )

        response = (
            f'<div class="adaptive-card">'
            f'<div class="adaptive-card-header success"><i class="fas fa-check-circle"></i> Leave Request Submitted</div>'
            f'<div class="adaptive-card-body">'
            f'<div class="info-grid">'
            f'<div><strong>Request ID:</strong> #{result.request_id}</div>'
            f'<div><strong>Status:</strong> <span class="badge warning">Pending HR</span></div>'
            f'<div><strong>Type:</strong> {LEAVE_TYPE_LABELS.get(leave_type, leave_type)}</div>'
            f'<div><strong>Dates:</strong> {start_date} to {end_date}</div>'
            f'<div><strong>Working days:</strong> {working_days}</div>'
            f'<div><strong>Assigned HR:</strong> {assigned_hr or "Any available"}</div>'
            f'</div>'
            f'<div class="info-row" style="margin-top:10px;"><strong>Reason:</strong> {reason or "Not specified"}</div>'
            f'<div class="info-row"><strong>Remaining {LEAVE_TYPE_LABELS.get(leave_type, leave_type)}:</strong> {balance - working_days} days</div>'
            f'</div></div>'
        )

        if holiday_note:
            response += f"\n\n📅 **Note:** {holiday_note}"

        return AgentResult(response=response, approval_required=True)

    def _render_leave_form(self, user_id: str, prefill: dict = None) -> AgentResult:
        """Render an adaptive card for leave application when dates are missing."""
        prefill = prefill or {}
        p_type = prefill.get("leave_type") or "casual"
        p_start = prefill.get("start_date") or ""
        p_end = prefill.get("end_date") or ""
        p_reason = prefill.get("reason") or ""
        p_hr = prefill.get("hr") or ""

        hr_users = database.get_hr_users()
        balance = database.get_leave_balance(user_id)

        # Build balance summary as proper HTML
        if isinstance(balance, dict):
            balance_html = '<div class="info-grid">'
            for lt, info in balance.items():
                pct = round((info['remaining'] / max(info['total'], 1)) * 100)
                color = '#34d399' if pct > 50 else '#fb923c' if pct > 25 else '#f87171'
                balance_html += (
                    f'<div>'
                    f'<strong>{LEAVE_TYPE_LABELS.get(lt, lt)}</strong>'
                    f'{info["remaining"]}/{info["total"]} remaining'
                    f'<div style="height:4px;background:rgba(255,255,255,.06);border-radius:2px;margin-top:4px;">'
                    f'<div style="height:100%;width:{pct}%;background:{color};border-radius:2px;"></div>'
                    f'</div></div>'
                )
            balance_html += '</div>'
        else:
            balance_html = f'<p>Total: {balance} days</p>'

        hr_list = ""
        if hr_users:
            hr_items = "".join(f'<code>{h["username"]}</code> ' for h in hr_users)
            hr_list = f'<p style="margin-top:10px;"><strong>Available HR:</strong> {hr_items}</p>'

        return AgentResult(
            response=(
                f'<div class="adaptive-card">'
                f'<div class="adaptive-card-header primary"><i class="fas fa-calendar-plus"></i> Apply Leave — Review Details</div>'
                f'<div class="adaptive-card-body">'
                f'<p><strong>Your Leave Balances:</strong></p>'
                f'{balance_html}'
                f'<div class="help-box" style="display:flex; flex-direction:column; gap:10px; margin-top:16px;">'
                f'<select class="message-input ac-leave-type" style="width:100%;">'
                f'<option value="casual" {"selected" if p_type=="casual" else ""}>Casual Leave</option>'
                f'<option value="sick" {"selected" if p_type=="sick" else ""}>Sick Leave</option>'
                f'<option value="earned" {"selected" if p_type=="earned" else ""}>Earned Leave</option>'
                f'<option value="comp_off" {"selected" if p_type=="comp_off" else ""}>Compensatory Off</option>'
                f'</select>'
                f'<div style="display:flex; gap:10px;">'
                f'<input type="date" class="message-input ac-start-date" style="flex:1;" value="{p_start}" />'
                f'<input type="date" class="message-input ac-end-date" style="flex:1;" value="{p_end}" />'
                f'</div>'
                f'<input type="text" class="message-input ac-reason" placeholder="Reason for leave..." style="width:100%;" value="{p_reason}" />'
                f'<select class="message-input ac-hr" style="width:100%;">'
                f'<option value="">-- Select Assigned HR --</option>'
                + "".join([f'<option value="{h["username"]}" {"selected" if p_hr==h["username"] else ""}>{h["username"]}</option>' for h in hr_users]) +
                f'</select>'
                f'<button class="icon-btn" style="background:var(--accent); color:white; justify-content:center; width:100%; border-radius:8px;" onclick="submitAdaptiveLeaveForm(this)"><i class="fas fa-paper-plane"></i> Confirm & Submit Leave</button>'
                f'</div>'
                f'</div></div>'
            ),
            tool_calls=[{
                "type": "adaptive_card",
                "card_type": "leave_form",
                "data": {
                    "leave_types": list(LEAVE_TYPE_LABELS.items()),
                    "hr_users": hr_users,
                    "balance": balance if isinstance(balance, dict) else {},
                }
            }]
        )

    def _render_hr_picker(
        self, start_date: str, end_date: str,
        leave_type: str, reason: str,
        hr_users: list[dict], working_days: int,
    ) -> AgentResult:
        """Render an adaptive card to pick an HR for the leave request."""
        hr_buttons = "".join(
            f'<button class="icon-btn" style="background:var(--surface2); border:1px solid var(--border); width:100%; justify-content:center; margin-bottom:8px;" onclick="submitAdaptiveHRSelect(\'{leave_type}\', \'{start_date}\', \'{end_date}\', \'{reason}\', \'{h["username"]}\')">'
            f'<i class="fas fa-user"></i> {h["username"]}'
            f'</button>' 
            for h in hr_users
        )
        return AgentResult(
            response=(
                f'<div class="adaptive-card">'
                f'<div class="adaptive-card-header info"><i class="fas fa-clipboard-user"></i> Select HR Assigned</div>'
                f'<div class="adaptive-card-body">'
                f'<div class="info-grid">'
                f'<div><strong>Type:</strong> {LEAVE_TYPE_LABELS.get(leave_type, leave_type)}</div>'
                f'<div><strong>Dates:</strong> {start_date} to {end_date}</div>'
                f'<div><strong>Working Days:</strong> {working_days}</div>'
                f'<div><strong>Reason:</strong> {reason or "Not specified"}</div>'
                f'</div>'
                f'<p style="margin-top:10px; margin-bottom:10px;"><strong>Select an available HR to route your request to:</strong></p>'
                f'{hr_buttons}'
                f'</div></div>'
            ),
            tool_calls=[{
                "type": "adaptive_card",
                "card_type": "hr_picker",
                "data": {
                    "hr_users": hr_users,
                    "leave_type": leave_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "reason": reason,
                    "working_days": working_days,
                }
            }]
        )

    def _cancel_leave(self, query: str, user_id: str) -> AgentResult:
        leave_id = _extract_id(query)
        if leave_id is None:
            return AgentResult(
                response="Please specify the leave ID to cancel.\n\nExample: *Cancel leave 5*"
            )
        result_msg = database.cancel_leave(leave_id, user_id)
        icon = "✅" if "cancelled" in result_msg else "❌"
        return AgentResult(response=f"{icon} {result_msg}")

    def _handle_hr_decision(self, intent: str, parsed: dict, user_id: str, role: str) -> AgentResult:
        if role not in ("hr", "admin", "manager"):
            return AgentResult(response="❌ Only HR or managers can approve/reject leave requests.")
        
        if intent == "approve_all_leaves":
            pending = database.get_pending_approvals()
            leave_requests = [a for a in pending if a["request_type"] == "leave"]
            if not leave_requests:
                return AgentResult(response="✅ No pending leave requests to approve.")
            
            count = 0
            for req in leave_requests:
                database.process_leave_decision(req["request_id"], "approved", user_id)
                count += 1
            return AgentResult(response=f"🟢 Successfully approved all {count} pending leave requests.")

        leave_id = parsed.get("leave_id")
        if not leave_id:
            return AgentResult(response="Please specify the leave ID you wish to approve or reject.")
            
        status = "approved" if intent == "approve_leave" else "rejected"
        result_msg = database.process_leave_decision(int(leave_id), status, user_id)
        
        icon = "🟢" if status == "approved" else "🔴"
        return AgentResult(response=f"{icon} {result_msg}")

    def _show_balance(self, user_id: str) -> AgentResult:
        """Show leave balance for all leave types."""
        balance = database.get_leave_balance(user_id)

        if isinstance(balance, dict) and balance:
            rows = []
            total_remaining = 0
            for lt in ["casual", "sick", "earned", "comp_off"]:
                info = balance.get(lt)
                if info:
                    bar_len = 10
                    filled = round((info["remaining"] / max(info["total"], 1)) * bar_len) if info["total"] > 0 else 0
                    bar = "█" * filled + "░" * (bar_len - filled)
                    rows.append(
                        f"| {LEAVE_TYPE_LABELS.get(lt, lt)} | {info['total']} | {info['used']} | "
                        f"**{info['remaining']}** | {bar} |"
                    )
                    total_remaining += info["remaining"]

            table = (
                "| Leave Type | Total | Used | Remaining | Usage |\n"
                "|---|---|---|---|---|\n"
                + "\n".join(rows)
            )
            return AgentResult(
                response=f"📊 **Your Leave Balances (2026)**\n\n{table}\n\n"
                f"**Total Remaining:** {total_remaining} days"
            )

        return AgentResult(response=f"📊 **Leave Balance:** {balance} days remaining.")

    def _leave_history(self, user_id: str, role: str) -> AgentResult:
        if role in ("hr", "admin"):
            leaves = database.get_all_leaves()
            title = "📋 **All Leave Requests (HR View)**"
        else:
            leaves = database.list_leaves(user_id)
            title = "📋 **Your Leave History**"

        if not leaves:
            return AgentResult(response=f"{title}\n\nNo leave records found.")

        rows = []
        for lv in leaves:
            status_icon = {
                "pending": "🟡", "approved": "🟢",
                "rejected": "🔴", "cancelled": "⚫"
            }.get(lv["status"], "⚪")
            user_col = f" | {lv['user_id']}" if "user_id" in lv else ""
            rows.append(
                f"| {lv['id']} | {lv['start_date']} | {lv['end_date']} "
                f"| {status_icon} {lv['status']} | {lv.get('reason', '')}{user_col} |"
            )

        header = "| ID | Start | End | Status | Reason |"
        if role in ("hr", "admin"):
            header = "| ID | Start | End | Status | Reason | User |"
        separator = "|" + "|".join(["---"] * header.count("|")) + "|"
        table = "\n".join([header, separator] + rows)
        return AgentResult(response=f"{title}\n\n{table}")

    def _pending_leaves(self, user_id: str, role: str) -> AgentResult:
        if role in ("hr",):
            # HR sees only their assigned pending approvals
            approvals = database.get_approvals_for_hr(user_id)
            if not approvals:
                return AgentResult(response="✅ No pending leave approvals assigned to you.")

            rows = []
            for a in approvals:
                leave = database.get_leave_by_id(a["request_id"])
                if leave:
                    rows.append(
                        f"| {a['id']} | {leave.get('user_id', 'N/A')} | "
                        f"{leave['start_date']} to {leave['end_date']} | "
                        f"{leave.get('leave_type', 'casual')} | "
                        f"{a.get('created_at', 'N/A')[:10] if a.get('created_at') else 'N/A'} |"
                    )

            header = "| Approval ID | Employee | Dates | Type | Requested On |"
            separator = "|---|---|---|---|---|"
            table = "\n".join([header, separator] + rows)
            return AgentResult(
                response=(
                    f"📋 **Your Pending Leave Approvals ({len(rows)} requests)**\n\n{table}\n\n"
                    "Use the **Pending Requests** tab in the sidebar to approve or reject."
                ),
                tool_calls=[{"type": "adaptive_card", "card_type": "show_pending_tab"}]
            )

        elif role in ("manager", "admin"):
            approvals = database.get_pending_approvals()
            leave_approvals = [a for a in approvals if a["request_type"] == "leave"]
            if not leave_approvals:
                return AgentResult(response="✅ No pending leave approvals at this time.")

            rows = []
            for a in leave_approvals:
                leave = database.get_leave_by_id(a["request_id"])
                if leave:
                    rows.append(
                        f"| {a['id']} | {leave.get('user_id', 'N/A')} | "
                        f"{leave['start_date']} to {leave['end_date']} | "
                        f"{a.get('created_at', 'N/A')[:10] if a.get('created_at') else 'N/A'} |"
                    )

            header = "| Approval ID | Employee | Dates | Requested On |"
            separator = "|---|---|---|---|"
            table = "\n".join([header, separator] + rows)
            return AgentResult(
                response=f"📋 **Pending Leave Approvals**\n\n{table}\n\n"
                "Use the **Pending Requests** tab to approve or reject."
            )
        else:
            pending = database.get_pending_leaves(user_id)
            if not pending:
                return AgentResult(response="✅ You have no pending leave requests.")

            rows = "\n".join(
                f"• **Leave #{p['id']}:** {p['start_date']} to {p['end_date']} — {p.get('reason', 'No reason')}"
                for p in pending
            )
            return AgentResult(response=f"🟡 **Your Pending Leave Requests**\n\n{rows}")

    def _approval_status(self, query: str, user_id: str) -> AgentResult:
        leave_id = _extract_id(query)
        if leave_id is None:
            leaves = database.list_leaves(user_id)
            if not leaves:
                return AgentResult(response="No leave requests found.")
            rows = "\n".join(
                f"• **Leave #{lv['id']}:** {lv['status']} ({lv['start_date']} to {lv['end_date']})"
                for lv in leaves
            )
            return AgentResult(response=f"📊 **Your Leave Statuses**\n\n{rows}")

        status = database.get_approval_status("leave", leave_id)
        leave = database.get_leave_by_id(leave_id)
        if leave is None:
            return AgentResult(response=f"❌ Leave request #{leave_id} not found.")

        status_icon = {"pending": "🟡", "approved": "🟢", "rejected": "🔴"}.get(status, "⚪")
        return AgentResult(
            response=(
                f"📊 **Approval Status for Leave #{leave_id}**\n\n"
                f"• **Status:** {status_icon} {status}\n"
                f"• **Dates:** {leave['start_date']} to {leave['end_date']}\n"
                f"• **Leave status:** {leave['status']}\n"
                f"• **Reason:** {leave.get('reason', 'Not specified')}"
            )
        )

    def _holiday_calendar(self) -> AgentResult:
        holidays = database.COMPANY_HOLIDAYS_2026
        rows = "\n".join(f"• **{h}** — {_holiday_name(h)}" for h in holidays)
        return AgentResult(
            response=f"📅 **Company Holiday Calendar 2026**\n\n{rows}\n\n"
            "*Note: Weekends (Saturday & Sunday) are also non-working days.*"
        )


# ──────────────────────────────────────────────────────────────────────────
#  Module-level helpers
# ──────────────────────────────────────────────────────────────────────────

def _extract_dates(text: str) -> list[str]:
    """Extract YYYY-MM-DD dates from text."""
    return re.findall(r"\d{4}-\d{2}-\d{2}", text)


def _extract_id(text: str) -> int | None:
    """Extract a numeric ID from text (e.g., 'cancel leave 5' → 5)."""
    match = re.search(r"(?:leave|request|id)\s*#?\s*(\d+)", text)
    if match:
        return int(match.group(1))
    numbers = re.findall(r"\d+", text)
    non_date_numbers = [n for n in numbers if len(n) <= 3]
    if non_date_numbers:
        return int(non_date_numbers[-1])
    return None


def _extract_leave_type(text: str) -> str:
    """Extract leave type from text."""
    t = text.lower()
    if "sick" in t:
        return "sick"
    if "earned" in t:
        return "earned"
    if "comp" in t:
        return "comp_off"
    return "casual"  # default


def _extract_hr(text: str) -> str:
    """Extract HR username from text (e.g., 'hr john_hr' → 'john_hr')."""
    match = re.search(r"\bhr\s+([a-zA-Z0-9_]+)\s*$", text.strip())
    if match:
        candidate = match.group(1)
        # Verify it's actually an HR user, not a keyword
        if candidate not in ("leave", "team", "policy", "department", "agent"):
            return candidate
    return ""


def _extract_reason(text: str) -> str:
    """Extract reason from text (after 'for' or 'reason')."""
    match = re.search(r"\bfor\s+(.+?)(?:\s+from\s+|\s+between\s+|\s+hr\s+|$)", text, re.IGNORECASE)
    if match:
        reason = match.group(1).strip()
        reason = re.sub(r"\d{4}-\d{2}-\d{2}", "", reason).strip()
        if reason:
            return reason

    match = re.search(r"\breason\s*:?\s*(.+?)(?:\s+hr\s+|$)", text, re.IGNORECASE)
    if match:
        reason = match.group(1).strip()
        reason = re.sub(r"\d{4}-\d{2}-\d{2}", "", reason).strip()
        if reason:
            return reason

    return ""


def _check_holidays_in_range(start_date: str, end_date: str) -> str:
    """Check if any holidays fall within the leave range."""
    holidays_in_range = []
    current = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    while current <= end:
        dt_str = current.isoformat()
        if database.is_holiday(dt_str):
            holidays_in_range.append(f"{dt_str} ({_holiday_name(dt_str)})")
        current += timedelta(days=1)
    if holidays_in_range:
        return f"The following holidays fall in your leave period: {', '.join(holidays_in_range)}"
    return ""


_HOLIDAY_NAMES = {
    "2026-01-01": "New Year's Day",
    "2026-01-26": "Republic Day",
    "2026-03-10": "Holi",
    "2026-04-02": "Good Friday",
    "2026-05-01": "May Day",
    "2026-08-15": "Independence Day",
    "2026-10-02": "Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-09": "Diwali",
    "2026-12-25": "Christmas",
}


def _holiday_name(dt: str) -> str:
    return _HOLIDAY_NAMES.get(dt, "Holiday")
