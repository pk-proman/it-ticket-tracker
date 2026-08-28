import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..database import get_db
from ..deps import get_current_user
from ..security import verify_password
from ..utils import row_to_dict

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


def public_user(row) -> dict:
    d = row_to_dict(row)
    if d:
        d.pop("password_hash", None)
    return d


@router.post("/login")
def login(payload: LoginRequest, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    username = payload.username.strip()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not user["active"] or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    request.session["user_id"] = user["id"]
    return public_user(user)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return public_user(user)
