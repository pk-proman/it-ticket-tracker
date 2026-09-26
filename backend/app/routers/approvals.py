"""
Category-based ticket approval workflow (e.g. "ERPNext" tickets need
Head-Digital Transformation sign-off before they're assigned).

Token-secured, not login-secured -- the approver clicks a link straight
from an email, no account/login required. Deliberately GET-then-POST rather
than a one-click GET: many corporate mail systems (Outlook Safe Links,
security scanners) pre-fetch every URL in an email to check it for malware,
which would silently approve things before a human ever saw the message if
GET alone did the approving. GET only ever shows a confirmation page; the
actual decision requires an explicit form POST (a real click on a button),
which link-prefetchers don't do.
"""
import secrets
import sqlite3

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse

from .. import config, mailer
from ..database import get_db
from ..utils import log_audit

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def create_approval(conn: sqlite3.Connection, ticket_id: int, approver_id: int, default_assignee_id: int | None) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        """INSERT INTO ticket_approvals (ticket_id, approver_id, default_assignee_id, token)
           VALUES (?, ?, ?, ?)""",
        (ticket_id, approver_id, default_assignee_id, token),
    )
    return token


def approval_url(token: str) -> str:
    return f"{config.APP_BASE_URL}/api/approvals/{token}"


def _page(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; background: #f8fafc; color: #1e293b;
          display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; max-width: 480px; width: 90%; }}
  h1 {{ font-size: 18px; margin: 0 0 16px; }}
  p {{ font-size: 14px; line-height: 1.6; color: #475569; }}
  button {{ font-size: 14px; font-weight: 600; padding: 10px 20px; border-radius: 6px; border: none; cursor: pointer; margin-right: 8px; }}
  .approve {{ background: #2748db; color: #fff; }}
  .reject {{ background: #fff; color: #dc2626; border: 1px solid #dc2626; }}
</style></head>
<body><div class="card"><h1>{title}</h1>{body_html}</div></body></html>"""


@router.get("/{token}", response_class=HTMLResponse)
def approval_page(token: str, conn: sqlite3.Connection = Depends(get_db)):
    approval = conn.execute("SELECT * FROM ticket_approvals WHERE token = ?", (token,)).fetchone()
    if not approval:
        return HTMLResponse(_page("Link not found", "<p>This approval link is invalid.</p>"), status_code=404)

    ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (approval["ticket_id"],)).fetchone()
    if not ticket:
        return HTMLResponse(_page("Ticket not found", "<p>The related ticket no longer exists.</p>"), status_code=404)

    if approval["status"] != "pending":
        verb = "approved" if approval["status"] == "approved" else "rejected"
        return HTMLResponse(_page("Already decided", f"<p>This request was already <strong>{verb}</strong> on {approval['decided_at']}.</p>"))

    assignee = None
    if approval["default_assignee_id"]:
        assignee = conn.execute("SELECT full_name FROM users WHERE id = ?", (approval["default_assignee_id"],)).fetchone()

    body = f"""
      <p><strong>{ticket['ticket_number']}</strong>: {ticket['title']}</p>
      <p>Requested by {ticket['requester_name']} ({ticket['requester_email']})<br>
         Category: {ticket['category']} &middot; Priority: {ticket['priority']}</p>
      <p>{ticket['description'] or ''}</p>
      <p>If approved, this will be assigned to <strong>{assignee['full_name'] if assignee else 'the default assignee'}</strong>.</p>
      <form method="post" action="/api/approvals/{token}/decide">
        <button class="approve" name="decision" value="approved" type="submit">Approve</button>
        <button class="reject" name="decision" value="rejected" type="submit">Reject</button>
      </form>
    """
    return HTMLResponse(_page(f"Approve {ticket['ticket_number']}?", body))


@router.post("/{token}/decide", response_class=HTMLResponse)
def decide_approval(token: str, decision: str = Form(...), conn: sqlite3.Connection = Depends(get_db)):
    if decision not in ("approved", "rejected"):
        return HTMLResponse(_page("Invalid request", "<p>Unrecognized decision.</p>"), status_code=400)

    approval = conn.execute("SELECT * FROM ticket_approvals WHERE token = ?", (token,)).fetchone()
    if not approval:
        return HTMLResponse(_page("Link not found", "<p>This approval link is invalid.</p>"), status_code=404)
    if approval["status"] != "pending":
        return HTMLResponse(_page("Already decided", "<p>This request was already decided.</p>"))

    ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (approval["ticket_id"],)).fetchone()
    approver = conn.execute("SELECT full_name FROM users WHERE id = ?", (approval["approver_id"],)).fetchone()
    approver_name = approver["full_name"] if approver else "Approver"

    conn.execute(
        "UPDATE ticket_approvals SET status = ?, decided_at = datetime('now') WHERE id = ?",
        (decision, approval["id"]),
    )

    if decision == "approved":
        assignee_id = approval["default_assignee_id"]
        assignee = conn.execute("SELECT full_name FROM users WHERE id = ?", (assignee_id,)).fetchone() if assignee_id else None
        conn.execute(
            "UPDATE tickets SET assignee_id = ?, updated_at = datetime('now') WHERE id = ?",
            (assignee_id, ticket["id"]),
        )
        log_audit(
            conn, ticket["id"], "assignee", "Unassigned (pending approval)",
            assignee["full_name"] if assignee else "Unassigned", f"{approver_name} (approved)",
        )
        _notify_requester(conn, ticket, f"Your ticket {ticket['ticket_number']} was approved and assigned.")
        if config.EMAIL_ENABLED:
            mailer.send_ticket_approved(dict(ticket), ticket["id"], assignee["full_name"] if assignee else "an agent")
        message = f"<p>Approved. {ticket['ticket_number']} has been assigned{' to ' + assignee['full_name'] if assignee else ''}.</p>"
    else:
        log_audit(conn, ticket["id"], "status", ticket["status"], ticket["status"], f"{approver_name} (rejected approval request)")
        _notify_requester(conn, ticket, f"Your ticket {ticket['ticket_number']} was not approved.")
        if config.EMAIL_ENABLED:
            mailer.send_ticket_rejected(dict(ticket), ticket["id"])
        message = f"<p>Rejected. {ticket['ticket_number']} was not approved; the requester has been notified.</p>"

    return HTMLResponse(_page("Done", message))


def _notify_requester(conn: sqlite3.Connection, ticket, message: str):
    """In-app bell notification, only when the requester has an account --
    email (handled separately, above) always goes to requester_email
    regardless, matching how ticket-creation confirmations already work."""
    if ticket["requester_id"]:
        conn.execute(
            "INSERT INTO notifications (user_id, type, message, ticket_id) VALUES (?, ?, ?, ?)",
            (ticket["requester_id"], "ticket_update", message, ticket["id"]),
        )
