"""
FastAPI application entrypoint. Wires up session auth, all API routers,
and serves the built React frontend as static files so the whole app
runs behind a single port.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import config
from .database import init_db
from .seed import run_seed
from .routers import auth, users, settings as settings_router, tickets, assets, licenses, kb, notifications, dashboard, reports, sso

app = FastAPI(title="IT Support Ticket Tracker", version="1.0.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=config.SESSION_MAX_AGE_HOURS * 3600,
    same_site="lax",
    https_only=config.SESSION_SECURE_COOKIES,
)


@app.on_event("startup")
def on_startup():
    init_db()
    run_seed()


# --- API routers -----------------------------------------------------------
app.include_router(auth.router)
app.include_router(sso.router)
app.include_router(users.router)
app.include_router(settings_router.router)
app.include_router(tickets.router)
app.include_router(assets.router)
app.include_router(licenses.router)
app.include_router(kb.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)
app.include_router(reports.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- Static frontend ---------------------------------------------------------
# The React app is built to frontend/dist by `npm run build` and served here
# as static assets, with a catch-all so client-side routing (React Router)
# works on a hard refresh of any URL.
if config.FRONTEND_DIST.exists():
    assets_dir = config.FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = config.FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = config.FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend build not found. Run `npm run build` in /frontend.")
else:
    @app.get("/")
    async def frontend_not_built():
        return JSONResponse(
            status_code=200,
            content={
                "message": "Backend is running, but the frontend has not been built yet.",
                "hint": "cd frontend && npm install && npm run build, then restart the server.",
            },
        )
