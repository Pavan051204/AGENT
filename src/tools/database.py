import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from src.settings import get_config


@dataclass
class LeaveResult:
    request_id: int
    approval_required: bool


# Default annual leave entitlements per leave type
DEFAULT_LEAVE_BALANCES = {
    "casual": 12,
    "sick": 10,
    "earned": 15,
    "comp_off": 0,  # earned on-the-go
}


def _get_conn() -> sqlite3.Connection:
    config = get_config()
    Path(config.app_db_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(config.app_db_path)


def init_db() -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            start_date TEXT,
            end_date TEXT,
            leave_type TEXT DEFAULT 'casual',
            status TEXT,
            reason TEXT,
            assigned_hr TEXT DEFAULT '',
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leave_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            leave_type TEXT,
            total INTEGER,
            used INTEGER DEFAULT 0,
            year INTEGER,
            UNIQUE(user_id, leave_type, year)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            issue_type TEXT,
            priority TEXT,
            status TEXT,
            assigned_engineer TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT,
            request_id INTEGER,
            status TEXT,
            approver_id TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reimbursements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            amount REAL,
            status TEXT,
            category TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            asset_type TEXT,
            status TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id TEXT,
            content TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            event_type TEXT,
            detail TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            created_at TEXT
        )
        """
    )
    # Migrate existing tables: add missing columns silently
    for col, default in [("leave_type", "'casual'"), ("assigned_hr", "''"), ("created_at", "''")]:
        try:
            cur.execute(f"ALTER TABLE leaves ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass  # column already exists
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# User management (RBAC)
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str, role: str) -> int | None:
    """Insert a new user and auto-provision leave balances.

    Returns the user id, or None if the username exists.
    """
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, _now()),
        )
        user_id = cur.lastrowid
        # Auto-provision default leave balances for the new user
        current_year = date.today().year
        for leave_type, total in DEFAULT_LEAVE_BALANCES.items():
            cur.execute(
                "INSERT OR IGNORE INTO leave_balances (user_id, leave_type, total, used, year) VALUES (?, ?, ?, 0, ?)",
                (str(user_id), leave_type, total, current_year),
            )
        conn.commit()
        return user_id
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def provision_leave_balances(user_id: str, year: int | None = None) -> None:
    """Create default leave balance records for a user (idempotent)."""
    if year is None:
        year = date.today().year
    conn = _get_conn()
    cur = conn.cursor()
    for leave_type, total in DEFAULT_LEAVE_BALANCES.items():
        cur.execute(
            "INSERT OR IGNORE INTO leave_balances (user_id, leave_type, total, used, year) VALUES (?, ?, ?, 0, ?)",
            (user_id, leave_type, total, year),
        )
    conn.commit()
    conn.close()


def get_user_by_username(username: str) -> dict | None:
    """Retrieve a user record by username."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, password_hash, role, created_at FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2],
        "role": row[3],
        "created_at": row[4],
    }


def get_user_by_id(user_id: int) -> dict | None:
    """Retrieve a user record by id."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, password_hash, role, created_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2],
        "role": row[3],
        "created_at": row[4],
    }


def apply_leave(
    user_id: str,
    start_date: str,
    end_date: str,
    reason: str,
    leave_type: str = "casual",
    assigned_hr: str = "",
) -> LeaveResult:
    """Apply for leave.  Every leave request is sent to the assigned HR for approval."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO leaves (user_id, start_date, end_date, leave_type, status, reason, assigned_hr, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, start_date, end_date, leave_type, "pending", reason, assigned_hr, _now()),
    )
    request_id = cur.lastrowid
    conn.commit()
    conn.close()

    # All leave requests require HR approval
    create_approval("leave", request_id, approver_id=assigned_hr)

    return LeaveResult(request_id=request_id, approval_required=True)


def list_leaves(user_id: str) -> list[dict]:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, start_date, end_date, status, reason FROM leaves WHERE user_id = ?",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": row[0],
            "start_date": row[1],
            "end_date": row[2],
            "status": row[3],
            "reason": row[4],
        }
        for row in rows
    ]


def get_leave_balance(user_id: str, leave_type: str | None = None) -> dict | int:
    """Get leave balance.  If leave_type is given returns an int, else a dict of all types."""
    current_year = date.today().year
    conn = _get_conn()
    cur = conn.cursor()

    # Ensure balances exist for this user
    for lt, total in DEFAULT_LEAVE_BALANCES.items():
        cur.execute(
            "INSERT OR IGNORE INTO leave_balances (user_id, leave_type, total, used, year) VALUES (?, ?, ?, 0, ?)",
            (user_id, lt, total, current_year),
        )
    conn.commit()

    if leave_type:
        cur.execute(
            "SELECT total, used FROM leave_balances WHERE user_id = ? AND leave_type = ? AND year = ?",
            (user_id, leave_type, current_year),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return max(0, row[0] - row[1])
        return DEFAULT_LEAVE_BALANCES.get(leave_type, 0)

    # Return all types
    cur.execute(
        "SELECT leave_type, total, used FROM leave_balances WHERE user_id = ? AND year = ?",
        (user_id, current_year),
    )
    rows = cur.fetchall()
    conn.close()
    result = {}
    for lt, total, used in rows:
        result[lt] = {"total": total, "used": used, "remaining": max(0, total - used)}
    return result


def deduct_leave_balance(user_id: str, leave_type: str, days: int) -> bool:
    """Deduct days from leave balance.  Returns False if insufficient."""
    current_year = date.today().year
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT total, used FROM leave_balances WHERE user_id = ? AND leave_type = ? AND year = ?",
        (user_id, leave_type, current_year),
    )
    row = cur.fetchone()
    if not row or (row[0] - row[1]) < days:
        conn.close()
        return False
    cur.execute(
        "UPDATE leave_balances SET used = used + ? WHERE user_id = ? AND leave_type = ? AND year = ?",
        (days, user_id, leave_type, current_year),
    )
    conn.commit()
    conn.close()
    return True


def restore_leave_balance(user_id: str, leave_type: str, days: int) -> None:
    """Restore days to leave balance (on cancel / reject)."""
    current_year = date.today().year
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE leave_balances SET used = MAX(0, used - ?) WHERE user_id = ? AND leave_type = ? AND year = ?",
        (days, user_id, leave_type, current_year),
    )
    conn.commit()
    conn.close()


def get_hr_users() -> list[dict]:
    """Get all users with role 'hr'.  Used for HR selection dropdown."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role FROM users WHERE role = 'hr'"
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "role": r[2]} for r in rows]


def get_approvals_for_hr(hr_username: str) -> list[dict]:
    """Get pending approvals assigned to a specific HR user."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT a.id, a.request_type, a.request_id, a.status, a.created_at
           FROM approvals a
           JOIN leaves l ON a.request_id = l.id AND a.request_type = 'leave'
           WHERE a.status = 'pending' AND LOWER(l.assigned_hr) = LOWER(?)""",
        (hr_username,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "request_type": r[1], "request_id": r[2], "status": r[3], "created_at": r[4]}
        for r in rows
    ]


def create_ticket(user_id: str, issue_type: str, priority: str) -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tickets (user_id, issue_type, priority, status, assigned_engineer) VALUES (?, ?, ?, ?, ?)",
        (user_id, issue_type, priority, "open", ""),
    )
    ticket_id = cur.lastrowid
    conn.commit()
    conn.close()
    return ticket_id


def request_asset(user_id: str, asset_type: str) -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO assets (user_id, asset_type, status, created_at) VALUES (?, ?, ?, ?)",
        (user_id, asset_type, "pending", _now()),
    )
    asset_id = cur.lastrowid
    conn.commit()
    conn.close()
    create_approval("asset", asset_id, approver_id="")
    return asset_id


def submit_reimbursement(user_id: str, amount: float, category: str) -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reimbursements (user_id, amount, status, category, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, "pending", category, _now()),
    )
    reimb_id = cur.lastrowid
    conn.commit()
    conn.close()
    if amount > 5000:
        create_approval("reimbursement", reimb_id, approver_id="")
    return reimb_id


def create_approval(request_type: str, request_id: int, approver_id: str) -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO approvals (request_type, request_id, status, approver_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (request_type, request_id, "pending", approver_id, _now()),
    )
    approval_id = cur.lastrowid
    conn.commit()
    conn.close()
    return approval_id


def approve_request(approval_id: int, approver_id: str, status: str) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE approvals SET status = ?, approver_id = ? WHERE id = ?",
        (status, approver_id, approval_id),
    )
    conn.commit()
    conn.close()


def get_approval_status(request_type: str, request_id: int) -> str:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT status FROM approvals WHERE request_type = ? AND request_id = ? ORDER BY id DESC LIMIT 1",
        (request_type, request_id),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "none"


def save_memory(user_id: str, session_id: str, content: str) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memory (user_id, session_id, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, session_id, content, _now()),
    )
    conn.commit()
    conn.close()


def load_memory(user_id: str, limit: int = 10) -> list[str]:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT content FROM memory WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def log_event(user_id: str, event_type: str, detail: str) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO logs (user_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
        (user_id, event_type, detail, _now()),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Leave management – extended functions
# ---------------------------------------------------------------------------

def get_leave_by_id(leave_id: int) -> dict | None:
    """Retrieve a single leave request by its ID."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, start_date, end_date, status, reason, leave_type, assigned_hr FROM leaves WHERE id = ?",
        (leave_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row[0], "user_id": row[1], "start_date": row[2],
        "end_date": row[3], "status": row[4], "reason": row[5],
        "leave_type": row[6] or "casual", "assigned_hr": row[7] or "",
    }


def cancel_leave(leave_id: int, user_id: str) -> str:
    """Cancel a pending leave request.  Returns a status message."""
    leave = get_leave_by_id(leave_id)
    if leave is None:
        return "Leave request not found."
    if leave["user_id"] != user_id:
        return "You can only cancel your own leave requests."
    if leave["status"] not in ("pending",):
        return f"Cannot cancel leave with status '{leave['status']}'. Only pending leaves can be cancelled."
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE leaves SET status = 'cancelled' WHERE id = ?", (leave_id,))
    conn.commit()
    conn.close()
    return f"Leave request {leave_id} has been cancelled."


def get_pending_leaves(user_id: str) -> list[dict]:
    """Get all pending leave requests for a user."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, start_date, end_date, status, reason FROM leaves WHERE user_id = ? AND status = 'pending'",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "start_date": r[1], "end_date": r[2], "status": r[3], "reason": r[4]}
        for r in rows
    ]


def check_overlapping_leaves(user_id: str, start_date: str, end_date: str) -> list[dict]:
    """Check for any existing leaves that overlap with the given date range."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, start_date, end_date, status FROM leaves
           WHERE user_id = ? AND status IN ('pending', 'approved')
           AND start_date <= ? AND end_date >= ?""",
        (user_id, end_date, start_date),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "start_date": r[1], "end_date": r[2], "status": r[3]}
        for r in rows
    ]


def update_leave_status(leave_id: int, status: str) -> None:
    """Update the status of a leave request (approved / rejected)."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE leaves SET status = ? WHERE id = ?", (status, leave_id))
    conn.commit()
    conn.close()


def get_all_leaves(status_filter: str | None = None) -> list[dict]:
    """Get all leave requests (for HR / admin view).  Optionally filter by status."""
    conn = _get_conn()
    cur = conn.cursor()
    if status_filter:
        cur.execute(
            "SELECT id, user_id, start_date, end_date, status, reason FROM leaves WHERE status = ?",
            (status_filter,),
        )
    else:
        cur.execute("SELECT id, user_id, start_date, end_date, status, reason FROM leaves")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "user_id": r[1], "start_date": r[2], "end_date": r[3], "status": r[4], "reason": r[5]}
        for r in rows
    ]


def get_pending_approvals(approver_role: str | None = None) -> list[dict]:
    """Get all pending approval records.  Used by managers / HR / admin."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, request_type, request_id, status, approver_id, created_at FROM approvals WHERE status = 'pending'"
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "request_type": r[1], "request_id": r[2],
            "status": r[3], "approver_id": r[4], "created_at": r[5],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Holiday calendar & date validation
# ---------------------------------------------------------------------------

# Static holiday list (can be extended or moved to DB)
COMPANY_HOLIDAYS_2026 = [
    "2026-01-01",  # New Year
    "2026-01-26",  # Republic Day
    "2026-03-10",  # Holi
    "2026-04-02",  # Good Friday (approx)
    "2026-05-01",  # May Day
    "2026-08-15",  # Independence Day
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-20",  # Dussehra (approx)
    "2026-11-09",  # Diwali (approx)
    "2026-12-25",  # Christmas
]


def is_holiday(dt: str) -> bool:
    """Check if a date string (YYYY-MM-DD) falls on a company holiday."""
    return dt in COMPANY_HOLIDAYS_2026


def is_weekend(dt: str) -> bool:
    """Check if a date string falls on a weekend (Saturday or Sunday)."""
    d = date.fromisoformat(dt)
    return d.weekday() >= 5  # 5 = Saturday, 6 = Sunday


def validate_leave_dates(start_date: str, end_date: str) -> str | None:
    """Validate leave dates.  Returns an error message or None if valid."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD."

    if end < start:
        return "End date cannot be before start date."

    if start < date.today():
        return "Cannot apply leave for past dates."

    if (end - start).days > 30:
        return "Leave duration cannot exceed 30 days in a single request."

    # Check if all days are weekends / holidays
    all_off = True
    current = start
    while current <= end:
        dt_str = current.isoformat()
        if not is_weekend(dt_str) and not is_holiday(dt_str):
            all_off = False
            break
        current += timedelta(days=1)
    if all_off:
        return "The selected dates are all weekends or holidays. No leave needed."

    return None  # Valid


def count_working_days(start_date: str, end_date: str) -> int:
    """Count working days (excluding weekends and holidays) in a date range."""
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    count = 0
    current = start
    while current <= end:
        dt_str = current.isoformat()
        if not is_weekend(dt_str) and not is_holiday(dt_str):
            count += 1
        current += timedelta(days=1)
    return count


def _leave_days(start_date: str, end_date: str) -> int:
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()
    return (end - start).days + 1


def _now() -> str:
    return datetime.utcnow().isoformat()
