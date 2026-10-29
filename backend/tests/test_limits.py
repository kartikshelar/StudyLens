import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from app import main, providers
from app.store import QuotaExceeded, reserve_provider_attempt


@pytest.fixture(autouse=True)
def isolated_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "limits.db"))
    monkeypatch.setenv("STUDYLENS_LIVE_ENABLED", "true")
    monkeypatch.setenv("NEBIUS_API_KEY", "offline-test-only")
    monkeypatch.setenv("TAVILY_API_KEY", "offline-test-only")
    for provider in ("NEBIUS", "TAVILY"):
        monkeypatch.setenv(f"STUDYLENS_DAILY_{provider}_CALL_LIMIT", "10")
        monkeypatch.setenv(f"STUDYLENS_TOTAL_{provider}_CALL_LIMIT", "10")


def mock_provider(monkeypatch, handler):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))


def test_simultaneous_attempts_cannot_exceed_limit():
    def reserve(_index):
        try:
            return reserve_provider_attempt("nebius", "test", 3, 3)
        except QuotaExceeded:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(12)))
    assert sum(result is not None for result in results) == 3
    assert providers.nebius_budget_status()["call_count"] == 3


@pytest.mark.asyncio
async def test_timeout_consumes_slot_and_next_call_never_reaches_network(monkeypatch):
    monkeypatch.setenv("STUDYLENS_DAILY_NEBIUS_CALL_LIMIT", "1")
    network_calls = []

    def timeout(request):
        network_calls.append(request.url)
        raise httpx.ReadTimeout("simulated", request=request)

    mock_provider(monkeypatch, timeout)
    with pytest.raises(providers.ProviderError, match="timed out"):
        await providers.nemotron_json([])
    with pytest.raises(providers.ProviderLimitError, match="daily"):
        await providers.nemotron_json([])
    assert len(network_calls) == 1
    assert providers.nebius_budget_status()["calls_remaining"] == 0


@pytest.mark.asyncio
async def test_successful_usage_is_not_double_counted_and_run_cap_stops_calls(monkeypatch):
    def response(_request):
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    mock_provider(monkeypatch, response)
    with providers.request_budget(nebius=1, tavily=0) as run:
        assert await providers.nemotron_json([]) == {"ok": True}
        with pytest.raises(providers.ProviderLimitError, match="evaluation run"):
            await providers.nemotron_json([])
        assert run["nebius"]["used"] == 1
    status = providers.nebius_budget_status()
    assert status["call_count"] == 1
    assert status["total_call_count"] == 1
    assert status["total_tokens"] == 15


@pytest.mark.asyncio
async def test_tavily_search_and_extract_share_attempt_quota(monkeypatch):
    monkeypatch.setenv("STUDYLENS_DAILY_TAVILY_CALL_LIMIT", "1")
    network_calls = []

    def fail(request):
        network_calls.append(request.url)
        return httpx.Response(500)

    mock_provider(monkeypatch, fail)
    with pytest.raises(providers.ProviderError, match="Source search failed"):
        await providers.tavily_search("an example")
    with pytest.raises(providers.ProviderLimitError, match="daily"):
        await providers.tavily_extract("https://www.nature.com/articles/s41586-021-03819-2", "an example")
    assert len(network_calls) == 1
    assert providers.provider_budget_status("tavily")["call_count"] == 1


def test_total_limit_survives_utc_day_change(monkeypatch):
    monkeypatch.setenv("STUDYLENS_TOTAL_NEBIUS_CALL_LIMIT", "1")
    reserve_provider_attempt("nebius", "test", 10, 1)
    with sqlite3.connect(providers.os.getenv("STUDYLENS_DB_PATH")) as connection:
        connection.execute("UPDATE provider_attempts SET created_at = '2020-01-01T00:00:00+00:00'")
    status = providers.nebius_budget_status()
    assert status["call_count"] == 0
    assert status["total_call_count"] == 1
    assert status["calls_remaining"] == 0
    with pytest.raises(QuotaExceeded, match="total"):
        reserve_provider_attempt("nebius", "test", 10, 1)


def test_zero_limit_blocks_first_attempt(monkeypatch):
    monkeypatch.setenv("STUDYLENS_DAILY_NEBIUS_CALL_LIMIT", "0")
    assert providers.nebius_budget_status()["calls_remaining"] == 0
    with pytest.raises(providers.ProviderLimitError):
        providers._reserve_request("nebius", "test")
    assert providers.nebius_budget_status()["call_count"] == 0


@pytest.mark.asyncio
async def test_paused_mode_blocks_paid_routes_but_saved_reports_still_open(monkeypatch):
    monkeypatch.setenv("STUDYLENS_LIVE_ENABLED", "false")
    main.save_report({"id": "saved", "created_at": "2026-10-28", "status": "source_not_confirmed"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/api/claims/extract-text", json={"text": "A long enough scientific research claim."})
        assert response.status_code == 503
        assert (await client.get("/api/investigations/saved")).status_code == 200
    assert providers.nebius_budget_status()["call_count"] == 0


@pytest.mark.asyncio
async def test_rate_limit_rejects_repeated_requests_before_any_provider_call(monkeypatch):
    monkeypatch.setenv("STUDYLENS_REQUESTS_PER_MINUTE", "1")
    monkeypatch.setenv("STUDYLENS_REQUESTS_PER_HOUR", "10")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        # Invalid input consumes an HTTP slot but cannot invoke a paid provider.
        assert (await client.post("/api/claims/extract-text", json={"text": "short"})).status_code == 422
        blocked = await client.post("/api/claims/extract-text", json={"text": "short"})
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) > 0
        assert (await client.get("/api/health")).status_code == 200
    assert providers.nebius_budget_status()["call_count"] == 0
