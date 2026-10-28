from app.providers import nebius_budget_status
from app.store import record_provider_usage


def test_nebius_daily_call_limit_is_persistent(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "budget.db"))
    monkeypatch.setenv("STUDYLENS_DAILY_NEBIUS_CALL_LIMIT", "2")

    initial = nebius_budget_status()
    assert initial["call_count"] == 0
    assert initial["calls_remaining"] == 2

    record_provider_usage("nebius", "test-model", 10, 5, 15)
    used = nebius_budget_status()
    assert used["call_count"] == 1
    assert used["total_tokens"] == 15
    assert used["calls_remaining"] == 1

    record_provider_usage("nebius", "test-model", 8, 2, 10)
    exhausted = nebius_budget_status()
    assert exhausted["call_count"] == 2
    assert exhausted["calls_remaining"] == 0
