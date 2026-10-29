import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def validate_hosted_settings() -> None:
    if os.getenv("STUDYLENS_ENV", "development") != "production":
        return
    if not os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Production requires DATABASE_URL for persistent PostgreSQL storage; ephemeral SQLite is not permitted.")
    if len(os.getenv("STUDYLENS_RATE_LIMIT_SECRET", "")) < 32:
        raise RuntimeError("Production requires a private STUDYLENS_RATE_LIMIT_SECRET of at least 32 characters.")
    dist_value = os.getenv("STUDYLENS_WEB_DIST", "")
    dist = Path(dist_value)
    if not dist_value or not (dist / "index.html").is_file():
        raise RuntimeError("Production requires STUDYLENS_WEB_DIST pointing to the built website.")
    if os.getenv("STUDYLENS_LIVE_ENABLED", "true").strip().lower() in {"true", "1", "yes"}:
        from .store import hosted_ledger_ready
        if not hosted_ledger_ready():
            raise RuntimeError("Import the existing usage ledger before enabling hosted live requests.")


def install_website(app: FastAPI) -> None:
    validate_hosted_settings()
    dist = os.getenv("STUDYLENS_WEB_DIST")
    if dist:
        app.mount("/", StaticFiles(directory=dist, html=True), name="website")
