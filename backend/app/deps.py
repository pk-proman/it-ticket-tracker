"""
Auth dependencies shared by routers. Sessions are signed cookies (via
Starlette's SessionMiddleware) holding just the user id -- the user row
itself is always re-read from the DB so role/active changes take effect
immediately.
"""
import sqlite3

from fastapi import Depends, HTTPException, Request, status

from .database import get_db


def get_current_user(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user or not user["active"]:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return user


def get_optional_user(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user or not user["active"]:
        return None
    return user


def require_agent(user=Depends(get_current_user)):
    if user["role"] != "agent":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent access required")
    return user


def require_admin(user=Depends(get_current_user)):
    if not user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
