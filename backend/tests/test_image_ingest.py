"""Synthetic, bounded image ingestion cases; no real exam content."""

from io import BytesIO

import pytest
from PIL import Image

from apps.imports import image_ingest


def encoded_image(format_name="PNG", *, width=8, height=6, exif=None):
    output = BytesIO()
    options = {"exif": exif} if exif is not None else {}
    Image.new("RGB", (width, height), color=(20, 40, 60)).save(
        output, format=format_name, **options
    )
    return output.getvalue()


@pytest.mark.parametrize(
    ("format_name", "mime_type"),
    [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")],
)
def test_supported_content_is_normalized_to_one_png(format_name, mime_type):
    result = image_ingest.normalize_image(encoded_image(format_name))
    assert result.source_mime_type == mime_type
    assert (result.width, result.height) == (8, 6)
    assert result.png.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(result.png)) as page:
        assert page.mode == "RGB"
        assert page.size == (8, 6)


def test_exif_orientation_applies_before_page_dimensions():
    exif = Image.Exif()
    exif[274] = 6
    result = image_ingest.normalize_image(encoded_image("JPEG", width=8, height=6, exif=exif))
    assert (result.width, result.height) == (6, 8)


def test_long_edge_is_bounded():
    result = image_ingest.normalize_image(encoded_image(width=3_100, height=10))
    assert result.width == image_ingest.MAX_PAGE_SIDE
    assert result.height <= 10


@pytest.mark.parametrize("raw", [b"", b"not an image", b"\x89PNG\r\n\x1a\ntruncated"])
def test_empty_or_corrupt_payload_is_rejected(raw):
    with pytest.raises(image_ingest.ImageRejected):
        image_ingest.normalize_image(raw)


def test_unsupported_image_format_is_rejected_by_decoded_content():
    with pytest.raises(image_ingest.ImageRejected) as exc:
        image_ingest.normalize_image(encoded_image("GIF"))
    assert exc.value.code == "IMAGE_FORMAT_UNSUPPORTED"


def test_animated_webp_is_rejected():
    frames = [Image.new("RGB", (8, 6), color=color) for color in ("red", "blue")]
    output = BytesIO()
    frames[0].save(output, format="WEBP", save_all=True, append_images=frames[1:], duration=100)
    with pytest.raises(image_ingest.ImageRejected) as exc:
        image_ingest.normalize_image(output.getvalue())
    assert exc.value.code == "IMAGE_ANIMATED_UNSUPPORTED"


def test_byte_and_pixel_limits_are_enforced(monkeypatch):
    raw = encoded_image()
    monkeypatch.setattr(image_ingest, "MAX_IMAGE_BYTES", len(raw) - 1)
    with pytest.raises(image_ingest.ImageRejected) as exc:
        image_ingest.normalize_image(raw)
    assert exc.value.code == "IMAGE_SIZE_INVALID"

    monkeypatch.setattr(image_ingest, "MAX_IMAGE_BYTES", len(raw))
    monkeypatch.setattr(image_ingest, "MAX_IMAGE_PIXELS", 47)
    with pytest.raises(image_ingest.ImageRejected) as exc:
        image_ingest.normalize_image(raw)
    assert exc.value.code == "IMAGE_PIXELS_EXCEEDED"


def test_normalized_page_size_is_bounded_before_inference(monkeypatch):
    monkeypatch.setattr(image_ingest, "MAX_PAGE_PNG_BYTES", 16)
    with pytest.raises(image_ingest.ImageRejected) as exc:
        image_ingest.normalize_image(encoded_image())
    assert exc.value.code == "PAGE_IMAGE_TOO_LARGE"
