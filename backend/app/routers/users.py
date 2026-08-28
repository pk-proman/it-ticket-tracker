import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..security import hash_password
from ..utils import rows_to_list

router = APIRouter(prefix="/api/users", tags=["users"])


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


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, payload: ResetPasswordRequest, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(payload.new_password), user_id))
    return {"ok": True}
