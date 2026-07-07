from app.parsing.base import ParsedDocument
from app.parsing.docx_parser import parse_docx
from app.parsing.md_parser import parse_markdown
from app.parsing.pdf_parser import parse_pdf


class UnsupportedFileFormatError(Exception):
    pass


def parse_document(file_bytes: bytes, filename: str) -> ParsedDocument:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        return parse_pdf(file_bytes, filename)
    if ext in ("docx",):
        return parse_docx(file_bytes, filename)
    if ext in ("md", "markdown"):
        return parse_markdown(file_bytes, filename)

    raise UnsupportedFileFormatError(f"Format file '.{ext}' tidak didukung")
