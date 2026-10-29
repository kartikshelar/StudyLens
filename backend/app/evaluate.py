"""Validate cases or score saved reports offline; live evaluation requires --live."""

import argparse
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .providers import ProviderError, provider_budget_status, request_budget, research_page_url
from .store import provider_usage_since

EVALUATION_DIR = Path(__file__).resolve().parents[2] / "evaluation"


def load_cases(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or not isinstance(document.get("cases"), list):
        raise ValueError("Expected evaluation schema version 1 and a cases array.")
    cases = document["cases"]
    seen = set()
    for case in cases:
        case_id = case.get("id", "")
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9-]+", case_id) or case_id in seen:
            raise ValueError("Each case needs a unique lowercase id.")
        seen.add(case_id)
        for field, minimum, maximum in (("claim", 15, 1200), ("search_query", 5, 500)):
            value = case.get(field)
            if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
                raise ValueError(f"{case_id}: invalid {field}.")
        expected = case.get("expected", {})
        if expected.get("outcome") not in {"source_confirmed", "source_not_confirmed"}:
            raise ValueError(f"{case_id}: invalid expected outcome.")
        urls = expected.get("accepted_urls", [])
        if not isinstance(urls, list) or any(not isinstance(url, str) or not research_page_url(url) for url in urls):
            raise ValueError(f"{case_id}: invalid accepted URLs.")
        if expected["outcome"] == "source_confirmed":
            if not urls or expected.get("relation") not in {"supports", "partly_supports", "contradicts"}:
                raise ValueError(f"{case_id}: source cases need accepted URLs and a relation.")
    return cases


def score_report(case: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Score machine-checkable properties only; substantive evidence review stays pending."""
    result: dict[str, Any] = {"case_id": case["id"], "human_review": "pending"}
    if report.get("error"):
        return {**result, "result": "error", "error": report["error"], "checks": {}}
    if any(report.get(field) != case.get(field) for field in ("claim", "search_query")):
        return {**result, "result": "error", "error": "Report inputs do not match this fixed evaluation case.", "checks": {}}
    expected = case["expected"]
    source = report.get("selected_source")
    comparison = report.get("comparison") or {}
    if expected["outcome"] == "source_not_confirmed":
        checks = {
            "abstained": report.get("status") == "source_not_confirmed",
            "no_selected_source": source is None,
            "no_comparison": report.get("comparison") is None,
        }
    else:
        selected_url = research_page_url(source.get("url", "")) if isinstance(source, dict) else None
        accepted = {research_page_url(url) for url in expected["accepted_urls"]}
        abstract_only = {research_page_url(url) for url in expected.get("abstract_only_urls", [])}
        excerpt = comparison.get("supporting_excerpt")
        checks = {
            "source_found": report.get("status") == "candidate_source",
            "correct_source": selected_url is not None and selected_url in accepted,
            "correct_relation": comparison.get("relation") == expected["relation"],
            # This records the application's check, not an independent source fetch.
            "application_quote_check": comparison.get("excerpt_verified") is True
            and isinstance(excerpt, str) and len(excerpt.split()) >= 8,
            "abstract_labeled": selected_url not in abstract_only or comparison.get("text_coverage") == "abstract_only",
        }
    return {
        **result,
        "result": "checks_passed" if all(checks.values()) else "checks_failed",
        "checks": checks,
        "manual_checks": ["Original authors' own result", "Summary supported by source", "Wording gap and limitations"],
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cases": len(rows),
        **{kind: sum(row["result"] == kind for row in rows)
           for kind in ("checks_passed", "checks_failed", "error", "not_run")},
        "human_reviews_completed": 0,
    }


def _write(output: Path | None, result: dict[str, Any]) -> None:
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run_live(cases, *, max_model_calls: int, max_tavily_requests: int, output: Path):
    # Import the app only in explicit live mode. Offline validation never loads .env.
    from fastapi import HTTPException
    from .main import InvestigationInput, create_investigation

    result = {
        "mode": "live", "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "Small diagnostic set; automated checks are not a real-world accuracy estimate. Human review pending.",
        "limits": {"nebius": max_model_calls, "tavily": max_tavily_requests},
        "cases": [],
    }
    with request_budget(nebius=max_model_calls, tavily=max_tavily_requests) as budget:
        for case in cases:
            # Allow worst-case two calls to each provider before starting another case.
            if any(budget[p]["limit"] - budget[p]["used"] < 2 or provider_budget_status(p)["calls_remaining"] < 2
                   for p in ("nebius", "tavily")):
                result["cases"].append({"case_id": case["id"], "result": "not_run", "reason": "Insufficient remaining request allowance."})
            else:
                before = {p: provider_budget_status(p) for p in ("nebius", "tavily")}
                usage_start = datetime.now(timezone.utc).isoformat()
                started = time.perf_counter()
                try:
                    report = await create_investigation(InvestigationInput(claim=case["claim"], search_query=case["search_query"]))
                    row = {**score_report(case, report), "report": report}
                except (ProviderError, HTTPException) as exc:
                    row = {"case_id": case["id"], "result": "error", "error": str(getattr(exc, "detail", exc))}
                row["latency_seconds"] = round(time.perf_counter() - started, 3)
                after = {p: provider_budget_status(p) for p in ("nebius", "tavily")}
                row["usage"] = {
                    p: {"total_call_count": after[p]["total_call_count"] - before[p]["total_call_count"]}
                    for p in ("nebius", "tavily")
                }
                row["usage"]["nebius"].update({
                    key: value for key, value in provider_usage_since("nebius", usage_start).items()
                    if key != "call_count"
                })
                result["cases"].append(row)
            result["summary"] = summarize(result["cases"])
            result["run_requests"] = {p: values["used"] for p, values in budget.items()}
            _write(output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=EVALUATION_DIR / "cases.json")
    parser.add_argument("--case-id", action="append", default=[])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Explicitly permit paid provider calls.")
    mode.add_argument("--reports-dir", type=Path, help="Offline replay: one <case-id>.json report per case.")
    parser.add_argument("--max-cases", type=int, default=2)
    parser.add_argument("--max-model-calls", type=int, default=4)
    parser.add_argument("--max-tavily-requests", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.cases)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    unknown = set(args.case_id) - {case["id"] for case in cases}
    if unknown:
        parser.error(f"Unknown cases: {', '.join(sorted(unknown))}")
    if args.case_id:
        cases = [case for case in cases if case["id"] in args.case_id]
    if args.live:
        if not args.case_id:
            parser.error("Live runs require explicit --case-id values.")
        if not 1 <= args.max_cases <= 9 or len(cases) > args.max_cases:
            parser.error("Selected cases exceed --max-cases (default 2).")
        if not 2 <= args.max_model_calls <= 18 or not 2 <= args.max_tavily_requests <= 18:
            parser.error("Live per-run request caps must be between 2 and 18.")
        output = args.output or EVALUATION_DIR / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        result = asyncio.run(run_live(cases, max_model_calls=args.max_model_calls, max_tavily_requests=args.max_tavily_requests, output=output))
        print(f"Saved results: {output}")
    elif args.reports_dir:
        rows = []
        for case in cases:
            path = args.reports_dir / f"{case['id']}.json"
            if not path.exists():
                rows.append({"case_id": case["id"], "result": "not_run", "reason": "No saved report."})
                continue
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
                rows.append({**score_report(case, report), "report": report})
            except (ValueError, TypeError, AttributeError) as exc:
                rows.append({"case_id": case["id"], "result": "error", "error": str(exc)})
        result = {"mode": "offline_replay", "cases": rows, "summary": summarize(rows)}
        _write(args.output, result)
    else:
        result = {"mode": "offline_validation", "validated_cases": len(cases), "provider_calls": 0}
        _write(args.output, result)
    print(json.dumps(result.get("summary", result), indent=2))
    return int(any(row["result"] in {"checks_failed", "error"} for row in result.get("cases", [])))


if __name__ == "__main__":
    raise SystemExit(main())
