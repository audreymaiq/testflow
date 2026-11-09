"""Bounded image decoding for the document import stage.

The original bytes are kept by ImportJob; this module returns a normalized page
image for extraction and review. It has no database or storage side effects.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_PAGE_SIDE = 3_000
IMAGE_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


class ImageRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NormalizedImage:
    png: bytes
    width: int
    height: int
    source_mime_type: str


def normalize_image(raw: bytes) -> NormalizedImage:
    """Validate actual file content and decode one bounded, static image page."""
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ImageRejected("IMAGE_SIZE_INVALID")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                source_format = source.format
                if source_format not in IMAGE_MIME_TYPES:
                    raise ImageRejected("IMAGE_FORMAT_UNSUPPORTED")
                if source.width < 1 or source.height < 1:
                    raise ImageRejected("IMAGE_DIMENSIONS_INVALID")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ImageRejected("IMAGE_PIXELS_EXCEEDED")
                if getattr(source, "n_frames", 1) != 1:
                    raise ImageRejected("IMAGE_ANIMATED_UNSUPPORTED")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((MAX_PAGE_SIDE, MAX_PAGE_SIDE), Image.Resampling.LANCZOS)
                normalized = oriented.convert("RGB")
                output = BytesIO()
                normalized.save(output, format="PNG", optimize=True)
                return NormalizedImage(
                    png=output.getvalue(),
                    width=normalized.width,
                    height=normalized.height,
                    source_mime_type=IMAGE_MIME_TYPES[source_format],
                )
    except ImageRejected:
        raise
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise ImageRejected("IMAGE_DECODE_FAILED") from exc
