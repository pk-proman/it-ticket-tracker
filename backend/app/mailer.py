"""
Outbound email (SMTP) plus the ticket-lifecycle email templates that use it.

Entirely optional -- config.EMAIL_ENABLED is false until SMTP_HOST and
SMTP_FROM_EMAIL are set. Every function here degrades to a harmless no-op
(just a log line) when disabled, so callers never need to check
EMAIL_ENABLED themselves.

Reply-by-email: when config.REPLY_BY_EMAIL_ENABLED is on, every ticket email
sets Reply-To to a per-ticket address (ticket-it-0001@<domain>). Replying in
any normal email client lands on our SendGrid Inbound Parse webhook (see
routers/email_inbound.py), which turns it into a comment on that ticket.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from . import config

logger = logging.getLogger("mailer")


def send_email(to: str, subject: str, text_body: str, html_body: str | None = None, reply_to: str | None = None) -> bool:
    """Send one email. Returns True on success (or when disabled, since
    there's nothing to fail), False if a real send attempt failed."""
    if not to:
        return False
    if not config.EMAIL_ENABLED:
        logger.info("EMAIL (SMTP not configured, not sent) to=%s subject=%r", to, subject)
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{config.SMTP_FROM_NAME} <{config.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
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
    )
    send_email(to_email, subject, body, reply_to=reply_to)
