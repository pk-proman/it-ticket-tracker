import csv
import io
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..database import get_db
from ..deps import require_admin
from ..utils import rows_to_list

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _month_bounds(year: int, month: int):
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"
    return start, end


def _build_monthly_report(conn: sqlite3.Connection, year: int, month: int) -> dict:
    start, end = _month_bounds(year, month)

    by_category = rows_to_list(conn.execute(
        """SELECT category, COUNT(*) AS count FROM tickets
           WHERE created_at >= ? AND created_at < ? GROUP BY category ORDER BY count DESC""",
        (start, end),
    ).fetchall())

    total_created = conn.execute(
        "SELECT COUNT(*) AS c FROM tickets WHERE created_at >= ? AND created_at < ?", (start, end)
    ).fetchone()["c"]

    resolved_rows = conn.execute(
        """SELECT created_at, resolved_at, sla_due_at FROM tickets
           WHERE resolved_at IS NOT NULL AND resolved_at >= ? AND resolved_at < ?""",
        (start, end),
    ).fetchall()

    total_resolved = len(resolved_rows)
    total_seconds = 0
    met_sla = 0
    for r in resolved_rows:
        try:
            created = datetime.fromisoformat(r["created_at"])
            resolved = datetime.fromisoformat(r["resolved_at"])
            total_seconds += (resolved - created).total_seconds()
        except ValueError:
            pass
        if r["sla_due_at"]:
            try:
                due = datetime.fromisoformat(r["sla_due_at"])
                resolved = datetime.fromisoformat(r["resolved_at"])
                if resolved <= due:
                    met_sla += 1
            except ValueError:
                pass

    avg_resolution_hours = round((total_seconds / total_resolved) / 3600, 2) if total_resolved else 0
    sla_compliance_pct = round((met_sla / total_resolved) * 100, 1) if total_resolved else None

    return {
        "year": year,
        "month": month,
        "total_created": total_created,
        "total_resolved": total_resolved,
        "avg_resolution_hours": avg_resolution_hours,
        "sla_compliance_pct": sla_compliance_pct,
        "sla_met_count": met_sla,
        "by_category": by_category,
    }


@router.get("/monthly")
def monthly_report(
    year: int = Query(default=None), month: int = Query(default=None),
    conn: sqlite3.Connection = Depends(get_db), user=Depends(require_admin),
):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    return _build_monthly_report(conn, year, month)


@router.get("/monthly/export.csv")
def monthly_report_csv(
    year: int = Query(default=None), month: int = Query(default=None),
    conn: sqlite3.Connection = Depends(get_db), user=Depends(require_admin),
):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    report = _build_monthly_report(conn, year, month)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([f"Monthly Summary Report - {year}-{month:02d}"])
    writer.writerow([])
    writer.writerow(["Total tickets created", report["total_created"]])
    writer.writerow(["Total tickets resolved", report["total_resolved"]])
    writer.writerow(["Average resolution time (hours)", report["avg_resolution_hours"]])
    writer.writerow(["SLA compliance %", report["sla_compliance_pct"] if report["sla_compliance_pct"] is not None else "N/A"])
    writer.writerow([])
    writer.writerow(["Category", "Tickets Created"])
    for row in report["by_category"]:
        writer.writerow([row["category"], row["count"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=monthly_report_{year}_{month:02d}.csv"},
    )
