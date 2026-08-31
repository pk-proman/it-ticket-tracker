import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..config import OPEN_STATUSES
from ..database import get_db
from ..deps import require_admin
from ..utils import rows_to_list, serialize_tickets

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(conn: sqlite3.Connection = Depends(get_db), user=Depends(require_admin)):
    open_placeholders = ",".join("?" for _ in OPEN_STATUSES)

    by_priority = rows_to_list(conn.execute(
        f"SELECT priority, COUNT(*) AS count FROM tickets WHERE status IN ({open_placeholders}) GROUP BY priority",
        OPEN_STATUSES,
    ).fetchall())

    by_category = rows_to_list(conn.execute(
        f"SELECT category, COUNT(*) AS count FROM tickets WHERE status IN ({open_placeholders}) GROUP BY category",
        OPEN_STATUSES,
    ).fetchall())

    by_status = rows_to_list(conn.execute(
        "SELECT status, COUNT(*) AS count FROM tickets GROUP BY status"
    ).fetchall())

    overdue_rows = conn.execute(
        f"""SELECT t.*, a.full_name AS assignee_name FROM tickets t
            LEFT JOIN users a ON a.id = t.assignee_id
            WHERE status IN ({open_placeholders}) AND sla_due_at IS NOT NULL AND sla_due_at < datetime('now')
            ORDER BY sla_due_at ASC LIMIT 25""",
        OPEN_STATUSES,
    ).fetchall()
    overdue_count = conn.execute(
        f"""SELECT COUNT(*) AS c FROM tickets
            WHERE status IN ({open_placeholders}) AND sla_due_at IS NOT NULL AND sla_due_at < datetime('now')""",
        OPEN_STATUSES,
    ).fetchone()["c"]

    assigned_to_me = []
    if user["role"] == "agent":
        assigned_to_me = serialize_tickets(conn.execute(
            f"""SELECT t.*, a.full_name AS assignee_name FROM tickets t
                LEFT JOIN users a ON a.id = t.assignee_id
                WHERE assignee_id = ? AND status IN ({open_placeholders})
                ORDER BY sla_due_at ASC LIMIT 25""",
            [user["id"]] + OPEN_STATUSES,
        ).fetchall())

    licenses_expiring = rows_to_list(conn.execute(
        """SELECT * FROM licenses WHERE renewal_date IS NOT NULL
           AND date(renewal_date) BETWEEN date('now') AND date('now', '+90 days')
           ORDER BY renewal_date"""
    ).fetchall())

    assets_expiring = rows_to_list(conn.execute(
        """SELECT * FROM assets WHERE warranty_expiry IS NOT NULL
           AND date(warranty_expiry) BETWEEN date('now') AND date('now', '+90 days')
           ORDER BY warranty_expiry"""
    ).fetchall())

    created_series = rows_to_list(conn.execute(
        """SELECT date(created_at) AS day, COUNT(*) AS count FROM tickets
           WHERE created_at >= datetime('now', '-30 days') GROUP BY day ORDER BY day"""
    ).fetchall())
    resolved_series = rows_to_list(conn.execute(
        """SELECT date(resolved_at) AS day, COUNT(*) AS count FROM tickets
           WHERE resolved_at IS NOT NULL AND resolved_at >= datetime('now', '-30 days') GROUP BY day ORDER BY day"""
    ).fetchall())

    open_total = conn.execute(
        f"SELECT COUNT(*) AS c FROM tickets WHERE status IN ({open_placeholders})", OPEN_STATUSES
    ).fetchone()["c"]

    return {
        "open_total": open_total,
        "by_priority": by_priority,
        "by_category": by_category,
        "by_status": by_status,
        "overdue_count": overdue_count,
        "overdue_tickets": serialize_tickets(overdue_rows),
        "assigned_to_me": assigned_to_me,
        "licenses_expiring": licenses_expiring,
        "assets_expiring": assets_expiring,
        "created_series": created_series,
        "resolved_series": resolved_series,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
