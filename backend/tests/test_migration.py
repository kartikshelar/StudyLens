import pytest

from app import store
from app.migrate import import_ledger


def test_migration_preserves_reports_corrections_and_spending_history(tmp_path, monkeypatch):
    source_path = tmp_path / "source.db"
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(source_path))
    attempt = store.reserve_provider_attempt("nebius", "test", 2, 2)
    store.record_provider_usage("nebius", "test-model", 10, 5, 15, attempt_id=attempt)
    report = {"id": "original-report", "created_at": "2026-10-28", "corrections": [{"previous_url": "old", "new_url": "new"}]}
    store.save_report(report)
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "destination.db"))
    with store._database() as destination:
        counts = import_ledger(source_path, destination)
    assert counts == {"investigations": 1, "provider_usage": 1, "provider_attempts": 1}
    assert store.get_report(report["id"]) == report
    assert store.provider_attempt_counts("nebius", "")["total_call_count"] == 1
    assert store.provider_usage_since("nebius", "")["total_tokens"] == 15
    assert store.hosted_ledger_ready()
    assert store.reserve_provider_attempt("nebius", "next", 2, 2) > attempt


def test_migration_refuses_an_existing_destination_without_overwriting_it(tmp_path, monkeypatch):
    source_path = tmp_path / "source.db"
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(source_path))
    store.save_report({"id": "source", "created_at": "2026-10-28"})
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "destination.db"))
    existing = {"id": "existing", "created_at": "2026-10-28"}
    store.save_report(existing)
    with pytest.raises(ValueError, match="not empty"):
        with store._database() as destination:
            import_ledger(source_path, destination)
    assert store.get_report("existing") == existing
    assert store.get_report("source") is None
