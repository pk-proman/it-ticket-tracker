#!/usr/bin/env python3
"""
Single entrypoint to run the whole app (backend API + built frontend) on one port.

Usage:
    python run.py

Reads configuration from .env (see .env.example). Requires the frontend to
already be built (npm install && npm run build inside /frontend) -- see
README.md for the full first-run setup.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import uvicorn

from app import config


def main():
    print(f"Starting IT Support & Maintenance Tracker on http://localhost:{config.PORT}")
    print(f"Data directory: {config.DATA_DIR}")
    if not config.FRONTEND_DIST.exists():
        print(
            "\nWARNING: frontend/dist not found. The API will run, but no UI will be served.\n"
            "Run: cd frontend && npm install && npm run build\n"
        )
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=False,
        app_dir=str(Path(__file__).resolve().parent / "backend"),
        # Behind a reverse proxy (Railway, nginx, etc.) the proxy terminates TLS
        # and forwards plain HTTP internally. Trust its X-Forwarded-Proto header
        # so request.url.scheme reads "https" -- required for SESSION_SECURE_COOKIES
        # to work at all in production; harmless when running directly on localhost.
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
