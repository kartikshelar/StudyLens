import httpx
import pytest

from app import main, providers


def atom_entry(paper_id, title, author, published):
    summary = "The authors tested how language model size and training data influence the result under a fixed compute budget. " * 3
    return f"<entry><id>http://arxiv.org/abs/{paper_id}v1</id><title>{title}</title><author><name>{author}</name></author><published>{published}T00:00:00Z</published><summary>{summary}</summary></entry>"


@pytest.mark.asyncio
async def test_search_follows_explicit_citations_with_a_bounded_free_metadata_request(monkeypatch):
    calls = []

    def response(request):
        calls.append(request)
        assert request.url.host == "export.arxiv.org"
        assert request.url.params["id_list"].split(",") == ["2203.15556", "2001.08361", "1412.6980", "1808.06226"]
        body = '<feed xmlns="http://www.w3.org/2005/Atom">' + atom_entry("2203.15556", "Training Compute-Optimal Large Language Models", "Jordan Hoffmann", "2022-03-29") + atom_entry("2001.08361", "Scaling Laws for Neural Language Models", "Jared Kaplan", "2020-01-23") + '</feed>'
        return httpx.Response(200, text=body)

    original_client = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(response), **kwargs))
    candidates = [{"url": "https://arxiv.org/abs/2203.15556", "title": "[2203.15556] Search title",
                   "snippet": "References: arXiv:2001.08361, arXiv:1412.6980, arXiv:1808.06226, arXiv:9999.99999"}]
    resolved = await providers._resolve_arxiv_candidates(candidates)
    assert len(calls) == 1
    assert len(resolved) == 2
    assert resolved[0]["title"] == "Training Compute-Optimal Large Language Models"
    assert resolved[1]["authors"] == "Jared Kaplan"
    assert resolved[1]["discovery"] == "arXiv citation in a search result"
    assert "Abstract:" in resolved[1]["source_text"]


def test_identity_guards_reject_later_papers_and_wrong_authors_but_allow_earlier_preprints():
    claim = "Kaplan and colleagues' 2020 scaling paper found a particular relation."
    candidate = {"metadata_source": "arxiv_api", "published": "2022-03-29", "authors": "Jordan Hoffmann"}
    assert "after" in main._identity_conflict(claim, candidate)
    candidate["published"] = "2020-01-23"
    assert "Kaplan" in main._identity_conflict(claim, candidate)
    candidate.update(published="2019-01-23", authors="Jared Kaplan")
    assert main._identity_conflict(claim, candidate) is None


@pytest.mark.asyncio
async def test_only_conflicting_candidates_abstains_without_model_call(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "identity.db"))

    async def search(_query):
        return [{"url": "https://arxiv.org/abs/2203.15556", "title": "Later paper", "snippet": "A related result.",
                 "metadata_source": "arxiv_api", "published": "2022-03-29", "authors": "Jordan Hoffmann"}]

    async def forbidden(*_args, **_kwargs):
        raise AssertionError("A clear metadata conflict must not invoke the model")

    monkeypatch.setattr(main, "tavily_search", search)
    monkeypatch.setattr(main, "nemotron_json", forbidden)
    report = await main.create_investigation(main.InvestigationInput(claim="Kaplan and colleagues' 2020 paper found equal scaling.", search_query="Kaplan scaling paper"))
    assert report["status"] == "source_not_confirmed"
    assert report["selected_source"] is None
    assert len(report["source_exclusions"]) == 1
    assert "error" not in report


@pytest.mark.asyncio
async def test_named_original_can_be_selected_and_shown_as_contradicting(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "contradiction.db"))
    quote = "Larger models are more sample efficient and should use relatively modest amounts of training data."
    source = {"url": "https://arxiv.org/abs/2001.08361", "title": "Scaling Laws for Neural Language Models", "snippet": quote,
              "metadata_source": "arxiv_api", "published": "2020-01-23", "authors": "Jared Kaplan",
              "source_text": quote * 6, "discovery": "arXiv citation in a search result"}

    async def search(_query):
        return [source]

    calls = 0

    async def model(_messages, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"index": 0, "url": source["url"], "source_type": "original_study", "reason": "A model-generated rationale."}
        return {"is_original_study": True, "relation": "contradicts", "supporting_excerpt": quote}

    async def forbidden(*_args):
        raise AssertionError("Use the already retrieved official abstract, without another extraction")

    monkeypatch.setattr(main, "tavily_search", search)
    monkeypatch.setattr(main, "nemotron_json", model)
    monkeypatch.setattr(main, "tavily_extract", forbidden)
    report = await main.create_investigation(main.InvestigationInput(claim="Kaplan and colleagues' 2020 paper found model size and data should scale equally.", search_query="Kaplan 2020 scaling"))
    assert report["status"] == "candidate_source"
    assert report["comparison"]["relation"] == "contradicts"
    assert report["selected_source"]["url"] == source["url"]
    assert "Official arXiv record" in report["selection_reason"]
    assert any("Unverified model selection rationale" in item for item in report["trace"])
