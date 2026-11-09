"""Figure crops use the normalized source page and bounded coordinates."""

from io import BytesIO

import pytest
from PIL import Image

from apps.imports.figure_crop import FigureRejected, crop_figure


def page_png():
    output = BytesIO()
    Image.new("RGB", (100, 80), "blue").save(output, format="PNG")
    return output.getvalue()


def test_crop_retains_expected_pixels_and_dimensions():
    cropped = crop_figure(page_png(), (0.1, 0.2, 0.5, 0.6))
    with Image.open(BytesIO(cropped)) as image:
        assert image.size == (40, 32)
        assert image.getpixel((0, 0)) == (0, 0, 255)


def test_tiny_or_corrupt_figure_is_rejected():
    with pytest.raises(FigureRejected, match="FIGURE_TOO_SMALL"):
        crop_figure(page_png(), (0, 0, 0.001, 0.001))
    with pytest.raises(FigureRejected, match="FIGURE_CROP_FAILED"):
        crop_figure(b"not an image", (0, 0, 1, 1))
