import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from .store import provider_usage_since, record_provider_usage

TEXT_MODEL = "nvidia/Nemotron-3_5-Lightning"
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


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def nebius_budget_status() -> dict[str, int]:
    limit = _bounded_env_int(
        "STUDYLENS_DAILY_NEBIUS_CALL_LIMIT",
        DEFAULT_DAILY_NEBIUS_CALL_LIMIT,
        1,
        500,
    )
    start_of_day = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    usage = provider_usage_since("nebius", start_of_day)
    return {
        **usage,
        "call_limit": limit,
        "calls_remaining": max(0, limit - usage["call_count"]),
    }


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


async def nemotron_json(messages: list[dict[str, Any]], *, vision: bool = False) -> dict[str, Any]:
    key = os.getenv("NEBIUS_API_KEY")
    if not key:
        raise ProviderError("Nebius access is not configured yet.")
    budget = nebius_budget_status()
    if budget["calls_remaining"] <= 0:
        raise ProviderError(
            "The local daily Nebius call limit has been reached. Increase it only after checking the Token Factory balance."
        )
    model = VISION_MODEL if vision else TEXT_MODEL
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
    return candidates


async def tavily_extract(url: str, query: str) -> str:
    if not research_page_url(url):
        raise ProviderError("That source is outside the supported research sites.")
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
    root = ET.fromstring(document)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        return ""
    title = " ".join((entry.findtext("atom:title", default="", namespaces=namespace)).split())
    summary = " ".join((entry.findtext("atom:summary", default="", namespaces=namespace)).split())
    authors = [
        " ".join((author.findtext("atom:name", default="", namespaces=namespace)).split())
        for author in entry.findall("atom:author", namespace)
    ]
    if not title or len(summary) < 200:
        return ""
    return f"Title: {title}\nAuthors: {', '.join(authors)}\nAbstract: {summary}"
