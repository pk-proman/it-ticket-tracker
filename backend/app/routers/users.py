import csv
import io
import secrets
import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..security import hash_password
from ..utils import rows_to_list

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_ROLES = {"agent", "requester"}
TRUE_VALUES = {"1", "true", "yes", "y"}


def _public(row):
    d = dict(row)
    d.pop("password_hash", None)
    return d


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    role: str = Field(pattern="^(agent|requester)$")
    is_admin: bool = False
    department: str = ""


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    role: str | None = Field(default=None, pattern="^(agent|requester)$")
    is_admin: bool | None = None
    department: str | None = None
    active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=200)


@router.get("")
def list_users(conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    # Any authenticated agent can see the agent directory (for assignment dropdowns);
    # full user management (create/edit/reset password) is admin-only, enforced below.
    rows = conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()
    if user["is_admin"]:
        return rows_to_list(rows)
    # Non-admin agents only get name/id/role for populating dropdowns.
    return [{"id": r["id"], "full_name": r["full_name"], "role": r["role"], "active": r["active"]} for r in rows]


@router.get("/agents")
def list_agents(conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    rows = conn.execute(
        "SELECT id, full_name, username FROM users WHERE role = 'agent' AND active = 1 ORDER BY full_name"
    ).fetchall()
    return rows_to_list(rows)


@router.post("")
def create_user(payload: CreateUserRequest, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (payload.username,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    cur = conn.execute(
        """INSERT INTO users (username, password_hash, full_name, email, role, is_admin, department)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (payload.username.strip(), hash_password(payload.password), payload.full_name.strip(),
         payload.email, payload.role, int(payload.is_admin), payload.department.strip()),
    )
    row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _public(row)


@router.patch("/{user_id}")
def update_user(user_id: int, payload: UpdateUserRequest, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return _public(row)
    set_clauses = []
    values = []
    for key, value in fields.items():
        col = key
        if isinstance(value, bool):
            value = int(value)
        set_clauses.append(f"{col} = ?")
        values.append(value)
    values.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?", values)
    updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _public(updated)


@router.delete("/{user_id}")
def delete_user(user_id: int, conn: sqlite3.Connection = Depends(get_db), admin=Depends(require_admin)):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="You can't delete your own account")
    if row["is_admin"]:
        other_admins = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE is_admin = 1 AND id != ?", (user_id,)
        ).fetchone()["c"]
        if other_admins == 0:
            raise HTTPException(status_code=400, detail="Can't delete the last admin account")
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{row['full_name']} has ticket history (raised, assigned, or commented on tickets) "
                "and can't be deleted. Disable their account instead (toggle Active to off)."
            ),
        )
    return {"ok": True}


class ImportSummary(BaseModel):
    created: list
    skipped: list
    errors: list


@router.post("/import", response_model=ImportSummary)
async def import_users(
    file: UploadFile = File(...), conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)
):
    """
    Bulk-create users from a CSV file. Expected header row (order doesn't
    matter): username, full_name, email, role, department, password, is_admin.

    - `role` must be "agent" or "requester" (defaults to "requester" if blank).
    - `password` is optional -- if left blank, a random temporary password is
      generated and returned in the response so it can be shared with the
      user out-of-band (there's no email delivery in this app -- see README).
    - `is_admin` is optional, one of true/false/1/0/yes/no (defaults to false).
    - Rows with a username that already exists are skipped, not overwritten.
    """
    # Not gating on file.content_type -- browsers/OSes send inconsistent
    # values for .csv (text/csv, application/vnd.ms-excel, octet-stream...);
    # the actual parse below is the real validation.
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:  # 2MB is generous for a user list
        raise HTTPException(status_code=400, detail="CSV file is too large (max 2MB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Could not read file as UTF-8 text -- please export as a plain CSV")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "username" not in {f.strip().lower() for f in reader.fieldnames}:
        raise HTTPException(status_code=400, detail="CSV must have a header row including at least a 'username' column")

    # Normalize header names so the CSV is forgiving of case/spacing.
    reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]

    created, skipped, errors = [], [], []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        username = (row.get("username") or "").strip()
        full_name = (row.get("full_name") or "").strip()
        email = (row.get("email") or "").strip()
        role = (row.get("role") or "requester").strip().lower()
        department = (row.get("department") or "").strip()
        password = (row.get("password") or "").strip()
        is_admin = (row.get("is_admin") or "").strip().lower() in TRUE_VALUES

        if not username or not full_name or not email:
            errors.append({"row": i, "username": username, "reason": "username, full_name, and email are required"})
            continue
        if "@" not in email:
            errors.append({"row": i, "username": username, "reason": f"'{email}' doesn't look like a valid email"})
            continue
        if role not in VALID_ROLES:
            errors.append({"row": i, "username": username, "reason": f"role must be 'agent' or 'requester', got '{role}'"})
            continue
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            skipped.append({"row": i, "username": username, "reason": "username already exists"})
            continue

        generated_password = None
        if not password:
            generated_password = secrets.token_urlsafe(9)
            password = generated_password
        elif len(password) < 6:
            errors.append({"row": i, "username": username, "reason": "password must be at least 6 characters"})
            continue

        conn.execute(
            """INSERT INTO users (username, password_hash, full_name, email, role, is_admin, department)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, hash_password(password), full_name, email, role, int(is_admin), department),
        )
        created.append({
            "row": i, "username": username, "full_name": full_name, "role": role,
            "temp_password": generated_password,  # null if the CSV supplied its own password
        })

    return {"created": created, "skipped": skipped, "errors": errors}


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, payload: ResetPasswordRequest, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(payload.new_password), user_id))
    return {"ok": True}
