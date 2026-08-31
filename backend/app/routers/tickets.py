import csv
import io
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

from .. import config
from ..database import get_db
from ..deps import get_current_user, require_agent, require_admin
from ..utils import compute_sla_due, log_audit, next_ticket_number, notify_user, rows_to_list, serialize_ticket_row

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateTicketRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(default="", max_length=20000)
    category: str
    priority: str = Field(pattern="^(Low|Medium|High|Critical)$")
    requester_name: Optional[str] = None
    requester_email: Optional[EmailStr] = None
    requester_department: Optional[str] = None

    @field_validator("requester_name", "requester_email", "requester_department", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        # Frontend sends "" for optional fields it left empty -- treat that as
        # "not provided" rather than failing EmailStr validation on "".
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class UpdateTicketRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=300)
    description: Optional[str] = Field(default=None, max_length=20000)
    category: Optional[str] = None
    priority: Optional[str] = Field(default=None, pattern="^(Low|Medium|High|Critical)$")
    status: Optional[str] = Field(default=None, pattern="^(Open|In Progress|Waiting on User|Waiting on Vendor|Resolved|Closed)$")
    assignee_id: Optional[int] = None


class CommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    is_internal: bool = False


class BulkActionRequest(BaseModel):
    ticket_ids: list[int]
    status: Optional[str] = Field(default=None, pattern="^(Open|In Progress|Waiting on User|Waiting on Vendor|Resolved|Closed)$")
    assignee_id: Optional[int] = None


class LinkRequest(BaseModel):
    id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _can_view_ticket(user, ticket_row) -> bool:
    """
    Admins see every ticket. Everyone else (agent or requester, as long as
    they're not an admin) only sees tickets they raised or are assigned to.
    """
    if user["is_admin"]:
        return True
    return ticket_row["requester_id"] == user["id"] or ticket_row["assignee_id"] == user["id"]


def _ticket_or_404(conn, ticket_id: int):
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return row


_serialize_ticket = serialize_ticket_row


# ---------------------------------------------------------------------------
# List / filter / export
# ---------------------------------------------------------------------------

def _build_filtered_query(user, status=None, priority=None, category=None, assignee_id=None,
                           date_from=None, date_to=None, q=None, mine=False, requester_id=None):
    clauses = []
    params: list = []

    if not user["is_admin"]:
        # Non-admins (agent or requester) only ever see tickets they raised or
        # are assigned to -- admins are the only role with org-wide visibility.
        clauses.append("(requester_id = ? OR assignee_id = ?)")
        params.extend([user["id"], user["id"]])
    elif requester_id:
        clauses.append("requester_id = ?")
        params.append(requester_id)

    if status:
        clauses.append("status = ?")
        params.append(status)
    if priority:
        clauses.append("priority = ?")
        params.append(priority)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if assignee_id:
        clauses.append("assignee_id = ?")
        params.append(assignee_id)
    if mine and user["role"] == "agent":
        clauses.append("assignee_id = ?")
        params.append(user["id"])
    if date_from:
        clauses.append("date(created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        clauses.append("date(created_at) <= date(?)")
        params.append(date_to)
    if q:
        clauses.append("(title LIKE ? OR description LIKE ? OR ticket_number LIKE ? OR requester_name LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


@router.get("")
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    assignee_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    mine: bool = False,
    requester_id: Optional[int] = None,
    sort: str = "created_at",
    direction: str = "desc",
    page: int = 1,
    page_size: int = 50,
    conn: sqlite3.Connection = Depends(get_db),
    user=Depends(get_current_user),
):
    where, params = _build_filtered_query(user, status, priority, category, assignee_id,
                                           date_from, date_to, q, mine, requester_id)
    sort_col = sort if sort in {
        "created_at", "updated_at", "priority", "status", "category", "sla_due_at", "ticket_number"
    } else "created_at"
    direction = "ASC" if direction.lower() == "asc" else "DESC"
    page = max(page, 1)
    page_size = min(max(page_size, 1), 500)
    offset = (page - 1) * page_size

    total = conn.execute(f"SELECT COUNT(*) AS c FROM tickets {where}", params).fetchone()["c"]
    rows = conn.execute(
        f"""SELECT t.*, a.full_name AS assignee_name
            FROM tickets t LEFT JOIN users a ON a.id = t.assignee_id
            {where} ORDER BY {sort_col} {direction} LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()
    return {
        "items": [_serialize_ticket(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/export.csv")
def export_tickets_csv(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    assignee_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    mine: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
    user=Depends(get_current_user),
):
    where, params = _build_filtered_query(user, status, priority, category, assignee_id, date_from, date_to, q, mine)
    rows = conn.execute(
        f"""SELECT t.*, a.full_name AS assignee_name
            FROM tickets t LEFT JOIN users a ON a.id = t.assignee_id
            {where} ORDER BY t.created_at DESC""",
        params,
    ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Ticket #", "Title", "Category", "Priority", "Status", "Requester", "Requester Email",
                      "Department", "Assignee", "Created", "Updated", "Resolved", "SLA Due", "SLA Overdue"])
    for r in rows:
        d = _serialize_ticket(r)
        writer.writerow([
            d["ticket_number"], d["title"], d["category"], d["priority"], d["status"],
            d["requester_name"], d["requester_email"], d["requester_department"],
            d.get("assignee_name") or "", d["created_at"], d["updated_at"], d["resolved_at"] or "",
            d["sla_due_at"] or "", "YES" if d["sla_overdue"] else "NO",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tickets_export.csv"},
    )


# ---------------------------------------------------------------------------
# Create / retrieve / update
# ---------------------------------------------------------------------------

@router.post("")
def create_ticket(payload: CreateTicketRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    valid_categories = {r["name"] for r in conn.execute("SELECT name FROM categories").fetchall()}
    if payload.category not in valid_categories:
        raise HTTPException(status_code=400, detail="Unknown category")

    if user["role"] == "requester":
        requester_id = user["id"]
        requester_name = user["full_name"]
        requester_email = user["email"]
        requester_department = user["department"] or ""
    else:
        # Agents can raise tickets on behalf of someone else (walk-up / phone request).
        requester_id = None
        requester_name = payload.requester_name or user["full_name"]
        requester_email = payload.requester_email or user["email"]
        requester_department = payload.requester_department or ""

    ticket_number = next_ticket_number(conn)
    sla_due_at = compute_sla_due(conn, payload.priority)

    cur = conn.execute(
        """INSERT INTO tickets
           (ticket_number, title, description, category, priority, status,
            requester_id, requester_name, requester_email, requester_department, sla_due_at)
           VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?)""",
        (ticket_number, payload.title.strip(), payload.description.strip(), payload.category,
         payload.priority, requester_id, requester_name, requester_email, requester_department, sla_due_at),
    )
    ticket_id = cur.lastrowid
    log_audit(conn, ticket_id, "status", None, "Open", user["full_name"])

    # Notify all agents of a new ticket
    agents = conn.execute("SELECT id FROM users WHERE role = 'agent' AND active = 1").fetchall()
    for a in agents:
        notify_user(conn, a["id"], "new_ticket", f"New ticket {ticket_number}: {payload.title.strip()}", ticket_id)

    row = _ticket_or_404(conn, ticket_id)
    return _serialize_ticket(row)


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized to view this ticket")
    d = _serialize_ticket(row)
    if row["assignee_id"]:
        assignee = conn.execute("SELECT full_name FROM users WHERE id = ?", (row["assignee_id"],)).fetchone()
        d["assignee_name"] = assignee["full_name"] if assignee else None
    else:
        d["assignee_name"] = None

    linked_assets = conn.execute(
        """SELECT a.* FROM assets a JOIN ticket_assets ta ON ta.asset_id = a.id WHERE ta.ticket_id = ?""",
        (ticket_id,),
    ).fetchall()
    linked_licenses = conn.execute(
        """SELECT l.* FROM licenses l JOIN ticket_licenses tl ON tl.license_id = l.id WHERE tl.ticket_id = ?""",
        (ticket_id,),
    ).fetchall()
    d["assets"] = rows_to_list(linked_assets)
    d["licenses"] = rows_to_list(linked_licenses)
    return d


@router.patch("/{ticket_id}")
def update_ticket(ticket_id: int, payload: UpdateTicketRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return _serialize_ticket(row)

    if user["role"] != "agent":
        # Requesters may only close their own already-resolved ticket -- nothing else.
        allowed = set(fields.keys()) <= {"status"} and fields.get("status") == "Closed"
        if not allowed or row["requester_id"] != user["id"] or row["status"] != "Resolved":
            raise HTTPException(status_code=403, detail="Requesters may only close their own resolved tickets")
    elif not user["is_admin"] and not _can_view_ticket(user, row):
        # Non-admin agents may only update tickets they raised or are assigned to.
        raise HTTPException(status_code=403, detail="You can only update tickets you raised or are assigned to")

    updates = {}
    if "title" in fields and fields["title"] is not None:
        updates["title"] = fields["title"].strip()
    if "description" in fields and fields["description"] is not None:
        updates["description"] = fields["description"].strip()
    if "category" in fields and fields["category"] is not None:
        valid_categories = {r["name"] for r in conn.execute("SELECT name FROM categories").fetchall()}
        if fields["category"] not in valid_categories:
            raise HTTPException(status_code=400, detail="Unknown category")
        updates["category"] = fields["category"]

    notify_targets = set()

    if "priority" in fields and fields["priority"] is not None and fields["priority"] != row["priority"]:
        updates["priority"] = fields["priority"]
        # Recompute SLA due date relative to original creation time when priority changes.
        recompute = conn.execute(
            "SELECT datetime(?, ?) AS due",
            (row["created_at"], f"+{conn.execute('SELECT hours FROM sla_rules WHERE priority = ?', (fields['priority'],)).fetchone()['hours']} hours"),
        ).fetchone()["due"]
        updates["sla_due_at"] = recompute
        log_audit(conn, ticket_id, "priority", row["priority"], fields["priority"], user["full_name"])

    if "status" in fields and fields["status"] is not None and fields["status"] != row["status"]:
        updates["status"] = fields["status"]
        log_audit(conn, ticket_id, "status", row["status"], fields["status"], user["full_name"])
        if fields["status"] == "Resolved" and not row["resolved_at"]:
            updates["resolved_at"] = "CURRENT_TIMESTAMP_MARKER"
        if fields["status"] == "Closed" and not row["closed_at"]:
            updates["closed_at"] = "CURRENT_TIMESTAMP_MARKER"
        if user["role"] == "agent" and row["requester_id"]:
            notify_targets.add(row["requester_id"])
        elif user["role"] != "agent" and row["assignee_id"]:
            notify_targets.add(row["assignee_id"])

    if "assignee_id" in fields and fields["assignee_id"] != row["assignee_id"]:
        new_assignee = fields["assignee_id"]
        if new_assignee is not None:
            agent_row = conn.execute("SELECT id, full_name FROM users WHERE id = ? AND role = 'agent'", (new_assignee,)).fetchone()
            if not agent_row:
                raise HTTPException(status_code=400, detail="assignee_id must be an existing agent")
            notify_targets.add(new_assignee)
        old_assignee_row = conn.execute("SELECT full_name FROM users WHERE id = ?", (row["assignee_id"],)).fetchone() if row["assignee_id"] else None
        updates["assignee_id"] = new_assignee
        log_audit(conn, ticket_id, "assignee",
                  old_assignee_row["full_name"] if old_assignee_row else "Unassigned",
                  agent_row["full_name"] if new_assignee is not None else "Unassigned",
                  user["full_name"])

    if not updates:
        return _serialize_ticket(row)

    set_parts = []
    values = []
    for col, val in updates.items():
        if val == "CURRENT_TIMESTAMP_MARKER":
            set_parts.append(f"{col} = datetime('now')")
        else:
            set_parts.append(f"{col} = ?")
            values.append(val)
    set_parts.append("updated_at = datetime('now')")
    values.append(ticket_id)
    conn.execute(f"UPDATE tickets SET {', '.join(set_parts)} WHERE id = ?", values)

    updated_number = conn.execute("SELECT ticket_number FROM tickets WHERE id = ?", (ticket_id,)).fetchone()["ticket_number"]
    for uid in notify_targets:
        notify_user(conn, uid, "ticket_update", f"Ticket {updated_number} was updated", ticket_id)

    return get_ticket(ticket_id, conn, user)


@router.post("/bulk")
def bulk_update(payload: BulkActionRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    if not payload.ticket_ids:
        raise HTTPException(status_code=400, detail="No tickets selected")
    updated = 0
    for tid in payload.ticket_ids:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (tid,)).fetchone()
        if not row:
            continue
        sub = UpdateTicketRequest(status=payload.status, assignee_id=payload.assignee_id)
        try:
            update_ticket(tid, sub, conn, user)
            updated += 1
        except HTTPException:
            continue
    return {"updated": updated}


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@router.get("/{ticket_id}/comments")
def list_comments(ticket_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")
    comments = conn.execute(
        "SELECT * FROM ticket_comments WHERE ticket_id = ? ORDER BY created_at ASC", (ticket_id,)
    ).fetchall()
    if user["role"] != "agent":
        comments = [c for c in comments if not c["is_internal"]]
    return rows_to_list(comments)


@router.post("/{ticket_id}/comments")
def add_comment(ticket_id: int, payload: CommentRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")
    is_internal = payload.is_internal and user["role"] == "agent"  # requesters can never post internal notes
    conn.execute(
        """INSERT INTO ticket_comments (ticket_id, author_id, author_name, body, is_internal)
           VALUES (?, ?, ?, ?, ?)""",
        (ticket_id, user["id"], user["full_name"], payload.body.strip(), int(is_internal)),
    )
    conn.execute("UPDATE tickets SET updated_at = datetime('now') WHERE id = ?", (ticket_id,))

    notify_targets = set()
    if not is_internal:
        if user["role"] == "agent" and row["requester_id"]:
            notify_targets.add(row["requester_id"])
        elif user["role"] != "agent" and row["assignee_id"]:
            notify_targets.add(row["assignee_id"])
    for uid in notify_targets:
        notify_user(conn, uid, "new_comment", f"New comment on ticket {row['ticket_number']}", ticket_id)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

@router.post("/{ticket_id}/attachments")
async def upload_attachment(ticket_id: int, file: UploadFile = File(...), conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")

    original_name = os.path.basename(file.filename or "upload")
    ext = Path(original_name).suffix.lower()
    if ext not in config.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' is not allowed")

    contents = await file.read()
    if len(contents) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds {config.MAX_UPLOAD_MB}MB limit")

    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = config.UPLOADS_DIR / stored_name
    dest.write_bytes(contents)

    conn.execute(
        """INSERT INTO ticket_attachments (ticket_id, filename, stored_filename, content_type, size, uploaded_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ticket_id, original_name, stored_name, file.content_type or "", len(contents), user["full_name"]),
    )
    conn.execute("UPDATE tickets SET updated_at = datetime('now') WHERE id = ?", (ticket_id,))
    return {"ok": True, "filename": original_name}


@router.get("/{ticket_id}/attachments")
def list_attachments(ticket_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")
    rows = conn.execute("SELECT * FROM ticket_attachments WHERE ticket_id = ? ORDER BY uploaded_at", (ticket_id,)).fetchall()
    return rows_to_list(rows)


@router.get("/{ticket_id}/attachments/{attachment_id}/download")
def download_attachment(ticket_id: int, attachment_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")
    att = conn.execute(
        "SELECT * FROM ticket_attachments WHERE id = ? AND ticket_id = ?", (attachment_id, ticket_id)
    ).fetchone()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = config.UPLOADS_DIR / att["stored_filename"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(path, filename=att["filename"], media_type=att["content_type"] or "application/octet-stream")


# ---------------------------------------------------------------------------
# Linking assets / licenses
# ---------------------------------------------------------------------------

@router.post("/{ticket_id}/link-asset")
def link_asset(ticket_id: int, payload: LinkRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")
    asset = conn.execute("SELECT id FROM assets WHERE id = ?", (payload.id,)).fetchone()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    conn.execute("INSERT OR IGNORE INTO ticket_assets (ticket_id, asset_id) VALUES (?, ?)", (ticket_id, payload.id))
    return {"ok": True}


@router.delete("/{ticket_id}/link-asset/{asset_id}")
def unlink_asset(ticket_id: int, asset_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")
    conn.execute("DELETE FROM ticket_assets WHERE ticket_id = ? AND asset_id = ?", (ticket_id, asset_id))
    return {"ok": True}


@router.post("/{ticket_id}/link-license")
def link_license(ticket_id: int, payload: LinkRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_admin)):
    _ticket_or_404(conn, ticket_id)
    lic = conn.execute("SELECT id FROM licenses WHERE id = ?", (payload.id,)).fetchone()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    conn.execute("INSERT OR IGNORE INTO ticket_licenses (ticket_id, license_id) VALUES (?, ?)", (ticket_id, payload.id))
    return {"ok": True}


@router.delete("/{ticket_id}/link-license/{license_id}")
def unlink_license(ticket_id: int, license_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_admin)):
    conn.execute("DELETE FROM ticket_licenses WHERE ticket_id = ? AND license_id = ?", (ticket_id, license_id))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

@router.get("/{ticket_id}/audit")
def get_audit_log(ticket_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = _ticket_or_404(conn, ticket_id)
    if not _can_view_ticket(user, row):
        raise HTTPException(status_code=403, detail="Not authorized")
    rows = conn.execute("SELECT * FROM audit_log WHERE ticket_id = ? ORDER BY changed_at ASC", (ticket_id,)).fetchall()
    return rows_to_list(rows)
