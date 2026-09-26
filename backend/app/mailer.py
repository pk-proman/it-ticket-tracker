"""
Outbound email -- via Microsoft Graph or plain SMTP -- plus the ticket-
lifecycle email templates that use it.

Entirely optional -- config.EMAIL_ENABLED is false until either Graph
(MS_CLIENT_ID/MS_CLIENT_SECRET/MS_TENANT_ID/MS_MAIL_SENDER) or SMTP
(SMTP_HOST/SMTP_FROM_EMAIL) is configured. Every function here degrades to
a harmless no-op (just a log line) when disabled, so callers never need to
check EMAIL_ENABLED themselves.

Graph is used in preference to SMTP when both are configured -- this exists
specifically for tenants that keep legacy SMTP AUTH disabled (Microsoft's
modern default) but still want mail sent from a real M365 mailbox, via
OAuth2 client-credentials instead of a username/password.

Reply-by-email: when config.REPLY_BY_EMAIL_ENABLED is on, every ticket email
sets Reply-To to a per-ticket address (ticket-it-0001@<domain>). Replying in
any normal email client lands on our SendGrid Inbound Parse webhook (see
routers/email_inbound.py), which turns it into a comment on that ticket.
"""
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage

import httpx

from . import config

logger = logging.getLogger("mailer")

_GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"

# In-memory cache for the Graph access token -- client-credentials tokens are
# typically valid ~60-90 min; no need to fetch a fresh one per email.
_graph_token_cache: dict = {"token": None, "expires_at": 0}


def _get_graph_token() -> str:
    now = time.time()
    if _graph_token_cache["token"] and _graph_token_cache["expires_at"] > now + 60:
        return _graph_token_cache["token"]

    resp = httpx.post(
        _GRAPH_TOKEN_URL.format(tenant=config.MS_TENANT_ID),
        data={
            "grant_type": "client_credentials",
            "client_id": config.MS_CLIENT_ID,
            "client_secret": config.MS_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _graph_token_cache["token"] = data["access_token"]
    _graph_token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return _graph_token_cache["token"]


def _send_via_graph(to: str, subject: str, text_body: str, html_body: str | None, reply_to: str | None) -> bool:
    token = _get_graph_token()
    body = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML" if html_body else "Text",
                "content": html_body or text_body,
            },
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": False,
    }
    if reply_to:
        body["message"]["replyTo"] = [{"emailAddress": {"address": reply_to}}]

    resp = httpx.post(
        _GRAPH_SEND_URL.format(sender=config.MS_MAIL_SENDER),
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    return True


def _send_via_smtp(to: str, subject: str, text_body: str, html_body: str | None, reply_to: str | None) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{config.SMTP_FROM_NAME} <{config.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if config.SMTP_PORT == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=15) as server:
            if config.SMTP_USERNAME:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            if config.SMTP_USE_TLS:
                server.starttls(context=ssl.create_default_context())
            if config.SMTP_USERNAME:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
    return True


def send_email(to: str, subject: str, text_body: str, html_body: str | None = None, reply_to: str | None = None) -> bool:
    """Send one email. Returns True on success (or when disabled, since
    there's nothing to fail), False if a real send attempt failed."""
    if not to:
        return False
    if not config.EMAIL_ENABLED:
        logger.info("EMAIL (not configured, not sent) to=%s subject=%r", to, subject)
        return True

    try:
        if config.GRAPH_MAIL_ENABLED:
            return _send_via_graph(to, subject, text_body, html_body, reply_to)
        return _send_via_smtp(to, subject, text_body, html_body, reply_to)
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def ticket_reply_address(ticket_number: str) -> str | None:
    """The per-ticket inbound address replies should go to, or None if
    reply-by-email isn't configured."""
    if not config.REPLY_BY_EMAIL_ENABLED:
        return None
    slug = ticket_number.strip().lower().replace(" ", "")
    return f"ticket-{slug}@{config.INBOUND_EMAIL_DOMAIN}"


def ticket_url(ticket_number_or_id) -> str:
    return f"{config.APP_BASE_URL}/tickets/{ticket_number_or_id}"


def _reply_footer(ticket_number: str) -> str:
    if config.REPLY_BY_EMAIL_ENABLED:
        return "\n\nYou can reply directly to this email to add a comment to the ticket."
    return ""


# Sign-off appended to every outbound ticket email. Change this one constant
# to update it everywhere at once.
_SIGNATURE = "\n\nRegards,\nProman IT / ERP Support"


# ---------------------------------------------------------------------------
# Ticket lifecycle templates
# ---------------------------------------------------------------------------

def send_ticket_created_confirmation(ticket: dict, ticket_id: int):
    """To the requester (whoever's email is on the ticket, account or not),
    confirming we received it."""
    reply_to = ticket_reply_address(ticket["ticket_number"])
    subject = f"[{ticket['ticket_number']}] We received your request: {ticket['title']}"
    body = (
        f"Hi {ticket['requester_name']},\n\n"
        f"We've received your IT support request and logged it as {ticket['ticket_number']}.\n\n"
        f"  Title: {ticket['title']}\n"
        f"  Category: {ticket['category']}\n"
        f"  Priority: {ticket['priority']}\n\n"
        f"Track it here: {ticket_url(ticket_id)}"
        f"{_reply_footer(ticket['ticket_number'])}"
        f"{_SIGNATURE}"
    )
    send_email(ticket["requester_email"], subject, body, reply_to=reply_to)


def send_new_ticket_alert(agent_email: str, ticket: dict, ticket_id: int):
    """To each agent, when a new ticket comes in."""
    subject = f"[{ticket['ticket_number']}] New ticket: {ticket['title']}"
    body = (
        f"A new ticket was raised by {ticket['requester_name']}.\n\n"
        f"  Category: {ticket['category']}\n"
        f"  Priority: {ticket['priority']}\n\n"
        f"View it here: {ticket_url(ticket_id)}"
        f"{_SIGNATURE}"
    )
    send_email(agent_email, subject, body)


def send_ticket_resolved(to_email: str, to_name: str, ticket: dict, ticket_id: int):
    """Special resolution email -- explicitly invites a reply for feedback
    ('did this actually fix it?') when reply-by-email is configured."""
    reply_to = ticket_reply_address(ticket["ticket_number"])
    subject = f"[{ticket['ticket_number']}] Resolved: {ticket['title']}"
    if config.REPLY_BY_EMAIL_ENABLED:
        cta = (
            "If this fixed things, no action needed -- feel free to close it from the ticket page.\n"
            "If it's NOT actually resolved, just reply to this email and we'll reopen it and pick it back up."
        )
    else:
        cta = "If this didn't actually fix things, log in and reopen it, or add a comment."
    body = (
        f"Hi {to_name},\n\n"
        f"Ticket {ticket['ticket_number']} ({ticket['title']}) has been marked Resolved.\n\n"
        f"{cta}\n\n"
        f"View it here: {ticket_url(ticket_id)}"
        f"{_SIGNATURE}"
    )
    send_email(to_email, subject, body, reply_to=reply_to)


def send_ticket_status_changed(to_email: str, to_name: str, ticket: dict, ticket_id: int):
    """Generic progress-stage email for any other status transition."""
    reply_to = ticket_reply_address(ticket["ticket_number"])
    subject = f"[{ticket['ticket_number']}] Status update: {ticket['status']}"
    body = (
        f"Hi {to_name},\n\n"
        f"Ticket {ticket['ticket_number']} ({ticket['title']}) is now: {ticket['status']}.\n\n"
        f"View it here: {ticket_url(ticket_id)}"
        f"{_reply_footer(ticket['ticket_number'])}"
        f"{_SIGNATURE}"
    )
    send_email(to_email, subject, body, reply_to=reply_to)


def send_new_comment_notification(to_email: str, to_name: str, ticket: dict, ticket_id: int, author_name: str, comment_body: str):
    reply_to = ticket_reply_address(ticket["ticket_number"])
    subject = f"[{ticket['ticket_number']}] New comment from {author_name}"
    snippet = comment_body if len(comment_body) <= 500 else comment_body[:500] + "…"
    body = (
        f"Hi {to_name},\n\n"
        f"{author_name} commented on ticket {ticket['ticket_number']} ({ticket['title']}):\n\n"
        f"  {snippet}\n\n"
        f"View it here: {ticket_url(ticket_id)}"
        f"{_reply_footer(ticket['ticket_number'])}"
        f"{_SIGNATURE}"
    )
    send_email(to_email, subject, body, reply_to=reply_to)


# ---------------------------------------------------------------------------
# Category-based approval workflow (see routers/approvals.py)
# ---------------------------------------------------------------------------

def send_approval_request(approver_email: str, approver_name: str, ticket: dict, ticket_id: int, token: str):
    """To the designated approver for this ticket's category -- the whole
    point of the exercise is that they can act on this without logging in."""
    subject = f"[{ticket['ticket_number']}] Approval needed: {ticket['title']}"
    link = f"{config.APP_BASE_URL}/api/approvals/{token}"
    body = (
        f"Hi {approver_name},\n\n"
        f"A new {ticket['category']} ticket needs your approval before it can be assigned.\n\n"
        f"  Ticket: {ticket['ticket_number']} -- {ticket['title']}\n"
        f"  Requested by: {ticket['requester_name']} ({ticket['requester_email']})\n"
        f"  Priority: {ticket['priority']}\n\n"
        f"Review and approve or reject it here (no login needed):\n{link}"
        f"{_SIGNATURE}"
    )
    send_email(approver_email, subject, body)


def send_ticket_approved(ticket: dict, ticket_id: int, assignee_name: str):
    """To the requester, once their ticket clears the approval step."""
    subject = f"[{ticket['ticket_number']}] Approved: {ticket['title']}"
    body = (
        f"Hi {ticket['requester_name']},\n\n"
        f"Your ticket {ticket['ticket_number']} ({ticket['title']}) has been approved "
        f"and assigned to {assignee_name}.\n\n"
        f"Track it here: {ticket_url(ticket_id)}"
        f"{_SIGNATURE}"
    )
    send_email(ticket["requester_email"], subject, body)


def send_ticket_rejected(ticket: dict, ticket_id: int):
    """To the requester, if the approver declines the request."""
    subject = f"[{ticket['ticket_number']}] Not approved: {ticket['title']}"
    body = (
        f"Hi {ticket['requester_name']},\n\n"
        f"Your ticket {ticket['ticket_number']} ({ticket['title']}) was not approved.\n\n"
        f"If you have questions about this, please reach out to IT directly.\n\n"
        f"View it here: {ticket_url(ticket_id)}"
        f"{_SIGNATURE}"
    )
    send_email(ticket["requester_email"], subject, body)
