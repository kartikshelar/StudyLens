import httpx
import psycopg
import pytest
from fastapi import FastAPI

from app import runtime, store


@pytest.mark.asyncio
async def test_built_site_and_api_share_one_origin_without_shadowing_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_ENV", "development")
    monkeypatch.setenv("STUDYLENS_WEB_DIST", str(tmp_path))
    (tmp_path / "index.html").write_text("<h1>StudyLens production build</h1>")
    test_app = FastAPI()

    @test_app.get("/api/test")
    def api():
        return {"api": True}

    runtime.install_website(test_app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        assert "StudyLens production build" in (await client.get("/")).text
        assert (await client.get("/api/test")).json() == {"api": True}
        assert (await client.get("/api/not-a-route")).status_code == 404


def test_production_refuses_ephemeral_storage_and_requires_migrated_spending_history(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_ENV", "production")
    with pytest.raises(RuntimeError, match="persistent PostgreSQL"):
        runtime.validate_hosted_settings()
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/studylens_test")
    monkeypatch.setenv("STUDYLENS_RATE_LIMIT_SECRET", "test-only-secret-which-is-long-enough")
    monkeypatch.setenv("STUDYLENS_WEB_DIST", str(tmp_path))
    (tmp_path / "index.html").write_text("Built site")
    monkeypatch.setenv("STUDYLENS_LIVE_ENABLED", "true")
    monkeypatch.setattr(store, "hosted_ledger_ready", lambda: False)
    with pytest.raises(RuntimeError, match="usage ledger"):
        runtime.validate_hosted_settings()
    monkeypatch.setenv("STUDYLENS_LIVE_ENABLED", "false")
    runtime.validate_hosted_settings()
    monkeypatch.setenv("STUDYLENS_LIVE_ENABLED", "true")
    monkeypatch.setattr(store, "hosted_ledger_ready", lambda: True)
    runtime.validate_hosted_settings()


def test_database_failure_cannot_fall_back_to_fresh_local_counters(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/studylens_test")
    local_path = tmp_path / "must-not-be-created.db"
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(local_path))

    def unavailable(*_args, **_kwargs):
        raise psycopg.OperationalError("test database unavailable")

    monkeypatch.setattr(store.psycopg, "connect", unavailable)
    with pytest.raises(psycopg.OperationalError):
        store.provider_attempt_counts("nebius", "")
    assert not local_path.exists()
