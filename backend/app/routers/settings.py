import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import PRIORITIES, STATUSES
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..utils import rows_to_list

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/categories")
def get_categories(conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    # Available to any logged-in user (not admin-only) -- everyone needs the
    # category list to raise a ticket. Managing the list (add/remove, below)
    # stays admin-only.
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return rows_to_list(rows)


class CategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.post("/categories")
def add_category(payload: CategoryRequest, conn: sqlite3.Connection = Depends(get_db), _admin=Depends(require_admin)):
    try:
        conn.execute("INSERT INTO categories (name) VALUES (?)", (payload.name.strip(),))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Category already exists")
    return rows_to_list(conn.execute("SELECT * FROM categories ORDER BY name").fetchall())


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
