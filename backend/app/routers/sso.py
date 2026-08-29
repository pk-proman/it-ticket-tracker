"""
Microsoft 365 / Entra ID single sign-on.

Entirely optional -- these routes only do anything useful once SSO_ENABLED
is true (see config.py / README.md for the Azure App Registration steps).
Runs alongside local username/password login, never replacing it.

Provisioning policy: the first time someone signs in via Microsoft with an
email that doesn't match an existing local account, we auto-create them as
a plain Requester. Nothing here can create an Agent or Admin account -- an
existing admin has to promote someone under Users after the fact.
"""
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import config
from ..database import get_db
from ..oauth import oauth
from ..security import hash_password

router = APIRouter(prefix="/api/auth/sso", tags=["sso"])


@router.get("/status")
def sso_status():
    """Public -- lets the login page decide whether to show the SSO button."""
    return {"enabled": config.SSO_ENABLED}


def _require_sso_enabled():
    if not config.SSO_ENABLED:
        raise HTTPException(status_code=404, detail="Single sign-on is not configured")


@router.get("/login")
async def sso_login(request: Request, _enabled=Depends(_require_sso_enabled)):
    return await oauth.microsoft.authorize_redirect(request, config.MS_REDIRECT_URI)


def _unique_username(conn: sqlite3.Connection, email: str) -> str:
    base = email.lower()
    candidate = base
    n = 2
    while conn.execute("SELECT 1 FROM users WHERE username = ?", (candidate,)).fetchone():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


@router.get("/callback")
async def sso_callback(request: Request, conn: sqlite3.Connection = Depends(get_db), _enabled=Depends(_require_sso_enabled)):
    try:
        token = await oauth.microsoft.authorize_access_token(request)
    except Exception as exc:  # noqa: BLE001 -- surfaced as a plain-text redirect message below
        return RedirectResponse(url=f"/login?sso_error={_safe(str(exc))}")

    userinfo = token.get("userinfo") or {}
    subject = userinfo.get("oid") or userinfo.get("sub")
    email = (userinfo.get("email") or userinfo.get("preferred_username") or "").strip().lower()
    name = userinfo.get("name") or email

    if not subject or not email:
        return RedirectResponse(url="/login?sso_error=Microsoft+did+not+return+an+email+address")

    user = conn.execute("SELECT * FROM users WHERE sso_subject = ?", (subject,)).fetchone()

    if not user:
        user = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
        if user:
            # Existing local account with a matching email -- link it for next time.
            conn.execute(
                "UPDATE users SET sso_subject = ?, auth_provider = 'microsoft' WHERE id = ?",
                (subject, user["id"]),
            )
            user = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()

    if not user:
        # First time this person has ever shown up -- auto-provision as Requester.
        # password_hash is set to an unguessable, never-communicated value so
        # local password login stays unusable for this account.
        username = _unique_username(conn, email)
        conn.execute(
            """INSERT INTO users (username, password_hash, full_name, email, role, is_admin, auth_provider, sso_subject)
               VALUES (?, ?, ?, ?, 'requester', 0, 'microsoft', ?)""",
            (username, hash_password(secrets.token_hex(32)), name, email, subject),
        )
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not user["active"]:
        return RedirectResponse(url="/login?sso_error=This+account+has+been+disabled")

    request.session["user_id"] = user["id"]
    return RedirectResponse(url="/")


def _safe(message: str) -> str:
    # Keep redirect-query error text short and free of characters that would
    # break the URL; the frontend just displays it as-is.
    return "".join(c for c in message if c.isalnum() or c in " .,'-")[:120].replace(" ", "+")
