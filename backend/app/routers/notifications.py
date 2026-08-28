import sqlite3

from fastapi import APIRouter, Depends

from ..database import get_db
from ..deps import get_current_user
from ..utils import rows_to_list

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user["id"],)
    ).fetchall()
    unread = conn.execute(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],)
    ).fetchone()["c"]
    return {"items": rows_to_list(rows), "unread_count": unread}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, user["id"])
    )
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user["id"],))
    return {"ok": True}
