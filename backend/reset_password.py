#!/usr/bin/env python3
"""
Reset a user's password from the command line -- useful if the admin
account gets locked out.

Usage:
    python backend/reset_password.py <username> <new_password>

Example:
    python backend/reset_password.py admin "NewStrongPassword123"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import get_connection, init_db
from app.security import hash_password


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    username, new_password = sys.argv[1], sys.argv[2]
    if len(new_password) < 6:
        print("Password must be at least 6 characters.")
        sys.exit(1)

    init_db()
    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            print(f"No user found with username '{username}'.")
            sys.exit(1)
        conn.execute("UPDATE users SET password_hash = ?, active = 1 WHERE id = ?", (hash_password(new_password), row["id"]))
        conn.commit()
        print(f"Password for '{username}' has been reset.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
