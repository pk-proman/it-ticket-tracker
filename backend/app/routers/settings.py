import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import PRIORITIES, STATUSES
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..utils import rows_to_list

router = APIRouter(prefix="/api/settings", tags=["settings"])


_CATEGORY_SELECT = """
    SELECT c.*, da.full_name AS default_assignee_name, ap.full_name AS approver_name
    FROM categories c
    LEFT JOIN users da ON da.id = c.default_assignee_id
    LEFT JOIN users ap ON ap.id = c.approver_id
"""


@router.get("/categories")
def get_categories(conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    # Available to any logged-in user (not admin-only) -- everyone needs the
    # category list to raise a ticket. Managing the list (add/remove, below)
    # stays admin-only.
    rows = conn.execute(f"{_CATEGORY_SELECT} ORDER BY c.name").fetchall()
    return rows_to_list(rows)


class CategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryConfigRequest(BaseModel):
    default_assignee_id: int | None = None
    requires_approval: bool = False
    approver_id: int | None = None


@router.post("/categories")
def add_category(payload: CategoryRequest, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    try:
        conn.execute("INSERT INTO categories (name) VALUES (?)", (payload.name.strip(),))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Category already exists")
    return rows_to_list(conn.execute(f"{_CATEGORY_SELECT} ORDER BY c.name").fetchall())


def _require_agent_or_none(conn: sqlite3.Connection, user_id: int | None, field: str):
    if user_id is None:
        return
    row = conn.execute("SELECT id FROM users WHERE id = ? AND role = 'agent'", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail=f"{field} must be an existing agent")


@router.patch("/categories/{category_id}")
def update_category_config(
    category_id: int, payload: CategoryConfigRequest,
    conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin),
):
    """Configure the workflow for a category: who tickets in it default-assign
    to, and (optionally) who must approve before that assignment happens."""
    existing = conn.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Category not found")
    _require_agent_or_none(conn, payload.default_assignee_id, "default_assignee_id")
    if payload.requires_approval and not payload.approver_id:
        raise HTTPException(status_code=400, detail="An approver is required when requires_approval is on")
    _require_agent_or_none(conn, payload.approver_id, "approver_id")

    conn.execute(
        "UPDATE categories SET default_assignee_id = ?, requires_approval = ?, approver_id = ? WHERE id = ?",
        (payload.default_assignee_id, int(payload.requires_approval), payload.approver_id, category_id),
    )
    return dict(conn.execute(f"{_CATEGORY_SELECT} WHERE c.id = ?", (category_id,)).fetchone())


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return {"ok": True}


@router.get("/sla")
def get_sla(conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    rows = conn.execute("SELECT * FROM sla_rules").fetchall()
    return rows_to_list(rows)


class SlaRequest(BaseModel):
    priority: str = Field(pattern="^(Low|Medium|High|Critical)$")
    hours: int = Field(gt=0, le=24 * 90)


@router.put("/sla")
def update_sla(payload: SlaRequest, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    conn.execute(
        "INSERT INTO sla_rules (priority, hours) VALUES (?, ?) "
        "ON CONFLICT(priority) DO UPDATE SET hours = excluded.hours",
        (payload.priority, payload.hours),
    )
    return rows_to_list(conn.execute("SELECT * FROM sla_rules").fetchall())


@router.get("/meta")
def get_meta(user=Depends(get_current_user)):
    """Static enum-like reference data for the frontend (priorities/statuses)."""
    return {"priorities": PRIORITIES, "statuses": STATUSES}
