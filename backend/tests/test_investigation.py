import pytest

from app import main


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
            "The result applies only to the tested setting."
        )

    calls = 0

    async def model(_messages, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"index": 0, "reason": "The result and method align."}
        return {
            "supporting_excerpt": "The method improved accuracy on this dataset.",
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
    assert report["comparison"]["supporting_excerpt"] == "The method improved accuracy on this dataset."
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
            return {"index": 0, "reason": "Potentially relevant."}
        return {"supporting_excerpt": "The result was proven in all settings.", "study_tested": "All settings", "study_found": "Success", "wording_gap": "None", "uncertainties": []}

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
        return "The study examined 100 examples and found no reliable improvement. " * 5

    async def model(_messages, **_kwargs):
        return {
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
