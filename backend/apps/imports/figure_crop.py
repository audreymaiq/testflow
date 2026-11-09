"""Extract bounded PNG assets from normalized private page images."""

from __future__ import annotations

from io import BytesIO
from math import ceil, floor

from PIL import Image, UnidentifiedImageError

MAX_FIGURE_BYTES = 10 * 1024 * 1024


class FigureRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def crop_figure(page_png: bytes, bbox: tuple[float, float, float, float]) -> bytes:
    """Crop a normalized [0,1] box; the caller supplies a validated PageFigure."""
    try:
        with Image.open(BytesIO(page_png)) as image:
            if image.format != "PNG" or image.width > 3000 or image.height > 3000:
                raise FigureRejected("FIGURE_PAGE_INVALID")
            x0, y0, x1, y1 = bbox
            left = max(0, floor(x0 * image.width))
            top = max(0, floor(y0 * image.height))
            right = min(image.width, ceil(x1 * image.width))
            bottom = min(image.height, ceil(y1 * image.height))
            if right - left < 2 or bottom - top < 2:
                raise FigureRejected("FIGURE_TOO_SMALL")
            with image.crop((left, top, right, bottom)) as cropped:
                output = BytesIO()
                cropped.convert("RGB").save(output, format="PNG", optimize=True)
            if output.tell() > MAX_FIGURE_BYTES:
                raise FigureRejected("FIGURE_TOO_LARGE")
            return output.getvalue()
    except FigureRejected:
        raise
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise FigureRejected("FIGURE_CROP_FAILED") from exc
