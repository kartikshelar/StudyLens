import json

import pytest

from app import evaluate, main, providers


def test_default_evaluation_validates_all_cases_without_network(monkeypatch, capsys):
    def forbidden(**_kwargs):
        raise AssertionError("Offline validation must not open a network client")

    monkeypatch.setattr(providers.httpx, "AsyncClient", forbidden)
    assert evaluate.main([]) == 0
    assert '"validated_cases": 9' in capsys.readouterr().out


def test_live_mode_requires_explicit_case_ids():
    with pytest.raises(SystemExit) as exc:
        evaluate.main(["--live"])
    assert exc.value.code == 2


def test_abstention_does_not_pass_if_a_provider_failed():
    case = {"id": "abstain-test", "expected": {"outcome": "source_not_confirmed"}}
    report = {"status": "source_not_confirmed", "selected_source": None, "comparison": None, "error": {"stage": "source_selection"}}
    assert evaluate.score_report(case, report)["result"] == "error"


def test_scoring_checks_source_relation_and_abstract_coverage():
    case = {
        "id": "contradiction", "claim": "An intentionally contradicted research claim.", "search_query": "scaling research paper", "expected": {
            "outcome": "source_confirmed", "relation": "contradicts",
            "accepted_urls": ["https://arxiv.org/abs/2001.08361"],
            "abstract_only_urls": ["https://arxiv.org/abs/2001.08361"],
        },
    }
    report = {
        "claim": case["claim"], "search_query": case["search_query"],
        "status": "candidate_source", "selected_source": {"url": "https://arxiv.org/abs/2001.08361v1"},
        "comparison": {"relation": "contradicts", "excerpt_verified": True,
                       "supporting_excerpt": "The authors found a different relation between model size and data.", "text_coverage": "abstract_only"},
    }
    assert evaluate.score_report(case, report)["result"] == "checks_passed"
    report["comparison"]["text_coverage"] = "full_text"
    assert evaluate.score_report(case, report)["checks"]["abstract_labeled"] is False
    report["selected_source"]["url"] = "https://arxiv.org/abs/2203.15556"
    assert evaluate.score_report(case, report)["checks"]["correct_source"] is False
    report["claim"] = "A different claim from an unrelated run."
    assert evaluate.score_report(case, report)["result"] == "error"


@pytest.mark.asyncio
async def test_live_runner_stops_before_another_case_and_saves_usage_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "eval.db"))
    monkeypatch.setenv("STUDYLENS_LIVE_ENABLED", "true")
    for provider in ("NEBIUS", "TAVILY"):
        monkeypatch.setenv(f"STUDYLENS_DAILY_{provider}_CALL_LIMIT", "10")
        monkeypatch.setenv(f"STUDYLENS_TOTAL_{provider}_CALL_LIMIT", "10")

    async def fake_investigation(_payload):
        for provider in ("nebius", "tavily"):
            providers._reserve_request(provider, "offline-simulation")
            providers._reserve_request(provider, "offline-simulation")
        return {"claim": _payload.claim, "search_query": _payload.search_query,
                "status": "source_not_confirmed", "selected_source": None, "comparison": None}

    monkeypatch.setattr(main, "create_investigation", fake_investigation)
    cases = [{"id": f"abstain-{n}", "claim": "An example research claim for a test.", "search_query": "example research study",
              "expected": {"outcome": "source_not_confirmed"}} for n in range(2)]
    output = tmp_path / "results.json"
    result = await evaluate.run_live(cases, max_model_calls=2, max_tavily_requests=2, output=output)
    assert result["summary"]["checks_passed"] == 1
    assert result["summary"]["not_run"] == 1
    assert result["run_requests"] == {"nebius": 2, "tavily": 2}
    assert json.loads(output.read_text())["cases"][0]["usage"]["nebius"]["total_call_count"] == 2
