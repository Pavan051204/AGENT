"""Cleanup script: remove users with reserved test email domains.

Why:
- Addresses like *@example.com are reserved (RFC 2606) and will bounce in Exchange/Office 365.
- During local testing, such users/leaves can remain in the DB and appear in approvals.

Usage:
  python cleanup_reserved_email_users.py            # dry-run (prints what would be deleted)
  python cleanup_reserved_email_users.py --apply   # perform deletion

This deletes:
- users with email domain in {example.com, example.org, example.net}
- their leave balances
- their leaves/tickets/assets/reimbursements
- approvals linked to those requests
- their memory/log rows

NOTE: This is irreversible for the current DB file.
"""

from __future__ import annotations

import argparse

from src.tools import database


RESERVED_DOMAINS = {"example.com", "example.org", "example.net"}


def _is_reserved(email: str) -> bool:
    email_l = (email or "").strip().lower()
    if "@" not in email_l:
        return False
    domain = email_l.rsplit("@", 1)[-1]
    return domain in RESERVED_DOMAINS


def _delete_approvals_for(cur, request_type: str, ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join(["?"] * len(ids))
    cur.execute(
        f"DELETE FROM approvals WHERE request_type = ? AND request_id IN ({placeholders})",
        [request_type, *ids],
    )
    return cur.rowcount


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually delete rows")
    args = parser.parse_args()

    conn = database._get_conn()
    cur = conn.cursor()

    cur.execute("SELECT username, email, role FROM users")
    rows = cur.fetchall()

    reserved_users = [(u, e, r) for (u, e, r) in rows if _is_reserved(e)]

    print(f"Found {len(reserved_users)} user(s) with reserved domains: {sorted(RESERVED_DOMAINS)}")
    for u, e, r in reserved_users:
        print(f"- {u} ({r}) -> {e}")

    if not reserved_users:
        conn.close()
        return 0

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to delete.")
        conn.close()
        return 0

    deleted = {
        "users": 0,
        "leave_balances": 0,
        "leaves": 0,
        "tickets": 0,
        "assets": 0,
        "reimbursements": 0,
        "approvals": 0,
        "memory": 0,
        "logs": 0,
    }

    for username, email, role in reserved_users:
        # Leaves
        cur.execute("SELECT id FROM leaves WHERE user_id = ?", (username,))
        leave_ids = [r[0] for r in cur.fetchall()]
        deleted["approvals"] += _delete_approvals_for(cur, "leave", leave_ids)
        if leave_ids:
            placeholders = ",".join(["?"] * len(leave_ids))
            cur.execute(f"DELETE FROM leaves WHERE id IN ({placeholders})", leave_ids)
            deleted["leaves"] += cur.rowcount

        # Tickets
        cur.execute("SELECT id FROM tickets WHERE user_id = ?", (username,))
        ticket_ids = [r[0] for r in cur.fetchall()]
        deleted["approvals"] += _delete_approvals_for(cur, "ticket", ticket_ids)
        if ticket_ids:
            placeholders = ",".join(["?"] * len(ticket_ids))
            cur.execute(f"DELETE FROM tickets WHERE id IN ({placeholders})", ticket_ids)
            deleted["tickets"] += cur.rowcount

        # Assets
        cur.execute("SELECT id FROM assets WHERE user_id = ?", (username,))
        asset_ids = [r[0] for r in cur.fetchall()]
        deleted["approvals"] += _delete_approvals_for(cur, "asset", asset_ids)
        if asset_ids:
            placeholders = ",".join(["?"] * len(asset_ids))
            cur.execute(f"DELETE FROM assets WHERE id IN ({placeholders})", asset_ids)
            deleted["assets"] += cur.rowcount

        # Reimbursements
        cur.execute("SELECT id FROM reimbursements WHERE user_id = ?", (username,))
        reimb_ids = [r[0] for r in cur.fetchall()]
        deleted["approvals"] += _delete_approvals_for(cur, "reimbursement", reimb_ids)
        if reimb_ids:
            placeholders = ",".join(["?"] * len(reimb_ids))
            cur.execute(f"DELETE FROM reimbursements WHERE id IN ({placeholders})", reimb_ids)
            deleted["reimbursements"] += cur.rowcount

        # Memory/logs
        cur.execute("DELETE FROM memory WHERE user_id = ?", (username,))
        deleted["memory"] += cur.rowcount
        cur.execute("DELETE FROM logs WHERE user_id = ?", (username,))
        deleted["logs"] += cur.rowcount

        # Leave balances + user row
        cur.execute("DELETE FROM leave_balances WHERE user_id = ?", (username,))
        deleted["leave_balances"] += cur.rowcount

        cur.execute("DELETE FROM users WHERE username = ?", (username,))
        deleted["users"] += cur.rowcount

    conn.commit()
    conn.close()

    print("\nDeleted:")
    for k, v in deleted.items():
        print(f"- {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
