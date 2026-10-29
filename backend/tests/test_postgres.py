import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from app import store
from app.migrate import import_ledger


@pytest.fixture
def postgres_schema(monkeypatch):
    url = os.getenv("STUDYLENS_TEST_POSTGRES_URL", "")
    if not url:
        pytest.skip("Set STUDYLENS_TEST_POSTGRES_URL to a disposable local studylens_test database.")
    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.path != "/studylens_test":
        pytest.fail("PostgreSQL integration tests only accept localhost/studylens_test, never a hosted app database.")
    schema = "studylens_test_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    query = dict(parse_qsl(parsed.query))
    query["options"] = f"-csearch_path={schema}"
    isolated_url = urlunsplit(parsed._replace(query=urlencode(query)))
    monkeypatch.setenv("DATABASE_URL", isolated_url)
    monkeypatch.setenv("STUDYLENS_ENV", "development")
    try:
        yield isolated_url
    finally:
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_postgres_atomic_quota_and_report_persistence(postgres_schema):
    with store._database() as connection:
        connection.execute("INSERT INTO runtime_state VALUES (?, ?)", ("ledger_seeded", "true"))
    def reserve(_index):
        try:
            return store.reserve_provider_attempt("nebius", "concurrent-test", 2, 2)
        except store.QuotaExceeded:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        attempts = list(pool.map(reserve, range(8)))
    successful = [value for value in attempts if value is not None]
    assert len(successful) == 2
    store.record_provider_usage("nebius", "offline-test", 10, 5, 15, attempt_id=successful[0])
    assert store.provider_attempt_counts("nebius", "")["total_call_count"] == 2
    report = {"id": "postgres-report", "created_at": "2026-10-29", "corrections": [{"accepted": True}]}
    store.save_report(report)
    assert store.get_report(report["id"]) == report
    assert store.admit_paid_request("test-client", 600, 1, 20) == 0
    assert store.admit_paid_request("test-client", 601, 1, 20) > 0


def test_new_postgres_database_cannot_create_a_fresh_paid_allowance(postgres_schema):
    with pytest.raises(store.QuotaExceeded, match="spending history"):
        store.reserve_provider_attempt("nebius", "must-not-send", 30, 60)
    assert store.provider_attempt_counts("nebius", "")["total_call_count"] == 0


def test_postgres_migration_preserves_ids_and_advances_sequences(postgres_schema, tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(source))
    first = store.reserve_provider_attempt("nebius", "before-hosting", 10, 10)
    store.record_provider_usage("nebius", "offline-test", 10, 5, 15, attempt_id=first)
    store.save_report({"id": "migrated", "created_at": "2026-10-29"})
    monkeypatch.setenv("DATABASE_URL", postgres_schema)
    with store._database() as destination:
        import_ledger(source, destination)
    assert store.hosted_ledger_ready()
    assert store.get_report("migrated")["id"] == "migrated"
    next_attempt = store.reserve_provider_attempt("nebius", "after-hosting", 10, 10)
    assert next_attempt > first
    store.record_provider_usage("nebius", "offline-test", 10, 5, 15, attempt_id=next_attempt)
    assert store.provider_attempt_counts("nebius", "")["total_call_count"] == 2
