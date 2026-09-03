"""
Reply-by-email: SendGrid Inbound Parse webhook.

When reply-by-email is configured (see config.REPLY_BY_EMAIL_ENABLED /
README), every ticket notification email sets Reply-To to a per-ticket
address like ticket-it-0001@<your inbound domain>. SendGrid receives mail
sent to that domain and POSTs it here as multipart/form-data. We turn it
into a ticket comment from whoever sent it, if we can identify them.

Entirely optional and inert until INBOUND_EMAIL_DOMAIN + INBOUND_WEBHOOK_TOKEN
are both set -- every request 404s until then.
"""
import hmac
import logging
import re
from email.utils import parseaddr

from fastapi import APIRouter, HTTPException, Request

from .. import config
from ..database import db_session
from ..utils import log_audit, strip_quoted_reply
from .tickets import add_comment_internal

router = APIRouter(prefix="/api/email/inbound", tags=["email"])
logger = logging.getLogger("email_inbound")

_TICKET_ADDR_RE = re.compile(r"ticket-(it-\d+)@", re.IGNORECASE)


def _extract_ticket_number(to_field: str) -> str | None:
    """SendGrid's `to` can contain multiple/mixed-case addresses; pull the
    first one matching our ticket-reply convention."""
    match = _TICKET_ADDR_RE.search(to_field or "")
    if not match:
        return None
    return match.group(1).upper()  # normalize casing, e.g. "it-0001" -> "IT-0001"


@router.post("/{token}")
async def inbound_email(token: str, request: Request):
    if not config.REPLY_BY_EMAIL_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    if not hmac.compare_digest(token, config.INBOUND_WEBHOOK_TOKEN):
        raise HTTPException(status_code=404, detail="Not found")

    form = await request.form()
    to_field = str(form.get("to", ""))
    from_field = str(form.get("from", ""))
    text_body = str(form.get("text", "") or "")

    ticket_number = _extract_ticket_number(to_field)
    sender_name, sender_email = parseaddr(from_field)
    sender_email = (sender_email or "").strip().lower()

    if not ticket_number or not sender_email:
        logger.info("Inbound email ignored: could not parse ticket/sender (to=%r from=%r)", to_field, from_field)
        return {"ok": True}  # 200 so SendGrid doesn't retry; nothing we can do with this one

    with db_session() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE ticket_number = ?", (ticket_number,)).fetchone()
        if not ticket:
            logger.info("Inbound email ignored: no ticket %s", ticket_number)
            return {"ok": True}

        author = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (sender_email,)).fetchone()
        is_agent_author = bool(author and author["role"] == "agent")

        if author:
            author_id, author_name = author["id"], author["full_name"]
        elif sender_email == (ticket["requester_email"] or "").lower():
            # Walk-up/phone ticket -- requester has no account, but the reply
            # came from the exact email address the ticket was raised under.
            author_id, author_name = None, ticket["requester_name"]
        else:
            logger.info(
                "Inbound email ignored: sender %s is not the requester or a known user on %s",
                sender_email, ticket_number,
            )
            return {"ok": True}

        body = strip_quoted_reply(text_body)
        if not body:
            logger.info("Inbound email ignored: empty after stripping quoted text (%s)", ticket_number)
            return {"ok": True}

        add_comment_internal(conn, ticket, author_id, author_name, body, is_internal=False, is_agent_author=is_agent_author)

        # Replying to a resolved/closed ticket as the requester reopens it --
        # this is the "actually, it's not fixed" signal the resolution email
        # explicitly invites.
        if not is_agent_author and ticket["status"] in ("Resolved", "Closed"):
            conn.execute(
                "UPDATE tickets SET status = 'Open', updated_at = datetime('now') WHERE id = ?",
                (ticket["id"],),
            )
            log_audit(conn, ticket["id"], "status", ticket["status"], "Open", f"{author_name} (via email reply)")

    return {"ok": True}
