from pydantic import BaseModel


class ParsedDocument(BaseModel):
    """Output seragam dari semua parser, apapun format sumbernya."""

    source_filename: str
    raw_text: str
    pages: list[str] | None = None  # khusus PDF, per halaman
    extraction_method: str  # "native" | "ocr"


def needs_ocr(page_text: str, min_chars: int = 20) -> bool:
    """Heuristik: kalau extractable text terlalu sedikit relatif ke ukuran
    halaman, kemungkinan itu hasil scan/gambar dan butuh OCR."""
    return len(page_text.strip()) < min_chars
