import pytest

from app import main
from app.providers import _parse_arxiv_atom, research_page_url


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "test.db"))


@pytest.mark.asyncio
async def test_report_requires_an_exact_passage(monkeypatch):
    source = {
        "url": "https://arxiv.org/abs/1234.5678",
        "title": "An example study",
        "snippet": "A study about this topic.",
    }

    async def search(_query):
        return [source]

    async def extract(_url, _query):
        return (
            "This study tested 100 examples. The method improved accuracy on this dataset. "
            "More research is needed. The authors compared the method with a fixed baseline "
            "using the same evaluation examples and recorded the observed outcome. "
            "The result applies only to the tested setting. "
            "The paper explains its data collection procedure and reports how the baseline was selected. "
            "Its discussion lists limitations of the evaluation and recommends follow-up experiments."
        )

    calls = 0

    async def model(_messages, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"index": 0, "url": source["url"], "source_type": "original_study", "reason": "The result and method align."}
        return {
            "is_original_study": True,
            "supporting_excerpt": "The authors compared the method with a fixed baseline using the same evaluation examples and recorded the observed outcome.",
            "study_tested": "A method on 100 examples.",
            "study_found": "Accuracy improved on this dataset.",
            "wording_gap": "The public claim generalizes beyond this dataset.",
            "uncertainties": ["The result may not transfer to other datasets."],
        }

    monkeypatch.setattr(main, "tavily_search", search)
    monkeypatch.setattr(main, "tavily_extract", extract)
    monkeypatch.setattr(main, "nemotron_json", model)
    report = await main.create_investigation(
        main.InvestigationInput(
            claim="This method always improves accuracy.",
            search_query="method accuracy research study",
        )
    )

    assert report["status"] == "candidate_source"
    assert report["comparison"]["supporting_excerpt"] == "The authors compared the method with a fixed baseline using the same evaluation examples and recorded the observed outcome."
    assert main.read_investigation(report["id"])["id"] == report["id"]


@pytest.mark.asyncio
async def test_invented_quote_is_not_presented_as_evidence(monkeypatch):
    async def search(_query):
        return [{"url": "https://arxiv.org/abs/1234.5678", "title": "Study", "snippet": "Relevant."}]

    async def extract(_url, _query):
        return "The accessible paper text is lengthy but does not support the claim. " * 5

    calls = 0

    async def model(_messages, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"index": 0, "url": "https://arxiv.org/abs/1234.5678", "source_type": "original_study", "reason": "Potentially relevant."}
        return {"is_original_study": True, "supporting_excerpt": "The result was proven in all settings and applies to every possible test case.", "study_tested": "All settings", "study_found": "Success", "wording_gap": "None", "uncertainties": []}

    monkeypatch.setattr(main, "tavily_search", search)
    monkeypatch.setattr(main, "tavily_extract", extract)
    monkeypatch.setattr(main, "nemotron_json", model)
    report = await main.create_investigation(
        main.InvestigationInput(
            claim="This method was proven in all settings.",
            search_query="method proven all settings",
        )
    )

    assert report["status"] == "source_not_confirmed"
    assert report["selected_source"] is None
    assert report["comparison"] is None


@pytest.mark.asyncio
async def test_no_candidate_is_a_valid_outcome(monkeypatch):
    async def search(_query):
        return []

    monkeypatch.setattr(main, "tavily_search", search)
    report = await main.create_investigation(
        main.InvestigationInput(
            claim="A nonexistent study proved this claim.",
            search_query="nonexistent study claim",
        )
    )
    assert report["status"] == "source_not_confirmed"
    assert report["candidates"] == []


@pytest.mark.asyncio
async def test_reader_can_add_a_source_when_search_found_none(monkeypatch):
    async def search(_query):
        return []

    async def extract(_url, _query):
        return "The study examined 100 examples and found no reliable improvement. " * 7

    async def model(_messages, **_kwargs):
        return {
            "is_original_study": True,
            "supporting_excerpt": "The study examined 100 examples and found no reliable improvement.",
            "study_tested": "100 examples",
            "study_found": "No reliable improvement",
            "wording_gap": "The public claim says it improved every example.",
            "uncertainties": [],
        }

    monkeypatch.setattr(main, "tavily_search", search)
    monkeypatch.setattr(main, "tavily_extract", extract)
    monkeypatch.setattr(main, "nemotron_json", model)
    report = await main.create_investigation(
        main.InvestigationInput(
            claim="The method improved every example in the study.",
            search_query="method improvement research examples",
        )
    )
    corrected = await main.correct_source(
        report["id"],
        main.SourceCorrection(source_url="https://arxiv.org/abs/1234.5678"),
    )

    assert corrected["status"] == "candidate_source"
    assert corrected["selected_source"]["url"] == "https://arxiv.org/abs/1234.5678"
    assert corrected["corrections"][0]["previous_url"] is None
    assert main.read_investigation(report["id"])["corrections"] == corrected["corrections"]


@pytest.mark.parametrize(
    "index,url,source_type",
    [
        (True, "https://arxiv.org/abs/1234.5678", "original_study"),
        (0, "https://arxiv.org/abs/9999.9999", "original_study"),
        (0, "https://arxiv.org/abs/1234.5678", "review"),
    ],
)
@pytest.mark.asyncio
async def test_selection_must_identify_the_same_original_page(monkeypatch, index, url, source_type):
    source = {"url": "https://arxiv.org/abs/1234.5678", "title": "A study", "snippet": "Relevant."}

    async def search(_query):
        return [source]

    async def model(_messages, **_kwargs):
        return {"index": index, "url": url, "source_type": source_type, "reason": "A related result."}

    monkeypatch.setattr(main, "tavily_search", search)
    monkeypatch.setattr(main, "nemotron_json", model)
    report = await main.create_investigation(
        main.InvestigationInput(claim="A study reported improved accuracy.", search_query="study accuracy")
    )
    assert report["status"] == "source_not_confirmed"
    assert report["selected_source"] is None
    assert report["candidates"] == [source]


@pytest.mark.asyncio
async def test_citing_paper_with_real_quote_is_not_confirmed(monkeypatch):
    source = {"url": "https://arxiv.org/abs/1234.5678", "title": "A later paper", "snippet": "Related work."}

    async def search(_query):
        return [source]

    async def extract(_url, _query):
        return "A later paper describes earlier research. Smith and Lee found the method improved accuracy in the original study. " * 3

    calls = 0

    async def model(_messages, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"index": 0, "url": source["url"], "source_type": "original_study", "reason": "A related result."}
        return {
            "is_original_study": False,
            "supporting_excerpt": "Smith and Lee found the method improved accuracy in the original study.",
            "uncertainties": None,
        }

    monkeypatch.setattr(main, "tavily_search", search)
    monkeypatch.setattr(main, "tavily_extract", extract)
    monkeypatch.setattr(main, "nemotron_json", model)
    report = await main.create_investigation(
        main.InvestigationInput(claim="The method improved accuracy in the study.", search_query="method accuracy paper")
    )
    assert report["status"] == "source_not_confirmed"
    assert report["selected_source"] is None


@pytest.mark.asyncio
async def test_uncertainty_shapes_and_ungrounded_numbers(monkeypatch):
    source_text = "The authors tested a new method on 100 examples and observed better accuracy than their baseline. " * 3

    async def model(_messages, **_kwargs):
        return {
            "is_original_study": True,
            "supporting_excerpt": "The authors tested a new method on 100 examples and observed better accuracy than their baseline.",
            "study_tested": "200 examples",
            "study_found": "Better accuracy",
            "wording_gap": "The claim extends beyond the examples.",
            "uncertainties": "The source notes a narrow sample.",
        }

    monkeypatch.setattr(main, "nemotron_json", model)
    comparison = await main._compare("The method improves accuracy.", "New method", source_text)
    assert comparison["excerpt_verified"] is True
    assert comparison["study_tested"] == ""
    assert comparison["uncertainties"] == ["The source notes a narrow sample."]


def test_known_news_and_listing_urls_are_filtered():
    assert research_page_url("https://www.nature.com/articles/d41586-021-00001-x") is None
    assert research_page_url("https://www.science.org/content/article/example") is None
    assert research_page_url("https://arxiv.org/search/?query=example") is None
    assert research_page_url("https://pubmed.ncbi.nlm.nih.gov/?term=example") is None
    assert research_page_url("https://arxiv.org/pdf/2203.15556v2") == "https://arxiv.org/abs/2203.15556"
    assert research_page_url("https://ar5iv.labs.arxiv.org/html/2203.15556") == "https://arxiv.org/abs/2203.15556"
    assert research_page_url("https://openreview.net/forum") is None
    assert research_page_url("https://openreview.net/forum?id=abc123") == "https://openreview.net/forum?id=abc123"


def test_official_arxiv_metadata_has_verifiable_abstract_text():
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>Training Compute-Optimal Large Language Models</title>
      <author><name>Jordan Hoffmann</name></author>
      <summary>We tested a series of language models under a fixed compute budget. The result showed that balancing model size and training data improved performance. This abstract contains enough context for a reader to inspect the claim and its limits in the original source.</summary>
    </entry></feed>"""
    text = _parse_arxiv_atom(atom)
    assert "Jordan Hoffmann" in text
    assert "Abstract: We tested a series" in text


@pytest.mark.asyncio
async def test_failed_reader_correction_keeps_original_match(monkeypatch):
    original = {"url": "https://arxiv.org/abs/1234.5678", "title": "Original paper", "snippet": "Result."}
    report = {
        "id": "existing-report",
        "created_at": "2026-10-28T00:00:00+00:00",
        "claim": "The original study reported an accuracy improvement.",
        "search_query": "original accuracy study",
        "status": "candidate_source",
        "message": "A candidate study was found.",
        "candidates": [original],
        "selected_source": original,
        "comparison": {"supporting_excerpt": "The original study reported an accuracy improvement.", "excerpt_verified": True},
        "selection_reason": "The title matches.",
        "trace": [],
        "corrections": [],
    }
    main.save_report(report)

    async def unavailable(_url, _query):
        raise main.ProviderError("The source could not be retrieved.")

    monkeypatch.setattr(main, "tavily_extract", unavailable)
    updated = await main.correct_source(
        report["id"], main.SourceCorrection(source_url="https://arxiv.org/abs/9999.9999")
    )
    assert updated["selected_source"] == original
    assert updated["comparison"] == report["comparison"]
    assert updated["corrections"][0]["accepted"] is False
    assert updated["corrections"][0]["previous_source"] == original
