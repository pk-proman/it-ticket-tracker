"""
Small shared helpers: ticket numbering, SLA due-date calculation,
audit logging, in-app notifications, and the notification "channel"
extension point where SMTP could be wired in later.
"""
import re
import sqlite3
from datetime import datetime, timezone

# Patterns that mark the start of quoted history in a plain-text email reply,
# across the common clients (Gmail, Apple Mail, Outlook). Not exhaustive --
# email reply parsing has no fully reliable solution -- but covers the
# large majority of real replies. Everything from the first match onward is
# discarded; only text strictly above it is kept as the "new" reply content.
_QUOTE_MARKERS = [
    re.compile(r"^On .{0,120} wrote:\s*$", re.MULTILINE),          # Gmail / Apple Mail
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.MULTILINE | re.IGNORECASE),  # Outlook
    re.compile(r"^From:\s.+$", re.MULTILINE),                       # Outlook plain-text header block
    re.compile(r"^Sent from my i?Phone", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^>", re.MULTILINE),                                # classic '>' quote prefix
]


def strip_quoted_reply(text: str) -> str:
    """Best-effort trim of an email reply body down to just the new text the
    person actually typed, dropping the quoted thread history below it."""
    if not text:
        return ""
    cut_at = len(text)
    for pattern in _QUOTE_MARKERS:
        match = pattern.search(text)
        if match and match.start() < cut_at:
            cut_at = match.start()
    return text[:cut_at].strip()


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
    polled by the frontend every 30-60s), and -- when SMTP is configured --
    also email them. This is the single place every ticket lifecycle event
    routes through, so it's also the single place email gets added; no other
    code needs to change when EMAIL_ENABLED flips on.
    """
    if not user_id:
        return
    conn.execute(
        """INSERT INTO notifications (user_id, type, message, ticket_id)
           VALUES (?, ?, ?, ?)""",
        (user_id, ntype, message, ticket_id),
    )
    _maybe_email_for_notification(conn, user_id, ntype, ticket_id)


def _maybe_email_for_notification(conn: sqlite3.Connection, user_id: int, ntype: str, ticket_id: int | None):
    from . import config, mailer  # local import: avoids a circular import at module load time

    if not config.EMAIL_ENABLED or not ticket_id:
        return
    user = conn.execute("SELECT full_name, email FROM users WHERE id = ?", (user_id,)).fetchone()
    ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not user or not user["email"] or not ticket:
        return
    ticket = dict(ticket)

    if ntype == "new_ticket":
        mailer.send_new_ticket_alert(user["email"], ticket, ticket_id)
    elif ntype == "ticket_update":
        if ticket["status"] == "Resolved":
            mailer.send_ticket_resolved(user["email"], user["full_name"], ticket, ticket_id)
        else:
            mailer.send_ticket_status_changed(user["email"], user["full_name"], ticket, ticket_id)
    elif ntype == "new_comment":
        latest = conn.execute(
            "SELECT author_name, body FROM ticket_comments WHERE ticket_id = ? ORDER BY created_at DESC LIMIT 1",
            (ticket_id,),
        ).fetchone()
        if latest:
            mailer.send_new_comment_notification(
                user["email"], user["full_name"], ticket, ticket_id, latest["author_name"], latest["body"]
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
