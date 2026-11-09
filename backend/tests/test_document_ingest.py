"""Real PDFium decoding and bounded DOCX conversion tests."""

import io
import zipfile

import pytest

from apps.imports import document_ingest as ingest


def pdf_bytes(*, pages=1, text="A question on this page with enough searchable text"):
    """Generate a tiny valid PDF without a test-only PDF rendering dependency."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for page_index in range(pages):
        page_id = len(objects) + 1
        stream_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode()
        )
        page_text = text[page_index] if isinstance(text, list) else text
        content = f"BT /F1 12 Tf 72 720 Td ({page_text}) Tj ET".encode()
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
    objects[1] = f"<< /Type /Pages /Count {pages} /Kids [{' '.join(kids)}] >>".encode()
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_offset = output.tell()
    output.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    )
    return output.getvalue()


def docx_bytes(*, external=False, active=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        if external:
            archive.writestr(
                "word/_rels/document.xml.rels",
                '<Relationships><Relationship TargetMode="External" Target="https://example.org"/></Relationships>',
            )
        if active:
            archive.writestr("word/vbaProject.bin", b"macro")
    return output.getvalue()


def test_pdf_text_layer_and_render_are_page_scoped():
    with ingest.DocumentPages(pdf_bytes(pages=2), "application/pdf") as document:
        assert document.page_count == 2
        for page_no in (1, 2):
            page = document.render(page_no)
            assert page.png.startswith(b"\x89PNG\r\n\x1a\n")
            assert "A question on this page" in page.text_layer
        with pytest.raises(ingest.DocumentRejected, match="PAGE_OUT_OF_RANGE"):
            document.render(3)


def test_pdf_page_limit_and_invalid_content():
    with pytest.raises(ingest.DocumentRejected, match="TOO_MANY_PAGES"):
        ingest.DocumentPages(pdf_bytes(pages=31), "application/pdf")
    with pytest.raises(ingest.DocumentRejected, match="PDF_INVALID"):
        ingest.DocumentPages(b"%PDF-corrupt", "application/pdf")


def test_docx_rejects_active_or_external_content():
    for content, code in (
        (docx_bytes(external=True), "DOCX_EXTERNAL_REFERENCE"),
        (docx_bytes(active=True), "DOCX_ACTIVE_CONTENT"),
    ):
        with pytest.raises(ingest.DocumentRejected, match=code):
            ingest.DocumentPages(content, ingest.DOCX_MIME)


def test_docx_conversion_uses_isolated_profile_and_pdf_result(monkeypatch):
    def converted(command, *, cwd, capture_output, timeout, check):
        assert command[1].startswith("-env:UserInstallation=file:")
        assert command[2:4] == ["--headless", "--convert-to"]
        assert timeout == ingest.CONVERT_TIMEOUT_SECONDS
        assert capture_output and not check
        (cwd / "output" / "source.pdf").write_bytes(pdf_bytes())
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ingest.subprocess, "run", converted)
    with ingest.DocumentPages(docx_bytes(), ingest.DOCX_MIME) as document:
        assert document.page_count == 1
        assert document.render(1).text_layer
