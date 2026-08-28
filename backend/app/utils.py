"""
Small shared helpers: ticket numbering, SLA due-date calculation,
audit logging, in-app notifications, and the notification "channel"
extension point where SMTP could be wired in later.
"""
import sqlite3
from datetime import datetime, timezone


def next_ticket_number(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT ticket_number FROM tickets ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        n = 1
    else:
        try:
            n = int(row["ticket_number"].split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"] + 1
    return f"IT-{n:04d}"


def get_sla_hours(conn: sqlite3.Connection, priority: str) -> int:
    row = conn.execute("SELECT hours FROM sla_rules WHERE priority = ?", (priority,)).fetchone()
    return row["hours"] if row else 72


def compute_sla_due(conn: sqlite3.Connection, priority: str, created_at_expr: str = "datetime('now')") -> str:
    hours = get_sla_hours(conn, priority)
    return conn.execute(
        f"SELECT datetime({created_at_expr}, ? ) AS due", (f"+{hours} hours",)
    ).fetchone()["due"]


def log_audit(conn: sqlite3.Connection, ticket_id: int, field: str, old_value, new_value, changed_by: str):
    conn.execute(
        """INSERT INTO audit_log (ticket_id, field, old_value, new_value, changed_by)
           VALUES (?, ?, ?, ?, ?)""",
        (ticket_id, field, "" if old_value is None else str(old_value),
         "" if new_value is None else str(new_value), changed_by),
    )


def notify_user(conn: sqlite3.Connection, user_id: int, ntype: str, message: str, ticket_id: int | None = None):
    """
    Create an in-app notification for a user (shown in the notification bell,
    polled by the frontend every 30-60s).

    --- SMTP EXTENSION POINT -------------------------------------------------
    v1 ships with in-app notifications only, by design (no external SMTP
    dependency). To add email notifications later, call an email-sending
    function from here, e.g.:

        from . import mailer
        mailer.send_email(to=user_email, subject=..., body=message)

    and implement `mailer.send_email()` using smtplib + settings pulled from
    the environment (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM).
    Everything else in this codebase already calls notify_user() at the right
    points (new comment, assignment, status change) so no other code needs to
    change.
    ---------------------------------------------------------------------------
    """
    if not user_id:
        return
    conn.execute(
        """INSERT INTO notifications (user_id, type, message, ticket_id)
           VALUES (?, ?, ?, ?)""",
        (user_id, ntype, message, ticket_id),
    )


def sanitize_text(value: str | None) -> str:
    """Escape HTML so free-text fields can never inject markup when rendered.
    The frontend renders comment/description bodies as plain text (React
    escapes by default), but we defense-in-depth escape on write too, and
    always store the raw escaped form for anything echoed into HTML contexts."""
    if value is None:
        return ""
    return value.strip()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]


def serialize_ticket_row(row: sqlite3.Row) -> dict:
    """Turn a `tickets` row into a dict with a computed `sla_overdue` flag.
    Shared by the tickets and dashboard routers so the flag is never
    silently missing from a ticket payload."""
    d = dict(row)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_closed = d.get("status") in ("Resolved", "Closed")
    overdue = False
    if d.get("sla_due_at") and not is_closed:
        try:
            due = datetime.fromisoformat(d["sla_due_at"])
            overdue = now > due
        except ValueError:
            overdue = False
    d["sla_overdue"] = overdue
    return d


def serialize_tickets(rows) -> list:
    return [serialize_ticket_row(r) for r in rows]
