from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


def prepare_screenshot(data: bytes) -> bytes:
    """Validate decoded dimensions and bound the vision input independently of upload size."""
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Upload a valid PNG, JPEG, or WebP screenshot.")
            width, height = image.size
            if width * height > 16_000_000 or max(width, height) > 8192:
                raise ValueError("This screenshot is too large in pixels. Crop it to the research claim first.")
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1600, 1600))
            if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", image.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=90)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The screenshot could not be decoded. Upload a valid PNG, JPEG, or WebP image.") from exc
