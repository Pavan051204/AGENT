import re
from datetime import date, timedelta

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

    def handle(self, state: dict) -> AgentResult:
        query = state.get("query", "").lower()
        user_id = state.get("user_id", "")
        role = state.get("role", "")

        # ── Apply Leave ───────────────────────────────────────────────
        if "apply" in query and "leave" in query:
            return self._apply_leave(query, user_id)

        # ── Cancel Leave ──────────────────────────────────────────────
        if "cancel" in query and "leave" in query:
            return self._cancel_leave(query, user_id)

        # ── Leave Balance ─────────────────────────────────────────────
        if "balance" in query:
            return self._show_balance(user_id)

        # ── Leave History ─────────────────────────────────────────────
        if "history" in query or ("list" in query and "leave" in query) or "my leaves" in query:
            return self._leave_history(user_id, role)

        # ── Pending Requests ──────────────────────────────────────────
        if "pending" in query:
            return self._pending_leaves(user_id, role)

        # ── Approval Status ───────────────────────────────────────────
        if "approval" in query or "status" in query:
            return self._approval_status(query, user_id)

        # ── Holiday Calendar ──────────────────────────────────────────
        if "holiday" in query or "calendar" in query:
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

    def _apply_leave(self, query: str, user_id: str) -> AgentResult:
        dates = _extract_dates(query)
        if len(dates) < 2:
            # Return an adaptive card for leave application form
            return self._render_leave_form(user_id)

        start_date, end_date = dates[0], dates[1]
        leave_type = _extract_leave_type(query)
        assigned_hr = _extract_hr(query)
        reason = _extract_reason(query)

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
            f"✅ **Leave Request Submitted**\n\n"
            f"• **Request ID:** {result.request_id}\n"
            f"• **Leave Type:** {LEAVE_TYPE_LABELS.get(leave_type, leave_type)}\n"
            f"• **Dates:** {start_date} to {end_date}\n"
            f"• **Working days:** {working_days}\n"
            f"• **Reason:** {reason or 'Not specified'}\n"
            f"• **Assigned HR:** {assigned_hr or 'Any available'}\n"
            f"• **Status:** Pending HR Approval\n"
            f"• **Remaining {LEAVE_TYPE_LABELS.get(leave_type, leave_type)}:** {balance - working_days} days"
        )

        if holiday_note:
            response += f"\n\n📅 **Note:** {holiday_note}"

        return AgentResult(response=response, approval_required=True)

    def _render_leave_form(self, user_id: str) -> AgentResult:
        """Render an adaptive card for leave application when dates are missing."""
        hr_users = database.get_hr_users()
        balance = database.get_leave_balance(user_id)

        # Build balance summary
        if isinstance(balance, dict):
            balance_lines = "\n".join(
                f"  • **{LEAVE_TYPE_LABELS.get(lt, lt)}:** {info['remaining']}/{info['total']} remaining"
                for lt, info in balance.items()
            )
        else:
            balance_lines = f"  • Total: {balance} days"

        hr_list = ""
        if hr_users:
            hr_options = ", ".join(f"`{h['username']}`" for h in hr_users)
            hr_list = f"\n\n**Available HR:** {hr_options}"

        return AgentResult(
            response=(
                "📝 **Apply Leave — Please provide details:**\n\n"
                f"**Your Leave Balances:**\n{balance_lines}\n\n"
                "Please use this format:\n"
                "*Apply [casual/sick/earned] leave from YYYY-MM-DD to YYYY-MM-DD for [reason] hr [hr_username]*\n\n"
                "**Example:**\n"
                "*Apply casual leave from 2026-05-10 to 2026-05-12 for family function hr john_hr*"
                f"{hr_list}"
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
        hr_options = "\n".join(f"  • `{h['username']}`" for h in hr_users)
        return AgentResult(
            response=(
                f"📋 **Almost done! Please select an HR to send your request to:**\n\n"
                f"**Leave Details:**\n"
                f"• Type: {LEAVE_TYPE_LABELS.get(leave_type, leave_type)}\n"
                f"• Dates: {start_date} to {end_date}\n"
                f"• Working Days: {working_days}\n"
                f"• Reason: {reason or 'Not specified'}\n\n"
                f"**Available HR:**\n{hr_options}\n\n"
                "Reply with:\n"
                f"*Apply {leave_type} leave from {start_date} to {end_date} for {reason or 'personal'} hr [HR_USERNAME]*"
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
