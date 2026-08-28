"""
SQLite connection management + schema creation.

We use the stdlib sqlite3 module directly (no ORM) with parameterized
queries everywhere to keep the stack simple and avoid SQL injection.
"""
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('agent', 'requester')),
    is_admin INTEGER NOT NULL DEFAULT 0,
    department TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS sla_rules (
    priority TEXT PRIMARY KEY,
    hours INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open',
    requester_id INTEGER REFERENCES users(id),
    requester_name TEXT NOT NULL,
    requester_email TEXT NOT NULL,
    requester_department TEXT DEFAULT '',
    assignee_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    closed_at TEXT,
    sla_due_at TEXT
);

CREATE TABLE IF NOT EXISTS ticket_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES users(id),
    author_name TEXT NOT NULL,
    body TEXT NOT NULL,
    is_internal INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ticket_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    content_type TEXT DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    old_value TEXT DEFAULT '',
    new_value TEXT DEFAULT '',
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_tag TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    assigned_to TEXT DEFAULT '',
    location TEXT DEFAULT '',
    purchase_date TEXT,
    warranty_expiry TEXT,
    status TEXT NOT NULL DEFAULT 'In Use',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ticket_assets (
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    PRIMARY KEY (ticket_id, asset_id)
);

CREATE TABLE IF NOT EXISTS licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    software_name TEXT NOT NULL,
    vendor TEXT DEFAULT '',
    license_key TEXT DEFAULT '',
    total_seats INTEGER NOT NULL DEFAULT 1,
    seats_in_use INTEGER NOT NULL DEFAULT 0,
    renewal_date TEXT,
    cost REAL DEFAULT 0,
    owner TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ticket_licenses (
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    license_id INTEGER NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
    PRIMARY KEY (ticket_id, license_id)
);

CREATE TABLE IF NOT EXISTS kb_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT DEFAULT 'Other',
    body TEXT NOT NULL,
    tags TEXT DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    ticket_id INTEGER REFERENCES tickets(id) ON DELETE CASCADE,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_assignee ON tickets(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tickets_requester ON tickets(requester_id);
CREATE INDEX IF NOT EXISTS idx_comments_ticket ON ticket_comments(ticket_id);
CREATE INDEX IF NOT EXISTS idx_attachments_ticket ON ticket_attachments(ticket_id);
CREATE INDEX IF NOT EXISTS idx_audit_ticket ON audit_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
"""


def get_connection() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_session():
    """Yield a connection for a single request; commits on success, rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """FastAPI dependency."""
    with db_session() as conn:
        yield conn
