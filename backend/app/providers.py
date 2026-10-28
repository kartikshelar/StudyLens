import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from .store import provider_usage_since, record_provider_usage

TEXT_MODEL = "nvidia/Nemotron-3_5-Lightning"
VISION_MODEL = "nvidia/Nemotron-3.5-Super-VL"
NEBIUS_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
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
            usage = body.get("usage", {})
            record_provider_usage(
                "nebius",
                model,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                int(usage.get("total_tokens", 0)),
            )
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ProviderError("The model returned an empty response.")
            return _json_from_model(content)
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
    return [
        {
            "url": str(item.get("url", "")),
            "title": str(item.get("title", "")),
            "snippet": str(item.get("content", "")),
        }
        for item in results
        if isinstance(item, dict) and is_primary_host(str(item.get("url", "")))
    ]


async def tavily_extract(url: str, query: str) -> str:
    if not is_primary_host(url):
        raise ProviderError("That source is outside the supported research sites.")
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
    return str(results[0].get("raw_content", ""))[:20000]
