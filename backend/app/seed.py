"""
Seeds the database on first run: categories, default SLA rules, an initial
admin/agent account, and a few example records so the UI isn't empty.

Safe to call on every startup -- everything here is idempotent (checks
before inserting).
"""
from . import config
from .database import get_connection
from .security import hash_password


def seed_categories(conn):
    for name in config.CATEGORIES:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))


def seed_sla_rules(conn):
    for priority, hours in config.SLA_HOURS.items():
        conn.execute(
            "INSERT OR IGNORE INTO sla_rules (priority, hours) VALUES (?, ?)",
            (priority, hours),
        )


def seed_admin(conn):
    existing = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
    if existing:
        return
    conn.execute(
        """INSERT INTO users (username, password_hash, full_name, email, role, is_admin, department)
           VALUES (?, ?, ?, ?, 'agent', 1, 'IT')""",
        (
            config.SEED_ADMIN_USERNAME,
            hash_password(config.SEED_ADMIN_PASSWORD),
            config.SEED_ADMIN_FULLNAME,
            config.SEED_ADMIN_EMAIL,
        ),
    )
    # A second demo agent and a demo requester, purely so the seeded example
    # tickets have someone to be assigned to / raised by.
    conn.execute(
        """INSERT INTO users (username, password_hash, full_name, email, role, is_admin, department)
           VALUES ('agent2', ?, 'Sam Rivera', 'sam.rivera@example.com', 'agent', 0, 'IT')""",
        (hash_password("agent123"),),
    )
    conn.execute(
        """INSERT INTO users (username, password_hash, full_name, email, role, is_admin, department)
           VALUES ('jsmith', ?, 'Jamie Smith', 'jamie.smith@example.com', 'requester', 0, 'Production')""",
        (hash_password("requester123"),),
    )


def seed_example_data(conn):
    existing = conn.execute("SELECT id FROM tickets LIMIT 1").fetchone()
    if existing:
        return

    admin = conn.execute("SELECT id, full_name, email FROM users WHERE is_admin = 1").fetchone()
    requester = conn.execute("SELECT id, full_name, email, department FROM users WHERE role = 'requester'").fetchone()
    if not admin or not requester:
        return

    # Example assets
    conn.execute(
        """INSERT INTO assets (asset_tag, type, assigned_to, location, purchase_date, warranty_expiry, status)
           VALUES ('AST-1001', 'Laptop', ?, 'Plant 1 - Line A', '2023-02-15', '2026-02-15', 'In Use')""",
        (requester["full_name"],),
    )
    conn.execute(
        """INSERT INTO assets (asset_tag, type, assigned_to, location, purchase_date, warranty_expiry, status)
           VALUES ('AST-1002', 'Network Switch', '', 'Server Room', '2022-06-01', '2025-06-01', 'In Use')"""
    )
    conn.execute(
        """INSERT INTO assets (asset_tag, type, assigned_to, location, purchase_date, warranty_expiry, status)
           VALUES ('AST-1003', 'Desktop', '', 'IT Storeroom', '2021-09-10', '2024-09-10', 'Spare')"""
    )

    # Example license, expiring soon so the dashboard widget has data
    conn.execute(
        """INSERT INTO licenses (software_name, vendor, license_key, total_seats, seats_in_use, renewal_date, cost, owner)
           VALUES ('AutoCAD', 'Autodesk', 'XXXX-XXXX-XXXX', 10, 8, date('now', '+25 days'), 3200.00, 'IT Procurement')"""
    )
    conn.execute(
        """INSERT INTO licenses (software_name, vendor, license_key, total_seats, seats_in_use, renewal_date, cost, owner)
           VALUES ('Microsoft 365 Business', 'Microsoft', 'XXXX-XXXX-XXXX', 120, 97, date('now', '+180 days'), 14400.00, 'IT Procurement')"""
    )

    # Example KB article
    conn.execute(
        """INSERT INTO kb_articles (title, category, body, tags, created_by)
           VALUES (?, 'Access/Account', ?, 'password, reset, login', ?)""",
        (
            "How to reset a Windows domain password",
            "1. Confirm the requester's identity (employee ID + department).\n"
            "2. Open Active Directory Users and Computers.\n"
            "3. Right-click the user, choose 'Reset Password'.\n"
            "4. Set a temporary password and check 'User must change password at next logon'.\n"
            "5. Notify the requester via their manager or a verified phone number.",
            admin["full_name"],
        ),
    )

    def create_ticket(number, title, description, category, priority, status, assignee_id, days_ago, resolved=False, closed=False):
        sla_hours = config.SLA_HOURS.get(priority, 72)
        conn.execute(
            f"""INSERT INTO tickets
                (ticket_number, title, description, category, priority, status,
                 requester_id, requester_name, requester_email, requester_department,
                 assignee_id, created_at, updated_at, sla_due_at,
                 resolved_at, closed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        datetime('now', ?), datetime('now', ?),
                        datetime('now', ?, ?),
                        {"datetime('now', ?)" if resolved else "NULL"},
                        {"datetime('now', ?)" if closed else "NULL"})
            """,
            [
                number, title, description, category, priority, status,
                requester["id"], requester["full_name"], requester["email"], requester["department"] or "",
                assignee_id,
                f"-{days_ago} days", f"-{max(days_ago - 1, 0)} days",
                f"-{days_ago} days", f"+{sla_hours} hours",
            ] + ([f"-{max(days_ago - 1, 0)} days"] if resolved else [])
              + ([f"-{max(days_ago - 2, 0)} days"] if closed else []),
        )

    create_ticket(
        "IT-0001", "Laptop won't power on",
        "My laptop (AST-1001) doesn't turn on at all, tried a different outlet already.",
        "Hardware", "High", "Open", admin["id"], days_ago=2,
    )
    create_ticket(
        "IT-0002", "Need access to shared drive \\\\fileserver\\production",
        "New hire needs read/write access to the production shared drive.",
        "Access/Account", "Medium", "In Progress", admin["id"], days_ago=1,
    )
    create_ticket(
        "IT-0003", "Outlook keeps freezing when opening large attachments",
        "Happens a few times a day, have to force-quit and reopen.",
        "Email", "Low", "Resolved", admin["id"], days_ago=6, resolved=True,
    )

    conn.execute(
        """INSERT INTO ticket_comments (ticket_id, author_id, author_name, body, is_internal)
           VALUES (1, ?, ?, 'Checked the power brick, it appears fine. Will bring a loaner laptop this afternoon.', 1)""",
        (admin["id"], admin["full_name"]),
    )
    conn.execute(
        """INSERT INTO ticket_comments (ticket_id, author_id, author_name, body, is_internal)
           VALUES (3, ?, ?, 'Cleared the Outlook cache and repaired the profile -- resolved.', 0)""",
        (admin["id"], admin["full_name"]),
    )
    conn.execute("INSERT INTO ticket_assets (ticket_id, asset_id) VALUES (1, 1)")


def run_seed():
    conn = get_connection()
    try:
        seed_categories(conn)
        seed_sla_rules(conn)
        seed_admin(conn)
        seed_example_data(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    from .database import init_db
    init_db()
    run_seed()
    print("Database seeded.")
