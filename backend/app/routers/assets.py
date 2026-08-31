import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..deps import get_current_user, require_agent, require_admin
from ..utils import rows_to_list

router = APIRouter(prefix="/api/assets", tags=["assets"])

ASSET_STATUSES = ("In Use", "Spare", "Retired")
ASSET_TYPES = ("Laptop", "Desktop", "Server", "Network Device", "Printer", "Other")


class AssetRequest(BaseModel):
    asset_tag: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    assigned_to: str = ""
    location: str = ""
    purchase_date: Optional[str] = None
    warranty_expiry: Optional[str] = None
    status: str = "In Use"
    notes: str = ""


@router.get("")
def list_assets(q: Optional[str] = None, status: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    clauses, params = [], []
    if not user["is_admin"]:
        # Non-admins (agent or requester) only see assets assigned to them.
        clauses.append("lower(assigned_to) = lower(?)")
        params.append(user["full_name"])
    if q:
        clauses.append("(asset_tag LIKE ? OR assigned_to LIKE ? OR location LIKE ? OR type LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM assets {where} ORDER BY asset_tag", params).fetchall()
    return rows_to_list(rows)


@router.get("/warranty-expiring")
def warranty_expiring(days: int = 90, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_admin)):
    rows = conn.execute(
        """SELECT * FROM assets
           WHERE warranty_expiry IS NOT NULL
             AND date(warranty_expiry) BETWEEN date('now') AND date('now', ?)
           ORDER BY warranty_expiry""",
        (f"+{days} days",),
    ).fetchall()
    return rows_to_list(rows)


@router.get("/{asset_id}")
def get_asset(asset_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    if not user["is_admin"] and (row["assigned_to"] or "").lower() != user["full_name"].lower():
        raise HTTPException(status_code=403, detail="Not authorized to view this asset")
    tickets = conn.execute(
        """SELECT t.id, t.ticket_number, t.title, t.status FROM tickets t
           JOIN ticket_assets ta ON ta.ticket_id = t.id WHERE ta.asset_id = ?""",
        (asset_id,),
    ).fetchall()
    d = dict(row)
    d["tickets"] = rows_to_list(tickets)
    return d


@router.post("")
def create_asset(payload: AssetRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    try:
        cur = conn.execute(
            """INSERT INTO assets (asset_tag, type, assigned_to, location, purchase_date, warranty_expiry, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.asset_tag.strip(), payload.type, payload.assigned_to, payload.location,
             payload.purchase_date, payload.warranty_expiry, payload.status, payload.notes),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Asset tag already exists")
    return dict(conn.execute("SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{asset_id}")
def update_asset(asset_id: int, payload: AssetRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    conn.execute(
        """UPDATE assets SET asset_tag = ?, type = ?, assigned_to = ?, location = ?,
           purchase_date = ?, warranty_expiry = ?, status = ?, notes = ? WHERE id = ?""",
        (payload.asset_tag.strip(), payload.type, payload.assigned_to, payload.location,
         payload.purchase_date, payload.warranty_expiry, payload.status, payload.notes, asset_id),
    )
    return dict(conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone())


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_admin)):
    conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    return {"ok": True}
