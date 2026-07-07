from app.parsing.base import ParsedDocument


def parse_markdown(file_bytes: bytes, filename: str) -> ParsedDocument:
    text = file_bytes.decode("utf-8", errors="ignore")

    return ParsedDocument(
        source_filename=filename,
        raw_text=text,
        pages=None,
        extraction_method="native",
    )
