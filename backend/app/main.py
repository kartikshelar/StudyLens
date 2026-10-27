import base64
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .providers import (
    ProviderError,
    TEXT_MODEL,
    VISION_MODEL,
    configured,
    nemotron_json,
    is_primary_host,
    tavily_extract,
    tavily_search,
)
from .store import get_report, save_report

load_dotenv()
app = FastAPI(title="StudyLens API", version="0.1.0")
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


class TextInput(BaseModel):
    text: str = Field(min_length=20, max_length=4000)


class InvestigationInput(BaseModel):
    claim: str = Field(min_length=15, max_length=1200)
    search_query: str = Field(min_length=5, max_length=500)


class SourceCorrection(BaseModel):
    source_url: str = Field(min_length=12, max_length=2000)


def _problem(exc: ProviderError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


def _clean_text(value: Any, limit: int = 1600) -> str:
    return str(value or "").strip()[:limit]


def _excerpt_in_source(excerpt: str, source: str) -> bool:
    normalize = lambda text: re.sub(r"\s+", " ", text).strip().casefold()
    return bool(excerpt) and normalize(excerpt) in normalize(source)


async def _compare(claim: str, source_title: str, source_text: str) -> dict[str, Any]:
    prompt = (
        "You are checking whether a research source supports a public claim. "
        "Use only the supplied source text. Return JSON only with fields "
        "supporting_excerpt (an exact contiguous quote from source text, or empty), "
        "study_tested, study_found, wording_gap, uncertainties (array of strings). "
        "If the source does not clearly address the claim, leave supporting_excerpt empty. "
        "Do not infer unstated sample sizes, causal effects, or numerical results."
    )
    result = await nemotron_json(
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Public claim: {claim}\nSource title: {source_title}\nSource text:\n{source_text[:14000]}",
            },
        ]
    )
    excerpt = _clean_text(result.get("supporting_excerpt"), 1200)
    supported_quote = _excerpt_in_source(excerpt, source_text)
    return {
        "supporting_excerpt": excerpt if supported_quote else "",
        "study_tested": _clean_text(result.get("study_tested")) if supported_quote else "",
        "study_found": _clean_text(result.get("study_found")) if supported_quote else "",
        "wording_gap": _clean_text(result.get("wording_gap")) if supported_quote else "",
        "uncertainties": [
            _clean_text(item, 400)
            for item in result.get("uncertainties", [])
            if isinstance(item, str)
        ][:5]
        if supported_quote
        else [],
        "excerpt_verified": supported_quote,
    }


async def _assess_candidate(report: dict[str, Any], candidate: dict[str, str]) -> None:
    try:
        source_text = await tavily_extract(candidate["url"], report["claim"])
        if len(source_text.strip()) < 200:
            raise ProviderError("The source has too little accessible text to inspect.")
        comparison = await _compare(report["claim"], candidate["title"], source_text)
    except ProviderError as exc:
        report["status"] = "source_not_confirmed"
        report["message"] = str(exc)
        report["selected_source"] = None
        report["comparison"] = None
        return
    report["trace"].append("Tavily Extract retrieved the candidate source")
    report["trace"].append(f"{TEXT_MODEL} compared the claim with retrieved text")
    if not comparison["excerpt_verified"]:
        report["status"] = "source_not_confirmed"
        report["message"] = "The candidate source did not provide a verifiable supporting passage."
        report["selected_source"] = None
        report["comparison"] = None
        return
    report["status"] = "candidate_source"
    report["message"] = "A candidate study was found. Inspect the source before relying on this comparison."
    report["selected_source"] = candidate
    report["comparison"] = comparison


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "providers_configured": configured()}


@app.post("/api/claims/extract-text")
async def extract_text(payload: TextInput) -> dict[str, str]:
    try:
        result = await nemotron_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract one checkable science or technology research claim from the user text. "
                        "Return JSON only with claim and search_query strings. "
                        "Preserve numbers, populations, and uncertainty words exactly. "
                        "Do not add claims not present in the input."
                    ),
                },
                {"role": "user", "content": payload.text},
            ]
        )
    except ProviderError as exc:
        raise _problem(exc) from exc
    claim = _clean_text(result.get("claim"), 1200)
    query = _clean_text(result.get("search_query"), 500)
    if len(claim) < 15 or len(query) < 5:
        raise HTTPException(status_code=422, detail="No checkable research claim was found.")
    return {"claim": claim, "search_query": query, "model": TEXT_MODEL}


@app.post("/api/claims/extract-image")
async def extract_image(image: UploadFile = File(...)) -> dict[str, str]:
    if image.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, or WebP screenshot.")
    data = await image.read(5_000_001)
    if len(data) > 5_000_000:
        raise HTTPException(status_code=413, detail="Screenshots must be smaller than 5 MB.")
    encoded = base64.b64encode(data).decode("ascii")
    try:
        result = await nemotron_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Read this screenshot. Extract one visible, checkable claim about a research result. "
                        "Return JSON only with claim and search_query strings. "
                        "Preserve numbers and qualifiers exactly. Never invent text that is not visible."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What research claim is visible?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{image.content_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            vision=True,
        )
    except ProviderError as exc:
        raise _problem(exc) from exc
    claim = _clean_text(result.get("claim"), 1200)
    query = _clean_text(result.get("search_query"), 500)
    if len(claim) < 15 or len(query) < 5:
        raise HTTPException(status_code=422, detail="No visible research claim was found.")
    return {"claim": claim, "search_query": query, "model": VISION_MODEL}


@app.post("/api/investigations")
async def create_investigation(payload: InvestigationInput) -> dict[str, Any]:
    report: dict[str, Any] = {
        "id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim": payload.claim.strip(),
        "search_query": payload.search_query.strip(),
        "status": "source_not_confirmed",
        "message": "No primary source was confirmed.",
        "candidates": [],
        "selected_source": None,
        "comparison": None,
        "trace": [],
        "corrections": [],
    }
    try:
        candidates = await tavily_search(report["search_query"])
        report["trace"].append("Tavily Search returned candidate research pages")
        report["candidates"] = candidates
        if candidates:
            selection = await nemotron_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "Choose the candidate ORIGINAL STUDY that most likely matches the public claim. "
                            "Use only the provided candidates. Return JSON only with index (zero-based integer, "
                            "or -1 if no defensible match) and reason (one sentence). "
                            "A shared topic alone is not enough; the population and result must align."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Claim: {report['claim']}\nCandidates: {candidates}",
                    },
                ]
            )
            report["trace"].append(f"{TEXT_MODEL} selected a source candidate")
            index = selection.get("index", -1)
            if isinstance(index, int) and 0 <= index < len(candidates):
                report["selection_reason"] = _clean_text(selection.get("reason"), 500)
                await _assess_candidate(report, candidates[index])
            else:
                report["message"] = "Search found research pages, but none clearly matched this claim."
    except ProviderError as exc:
        raise _problem(exc) from exc
    save_report(report)
    return report


@app.get("/api/investigations/{report_id}")
def read_investigation(report_id: str) -> dict[str, Any]:
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="This investigation was not found.")
    return report


@app.put("/api/investigations/{report_id}/source")
async def correct_source(report_id: str, payload: SourceCorrection) -> dict[str, Any]:
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="This investigation was not found.")
    source_url = payload.source_url.strip()
    if not is_primary_host(source_url):
        raise HTTPException(status_code=422, detail="Add a public HTTPS link from a supported research site.")
    candidate = next(
        (item for item in report["candidates"] if item["url"] == source_url), None
    )
    if not candidate:
        candidate = {
            "url": source_url,
            "title": urlparse(source_url).hostname or source_url,
            "snippet": "Source added by the reader; inspect the extracted passage.",
        }
        report["candidates"].append(candidate)
    previous = report.get("selected_source")
    await _assess_candidate(report, candidate)
    report["selection_reason"] = "Reader-supplied source; the extracted passage was checked against the claim."
    report["corrections"].append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "previous_url": previous["url"] if previous else None,
            "new_url": candidate["url"],
        }
    )
    save_report(report)
    return report
