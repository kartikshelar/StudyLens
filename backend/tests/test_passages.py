import pytest

from app import main


@pytest.mark.asyncio
async def test_indexed_passage_preserves_latex_and_original_wording(monkeypatch):
    quote = r"We train a 70B model on 4$\times$ more more data than Gopher."
    source = f"Title: Study\nAuthors: Example\nFirst submitted: 2022-01-01\nAbstract: {quote} The next sentence gives additional context."

    async def model(_messages, **_kwargs):
        return {"is_original_study": True, "passage_ids": [0], "relation": "supports"}

    monkeypatch.setattr(main, "nemotron_json", model)
    result = await main._compare("A model used more data.", "Study", source)
    assert result["supporting_excerpt"] == quote
    assert result["excerpt_verified"] is True
    assert result["quote_method"] == "indexed_passages"


@pytest.mark.parametrize("ids", [[True], ["0"], [-1], [3], [0, 2], [1, 0], [0, 0], [], None])
def test_invalid_passage_ids_cannot_fall_back_to_a_model_quote(ids):
    result = {"passage_ids": ids, "supporting_excerpt": "An otherwise matching quote."}
    excerpt, method = main._selected_excerpt(result, ["First passage.", "Second passage.", "Third passage."])
    assert excerpt == ""
    assert method == "invalid_passage_selection"


def test_consecutive_passages_keep_the_complete_intervening_text():
    result = {"passage_ids": [0, 1]}
    source = "One complete passage. The second complete passage. A third passage."
    passages = main._source_passages(source)
    excerpt, method = main._selected_excerpt(result, passages)
    assert excerpt == "One complete passage. The second complete passage."
    assert method == "indexed_passages"
