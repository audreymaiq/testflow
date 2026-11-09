"""Bounded PDF/DOCX decoding; no database, network, or user-visible side effects."""

from __future__ import annotations

import os
import subprocess
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import pypdfium2 as pdfium

from .image_ingest import MAX_IMAGE_PIXELS, MAX_PAGE_PNG_BYTES, MAX_PAGE_SIDE

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_PAGES = 30
MAX_DOCX_ENTRIES = 1000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_TEXT_CHARS = 1_000_000
TEXT_LAYER_MIN_CHARS = 40
RENDER_DPI = 200
CONVERT_TIMEOUT_SECONDS = 120
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class DocumentRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DocumentPage:
    png: bytes
    text_layer: str


def validate_docx(raw: bytes) -> None:
    """Reject malformed or active OOXML before invoking the document converter."""
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise DocumentRejected("DOCX_TOO_COMPLEX")
            names = {entry.filename for entry in entries}
            if not {"[Content_Types].xml", "word/document.xml"} <= names:
                raise DocumentRejected("DOCX_STRUCTURE_INVALID")
            total = 0
            for entry in entries:
                total += entry.file_size
                name = entry.filename.lower()
                if total > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise DocumentRejected("DOCX_EXPANSION_EXCEEDED")
                if entry.flag_bits & 1 or name.startswith("/") or ".." in Path(name).parts:
                    raise DocumentRejected("DOCX_STRUCTURE_INVALID")
                if any(part in name for part in ("vbaproject", "activex", "embeddings/")):
                    raise DocumentRejected("DOCX_ACTIVE_CONTENT")
                if name.endswith(".rels"):
                    relationships = ElementTree.fromstring(archive.read(entry))
                    if any(
                        node.attrib.get("TargetMode", "").lower() == "external"
                        for node in relationships
                    ):
                        raise DocumentRejected("DOCX_EXTERNAL_REFERENCE")
    except (zipfile.BadZipFile, ElementTree.ParseError, RuntimeError, OSError) as exc:
        raise DocumentRejected("DOCX_STRUCTURE_INVALID") from exc


def _convert_docx(raw: bytes, workdir: Path, soffice: str) -> bytes:
    source = workdir / "source.docx"
    source.write_bytes(raw)
    output_dir = workdir / "output"
    output_dir.mkdir()
    profile = (workdir / "profile").as_uri()
    command = [
        soffice,
        f"-env:UserInstallation={profile}",
        "--headless",
        "--convert-to",
        "pdf:writer_pdf_Export",
        "--outdir",
        str(output_dir),
        str(source),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            timeout=CONVERT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DocumentRejected("DOCX_CONVERTER_UNAVAILABLE") from exc
    converted = output_dir / "source.pdf"
    if result.returncode != 0 or not converted.is_file():
        raise DocumentRejected("DOCX_CONVERSION_FAILED")
    if converted.stat().st_size > MAX_DOCUMENT_BYTES:
        raise DocumentRejected("DOCX_CONVERSION_TOO_LARGE")
    return converted.read_bytes()


class DocumentPages:
    """Open one untrusted document in a worker; render only the requested page."""

    def __init__(self, raw: bytes, mime_type: str, *, soffice: str | None = None):
        if not raw or len(raw) > MAX_DOCUMENT_BYTES:
            raise DocumentRejected("DOCUMENT_SIZE_INVALID")
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._pdf: pdfium.PdfDocument | None = None
        try:
            if mime_type == DOCX_MIME:
                validate_docx(raw)
                self._temporary = tempfile.TemporaryDirectory(prefix="testflow-docx-")
                raw = _convert_docx(
                    raw,
                    Path(self._temporary.name),
                    soffice or os.environ.get("SOFFICE_BIN", "soffice"),
                )
            elif mime_type != "application/pdf" or not raw.startswith(b"%PDF-"):
                raise DocumentRejected("DOCUMENT_TYPE_INVALID")
            if not raw.startswith(b"%PDF-"):
                raise DocumentRejected("PDF_INVALID")
            self._pdf = pdfium.PdfDocument(raw)
            count = len(self._pdf)
            if count < 1:
                raise DocumentRejected("PDF_EMPTY")
            if count > MAX_PAGES:
                raise DocumentRejected("TOO_MANY_PAGES")
            self.page_count = count
        except pdfium.PdfiumError as exc:
            self.close()
            raise DocumentRejected("PDF_INVALID") from exc
        except Exception:
            self.close()
            raise

    def __enter__(self) -> DocumentPages:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        if self._pdf is not None:
            self._pdf.close()
            self._pdf = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def render(self, page_no: int) -> DocumentPage:
        if self._pdf is None or not 1 <= page_no <= self.page_count:
            raise DocumentRejected("PAGE_OUT_OF_RANGE")
        try:
            with closing(self._pdf[page_no - 1]) as page:
                width, height = page.get_size()
                if width <= 0 or height <= 0:
                    raise DocumentRejected("PAGE_DIMENSIONS_INVALID")
                scale = min(
                    RENDER_DPI / 72,
                    MAX_PAGE_SIDE / max(width, height),
                    (MAX_IMAGE_PIXELS / (width * height)) ** 0.5,
                )
                if scale <= 0:
                    raise DocumentRejected("PAGE_DIMENSIONS_INVALID")
                with closing(page.get_textpage()) as text_page:
                    text = text_page.get_text_bounded()
                if len(text) > MAX_TEXT_CHARS:
                    raise DocumentRejected("PAGE_TEXT_TOO_LARGE")
                text = text if sum(char.isalnum() for char in text) >= TEXT_LAYER_MIN_CHARS else ""
                with closing(page.render(scale=scale)) as bitmap:
                    image = bitmap.to_pil().convert("RGB")
                    output = BytesIO()
                    image.save(output, format="PNG", optimize=True)
                if output.tell() > MAX_PAGE_PNG_BYTES:
                    raise DocumentRejected("PAGE_IMAGE_TOO_LARGE")
                return DocumentPage(png=output.getvalue(), text_layer=text)
        except pdfium.PdfiumError as exc:
            raise DocumentRejected("PAGE_RENDER_FAILED") from exc
