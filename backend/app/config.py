"""
Central configuration, loaded from environment variables / .env file.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> repo root is two levels up from this file's parent (backend/)
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# Load .env from repo root if present, otherwise fall back to defaults silently.
load_dotenv(REPO_ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


PORT = _int("PORT", 8000)
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-only-insecure-secret-change-me")
SESSION_MAX_AGE_HOURS = _int("SESSION_MAX_AGE_HOURS", 12)
# Mark the session cookie Secure (HTTPS-only). Leave false for local http://
# development; set SESSION_SECURE_COOKIES=true in production once the app is
# served over HTTPS (e.g. behind Railway's / your reverse proxy's TLS).
SESSION_SECURE_COOKIES = os.getenv("SESSION_SECURE_COOKIES", "false").strip().lower() == "true"

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
if not DATA_DIR.is_absolute():
    DATA_DIR = (REPO_ROOT / DATA_DIR).resolve()
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"

SLA_HOURS = {
    "Critical": _int("SLA_HOURS_CRITICAL", 4),
    "High": _int("SLA_HOURS_HIGH", 24),
    "Medium": _int("SLA_HOURS_MEDIUM", 72),
    "Low": _int("SLA_HOURS_LOW", 120),
}

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 15)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_UPLOAD_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".pdf", ".txt", ".log", ".csv",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip",
}

SEED_ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME", "admin")
SEED_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "admin123")
SEED_ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
SEED_ADMIN_FULLNAME = os.getenv("SEED_ADMIN_FULLNAME", "IT Administrator")

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

# --- Microsoft 365 / Entra ID (Azure AD) single sign-on -------------------
# Entirely optional -- unset, the app behaves exactly as before (local
# username/password only). Set all three of MS_CLIENT_ID / MS_CLIENT_SECRET /
# MS_TENANT_ID to turn on the "Sign in with Microsoft" button. See README for
# the Azure App Registration steps. Restricted to a single tenant (your own
# organization's directory) by design -- never the shared "common" endpoint.
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "").strip()
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "").strip()
MS_TENANT_ID = os.getenv("MS_TENANT_ID", "").strip()
# Full callback URL as registered in Azure, e.g. https://support.example.com/api/auth/sso/callback
MS_REDIRECT_URI = os.getenv("MS_REDIRECT_URI", "").strip()

SSO_ENABLED = bool(MS_CLIENT_ID and MS_CLIENT_SECRET and MS_TENANT_ID and MS_REDIRECT_URI)

# --- Outbound email (SMTP) --------------------------------------------------
# Entirely optional -- unset, the app behaves exactly as before (in-app
# notification bell only, nothing sent). Set SMTP_HOST and SMTP_FROM_EMAIL to
# turn it on. See README for setup notes.
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _int("SMTP_PORT", 587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"  # STARTTLS; ignored on port 465 (implicit SSL)
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "IT Support & Maintenance Tracker").strip()
EMAIL_ENABLED = bool(SMTP_HOST and SMTP_FROM_EMAIL)

# Public base URL used to build ticket links inside emails. Set this to your
# real domain/subdomain once deployed -- the localhost default is fine for
# local dev but wrong for links that end up in someone's inbox.
APP_BASE_URL = os.getenv("APP_BASE_URL", f"http://localhost:{PORT}").rstrip("/")

# --- Inbound email / reply-by-email (SendGrid Inbound Parse) ---------------
# Entirely optional -- unset, replying to a notification email just goes
# nowhere useful (normal email, no special handling). Requires SendGrid's
# Inbound Parse configured on a subdomain you control (see README): an MX
# record for that subdomain points at SendGrid, which POSTs each inbound
# message to INBOUND_WEBHOOK path below.
#
# Reply-to addresses look like: ticket-it-0001@<INBOUND_EMAIL_DOMAIN>
INBOUND_EMAIL_DOMAIN = os.getenv("INBOUND_EMAIL_DOMAIN", "").strip()
# Secret path segment for the inbound webhook URL -- SendGrid's Inbound Parse
# doesn't sign its requests, so this acts as a lightweight shared secret.
# Configure this exact URL in SendGrid: https://<your-app>/api/email/inbound/<this>
INBOUND_WEBHOOK_TOKEN = os.getenv("INBOUND_WEBHOOK_TOKEN", "").strip()
REPLY_BY_EMAIL_ENABLED = bool(EMAIL_ENABLED and INBOUND_EMAIL_DOMAIN and INBOUND_WEBHOOK_TOKEN)

CATEGORIES = ["Hardware", "Network", "Software/License", "Server/Infra", "Access/Account", "Email", "Other"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "In Progress", "Waiting on User", "Waiting on Vendor", "Resolved", "Closed"]
OPEN_STATUSES = ["Open", "In Progress", "Waiting on User", "Waiting on Vendor"]
