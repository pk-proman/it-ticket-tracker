import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..deps import get_current_user, require_agent
from ..utils import rows_to_list

router = APIRouter(prefix="/api/licenses", tags=["licenses"])


class LicenseRequest(BaseModel):
    software_name: str = Field(min_length=1, max_length=200)
    vendor: str = ""
    license_key: str = ""
    total_seats: int = Field(default=1, ge=0)
    seats_in_use: int = Field(default=0, ge=0)
    renewal_date: Optional[str] = None
    cost: float = 0
    owner: str = ""


def _with_flags(row) -> dict:
    d = dict(row)
    d["seats_available"] = max(d["total_seats"] - d["seats_in_use"], 0)
    return d


@router.get("")
def list_licenses(q: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    if q:
        rows = conn.execute(
            "SELECT * FROM licenses WHERE software_name LIKE ? OR vendor LIKE ? ORDER BY software_name",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM licenses ORDER BY software_name").fetchall()
    return [_with_flags(r) for r in rows]


@router.get("/expiring")
def expiring_licenses(days: int = 90, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    rows = conn.execute(
        """SELECT * FROM licenses
           WHERE renewal_date IS NOT NULL
             AND date(renewal_date) BETWEEN date('now') AND date('now', ?)
           ORDER BY renewal_date""",
        (f"+{days} days",),
    ).fetchall()
    return [_with_flags(r) for r in rows]


@router.get("/{license_id}")
def get_license(license_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="License not found")
    tickets = conn.execute(
        """SELECT t.id, t.ticket_number, t.title, t.status FROM tickets t
           JOIN ticket_licenses tl ON tl.ticket_id = t.id WHERE tl.license_id = ?""",
        (license_id,),
    ).fetchall()
    d = _with_flags(row)
    d["tickets"] = rows_to_list(tickets)
    return d


@router.post("")
def create_license(payload: LicenseRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    cur = conn.execute(
        """INSERT INTO licenses (software_name, vendor, license_key, total_seats, seats_in_use, renewal_date, cost, owner)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (payload.software_name.strip(), payload.vendor, payload.license_key, payload.total_seats,
         payload.seats_in_use, payload.renewal_date, payload.cost, payload.owner),
    )
    return _with_flags(conn.execute("SELECT * FROM licenses WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{license_id}")
def update_license(license_id: int, payload: LicenseRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="License not found")
    conn.execute(
        """UPDATE licenses SET software_name = ?, vendor = ?, license_key = ?, total_seats = ?,
           seats_in_use = ?, renewal_date = ?, cost = ?, owner = ? WHERE id = ?""",
        (payload.software_name.strip(), payload.vendor, payload.license_key, payload.total_seats,
         payload.seats_in_use, payload.renewal_date, payload.cost, payload.owner, license_id),
    )
    return _with_flags(conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone())


@router.delete("/{license_id}")
def delete_license(license_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    conn.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
    return {"ok": True}
