import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..deps import get_current_user, require_agent
from ..utils import rows_to_list

router = APIRouter(prefix="/api/kb", tags=["knowledge base"])


class ArticleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: str = "Other"
    body: str = Field(min_length=1, max_length=20000)
    tags: str = ""


@router.get("")
def list_articles(q: Optional[str] = None, category: Optional[str] = None,
                   conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    clauses, params = [], []
    if q:
        clauses.append("(title LIKE ? OR body LIKE ? OR tags LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM kb_articles {where} ORDER BY updated_at DESC", params).fetchall()
    return rows_to_list(rows)


@router.get("/{article_id}")
def get_article(article_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(get_current_user)):
    row = conn.execute("SELECT * FROM kb_articles WHERE id = ?", (article_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return dict(row)


@router.post("")
def create_article(payload: ArticleRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    cur = conn.execute(
        "INSERT INTO kb_articles (title, category, body, tags, created_by) VALUES (?, ?, ?, ?, ?)",
        (payload.title.strip(), payload.category, payload.body.strip(), payload.tags.strip(), user["full_name"]),
    )
    return dict(conn.execute("SELECT * FROM kb_articles WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{article_id}")
def update_article(article_id: int, payload: ArticleRequest, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    row = conn.execute("SELECT * FROM kb_articles WHERE id = ?", (article_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    conn.execute(
        "UPDATE kb_articles SET title = ?, category = ?, body = ?, tags = ?, updated_at = datetime('now') WHERE id = ?",
        (payload.title.strip(), payload.category, payload.body.strip(), payload.tags.strip(), article_id),
    )
    return dict(conn.execute("SELECT * FROM kb_articles WHERE id = ?", (article_id,)).fetchone())


@router.delete("/{article_id}")
def delete_article(article_id: int, conn: sqlite3.Connection = Depends(get_db), user=Depends(require_agent)):
    conn.execute("DELETE FROM kb_articles WHERE id = ?", (article_id,))
    return {"ok": True}
