from io import BytesIO

import httpx
import pytest
from PIL import Image

from app import main
from app.images import prepare_screenshot


def png_bytes(size=(64, 64), mode="RGB"):
    output = BytesIO()
    Image.new(mode, size, "white").save(output, format="PNG")
    return output.getvalue()


def test_screenshot_is_resized_and_encoded_as_bounded_rgb_jpeg():
    result = prepare_screenshot(png_bytes((3000, 2000), "RGBA"))
    with Image.open(BytesIO(result)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (1600, 1067)


def test_pixel_limit_and_invalid_image_are_rejected_before_inference():
    with pytest.raises(ValueError, match="pixels"):
        prepare_screenshot(png_bytes((8193, 1)))
    with pytest.raises(ValueError, match="decoded"):
        prepare_screenshot(b"not an image")


@pytest.mark.asyncio
async def test_image_route_sends_validated_jpeg_and_returns_an_editable_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYLENS_DB_PATH", str(tmp_path / "images.db"))
    monkeypatch.setenv("STUDYLENS_LIVE_ENABLED", "true")
    calls = []

    async def model(messages, **kwargs):
        calls.append(kwargs)
        assert messages[1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        return {"claim": "The study reported a useful result in a controlled setting.", "search_query": "controlled study result"}

    monkeypatch.setattr(main, "nemotron_json", model)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        invalid = await client.post("/api/claims/extract-image", files={"image": ("bad.png", b"not an image", "image/png")})
        assert invalid.status_code == 422
        assert calls == []
        valid = await client.post("/api/claims/extract-image", files={"image": ("claim.png", png_bytes(), "image/png")})
        assert valid.status_code == 200
        assert valid.json()["search_query"] == "controlled study result"
    assert calls == [{"vision": True}]
