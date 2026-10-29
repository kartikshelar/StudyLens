import json
import os
import re
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from .store import (
    QuotaExceeded,
    provider_attempt_counts,
    provider_usage_since,
    record_provider_usage,
    reserve_provider_attempt,
)

TEXT_MODEL = "nvidia/Nemotron-3_5-Lightning"
COMPARE_MODEL = "nvidia/nemotron-3-super-120b-a12b"
VISION_MODEL = "nvidia/Nemotron-3.5-Super-VL"
NEBIUS_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
DEFAULT_NEBIUS_MAX_OUTPUT_TOKENS = 800
DEFAULT_DAILY_NEBIUS_CALL_LIMIT = 30

# A narrow first-release source set. The matching model must still inspect the
# content; being on one of these hosts alone never proves a claim.
PRIMARY_HOSTS = (
    "arxiv.org",
    "openreview.net",
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "biorxiv.org",
    "medrxiv.org",
    "journals.plos.org",
    "nature.com",
    "science.org",
    "pnas.org",
    "acm.org",
    "ieeexplore.ieee.org",
)


class ProviderError(Exception):
    pass


class ProviderLimitError(ProviderError):
    pass


_run_budget: ContextVar[dict[str, dict[str, int]] | None] = ContextVar("provider_run_budget", default=None)


@contextmanager
def request_budget(*, nebius: int, tavily: int):
    """An additional per-run ceiling for the evaluation CLI; never changes global limits."""
    budget = {
        "nebius": {"limit": max(0, nebius), "used": 0},
        "tavily": {"limit": max(0, tavily), "used": 0},
    }
    token = _run_budget.set(budget)
    try:
        yield budget
    finally:
        _run_budget.reset(token)


def live_enabled() -> bool:
    return os.getenv("STUDYLENS_LIVE_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def provider_budget_status(provider: str) -> dict[str, int]:
    defaults = {"nebius": (DEFAULT_DAILY_NEBIUS_CALL_LIMIT, 60), "tavily": (20, 40)}
    daily_default, total_default = defaults[provider]
    prefix = provider.upper()
    limit = _bounded_env_int(f"STUDYLENS_DAILY_{prefix}_CALL_LIMIT", daily_default, 0, 500)
    total_limit = _bounded_env_int(f"STUDYLENS_TOTAL_{prefix}_CALL_LIMIT", total_default, 0, 1000)
    start_of_day = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    usage = provider_usage_since(provider, start_of_day)
    attempts = provider_attempt_counts(provider, start_of_day)
    return {
        **usage,
        **attempts,
        "call_limit": limit,
        "total_call_limit": total_limit,
        "calls_remaining": max(0, min(limit - attempts["call_count"], total_limit - attempts["total_call_count"])),
    }


def nebius_budget_status() -> dict[str, int]:
    return provider_budget_status("nebius")


def _reserve_request(provider: str, operation: str) -> int:
    if not live_enabled():
        raise ProviderLimitError("Live research is paused by the project owner.")
    budget = _run_budget.get()
    if budget is not None and budget[provider]["used"] >= budget[provider]["limit"]:
        raise ProviderLimitError(f"The evaluation run's {provider.title()} request limit has been reached.")
    status = provider_budget_status(provider)
    try:
        attempt_id = reserve_provider_attempt(provider, operation, status["call_limit"], status["total_call_limit"])
    except QuotaExceeded as exc:
        raise ProviderLimitError(str(exc)) from exc
    if budget is not None:
        budget[provider]["used"] += 1
    return attempt_id


def configured() -> dict[str, bool]:
    return {
        "nebius": bool(os.getenv("NEBIUS_API_KEY")),
        "tavily": bool(os.getenv("TAVILY_API_KEY")),
    }


def is_primary_host(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == allowed or host.endswith("." + allowed) for allowed in PRIMARY_HOSTS
    )


def research_page_url(url: str) -> str | None:
    """Return a supported paper URL, excluding known news and listing pages."""
    if not is_primary_host(url):
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if host == "ar5iv.labs.arxiv.org":
        match = re.fullmatch(r"/html/(\d{4}\.\d{4,5})(?:v\d+)?", path)
        return f"https://arxiv.org/abs/{match.group(1)}" if match else None
    if host == "cacm.acm.org":
        return None
    if host.endswith("nature.com") and path.startswith("/articles/d41586-"):
        return None
    if host.endswith("science.org") and path.startswith("/content/"):
        return None
    if host in {"arxiv.org", "www.arxiv.org"}:
        match = re.fullmatch(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", path)
        if not match:
            return None
        return f"https://arxiv.org/abs/{match.group(1)}"
    if host == "pubmed.ncbi.nlm.nih.gov" and not re.fullmatch(r"/\d+", path):
        return None
    if host == "pmc.ncbi.nlm.nih.gov" and not re.fullmatch(r"/articles/PMC\d+", path, re.I):
        return None
    if host == "openreview.net":
        paper_id = parse_qs(parsed.query).get("id", [""])[0]
        if path != "/forum" or not paper_id:
            return None
        return urlunparse(("https", host, path, "", urlencode({"id": paper_id}), ""))
    return urlunparse((parsed.scheme, parsed.netloc, path or "/", "", "", ""))


def _json_from_model(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderError("The model did not return usable structured data.") from exc
    if not isinstance(value, dict):
        raise ProviderError("The model returned the wrong data shape.")
    return value


async def nemotron_json(messages: list[dict[str, Any]], *, vision: bool = False, model: str | None = None) -> dict[str, Any]:
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        raise ProviderError("Nebius access is not configured yet.")
    model = model or (VISION_MODEL if vision else TEXT_MODEL)
    if model not in {TEXT_MODEL, COMPARE_MODEL, VISION_MODEL}:
        raise ProviderError("The requested model is outside the project's configured model set.")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": _bounded_env_int(
            "NEBIUS_MAX_OUTPUT_TOKENS",
            DEFAULT_NEBIUS_MAX_OUTPUT_TOKENS,
            64,
            1600,
        ),
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"},
    }
    attempt_id = _reserve_request("nebius", model)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                NEBIUS_URL,
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            usage = body.get("usage") or {}
            record_provider_usage(
                "nebius",
                model,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                int(usage.get("total_tokens", 0)),
                attempt_id=attempt_id,
            )
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("The model response reached its output limit before completing JSON.")
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ProviderError("The model returned an empty response.")
            return _json_from_model(content)
    except httpx.TimeoutException as exc:
        raise ProviderError("Nebius inference timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise ProviderError(f"Nebius inference returned HTTP {exc.response.status_code}.") from exc
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise ProviderError("Nebius inference failed. Check access and try again.") from exc


async def tavily_search(query: str) -> list[dict[str, str]]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise ProviderError("Tavily access is not configured yet.")
    _reserve_request("tavily", "search")
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                TAVILY_SEARCH_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 8,
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_domains": list(PRIMARY_HOSTS),
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError("Source search failed. Please try again.") from exc
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        url = research_page_url(str(item.get("url", "")))
        if not url or url in seen:
            continue
        seen.add(url)
        candidates.append(
            {
                "url": url,
                "title": str(item.get("title", "")),
                "snippet": str(item.get("content", "")),
            }
        )
    return await _resolve_arxiv_candidates(candidates)


async def _resolve_arxiv_candidates(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    """Resolve paper identity and at most three explicit arXiv citations, in one free API read."""
    direct_ids = [item["url"].rsplit("/", 1)[-1] for item in candidates
                  if urlparse(item["url"]).hostname == "arxiv.org"]
    citation_ids = []
    for candidate in candidates:
        for paper_id in re.findall(r"(?:arxiv\s*:\s*|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5})", candidate["snippet"], re.I):
            if paper_id not in direct_ids and paper_id not in citation_ids and len(citation_ids) < 3:
                citation_ids.append(paper_id)
    ids = list(dict.fromkeys(direct_ids + citation_ids))
    if not ids:
        return candidates
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(ARXIV_API_URL, params={"id_list": ",".join(ids)})
            response.raise_for_status()
        records = _parse_arxiv_records(response.text)
    except (httpx.HTTPError, ET.ParseError):
        return candidates
    resolved = []
    seen = set()
    for candidate in candidates:
        record = records.get(candidate["url"])
        resolved.append({**candidate, **record} if record else candidate)
        seen.add(candidate["url"])
    for paper_id in citation_ids:
        url = f"https://arxiv.org/abs/{paper_id}"
        if url in records and url not in seen:
            resolved.append({**records[url], "discovery": "arXiv citation in a search result"})
            seen.add(url)
    return resolved


async def tavily_extract(url: str, query: str) -> str:
    canonical_url = research_page_url(url)
    if not canonical_url:
        raise ProviderError("That source is outside the supported research sites.")
    url = canonical_url
    parsed = urlparse(url)
    if parsed.hostname == "arxiv.org":
        arxiv_id = parsed.path.removeprefix("/abs/")
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.get(ARXIV_API_URL, params={"id_list": arxiv_id})
                response.raise_for_status()
            abstract = _parse_arxiv_atom(response.text)
            if abstract:
                return abstract
        except (httpx.HTTPError, ET.ParseError):
            pass
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise ProviderError("Tavily access is not configured yet.")
    _reserve_request("tavily", "extract")
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                TAVILY_EXTRACT_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={"urls": [url], "query": query, "extract_depth": "advanced"},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError("The source could not be retrieved.") from exc
    if not results:
        raise ProviderError("The source could not be retrieved.")
    text = str(results[0].get("raw_content", ""))[:20000]
    if parsed.hostname == "arxiv.org" and not re.search(r"(?im)^\s*(?:#+\s*)?abstract\b", text):
        raise ProviderError("The arXiv page did not expose its abstract text.")
    return text


def _parse_arxiv_atom(document: str) -> str:
    records = _parse_arxiv_records(document)
    return next(iter(records.values()))["source_text"] if records else ""


def _parse_arxiv_records(document: str) -> dict[str, dict[str, str]]:
    root = ET.fromstring(document)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    records = {}
    for entry in root.findall("atom:entry", namespace):
        title = " ".join(entry.findtext("atom:title", default="", namespaces=namespace).split())
        summary = " ".join(entry.findtext("atom:summary", default="", namespaces=namespace).split())
        identifier = entry.findtext("atom:id", default="", namespaces=namespace)
        match = re.search(r"/(\d{4}\.\d{4,5})(?:v\d+)?$", identifier)
        if not match or not title or len(summary) < 200:
            continue
        url = f"https://arxiv.org/abs/{match.group(1)}"
        authors = ", ".join(" ".join(author.findtext("atom:name", default="", namespaces=namespace).split())
                            for author in entry.findall("atom:author", namespace))
        published = entry.findtext("atom:published", default="", namespaces=namespace)[:10]
        source_text = f"Title: {title}\nAuthors: {authors}\nFirst submitted: {published}\nAbstract: {summary}"
        records[url] = {
            "url": url, "title": title, "authors": authors, "published": published,
            "snippet": f"Authors: {authors}\nFirst submitted: {published}\nAbstract: {summary}",
            "source_text": source_text, "metadata_source": "arxiv_api",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    return records
