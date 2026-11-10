"""Exercise the production worker's real DOCX converter without an OCR model."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from apps.imports.document_ingest import DOCX_MIME, DocumentPages


def sample_docx() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>',
        )
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>TestFlow DOCX conversion sample question and choices"
            "</w:t></w:r></w:p><w:sectPr/></w:body></w:document>",
        )
    return output.getvalue()


with DocumentPages(sample_docx(), DOCX_MIME) as document:
    page = document.render(1)
    assert document.page_count == 1
    assert page.png.startswith(b"\x89PNG\r\n\x1a\n")
    assert "TestFlow DOCX conversion" in page.text_layer
print("DOCX conversion and PDF page rendering passed")
