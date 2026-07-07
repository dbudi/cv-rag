import uuid

import tiktoken
from pydantic import BaseModel

from app.chunking.language_detector import detect_language
from app.chunking.section_detector import CVSection

_ENCODING = tiktoken.get_encoding("cl100k_base")


class CVChunk(BaseModel):
    chunk_id: str
    document_id: str
    source_filename: str
    section_type: str
    language: str
    content: str
    order_index: int
    char_count: int
    extraction_method: str


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _split_by_tokens(text: str, chunk_size_tokens: int, overlap_tokens: int) -> list[str]:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= chunk_size_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size_tokens, len(tokens))
        chunks.append(_ENCODING.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start = end - overlap_tokens  # overlap supaya konteks tidak terputus
    return chunks


def chunk_sections(
    sections: list[CVSection],
    document_id: str,
    source_filename: str,
    extraction_method: str,
    chunk_size_tokens: int,
    chunk_overlap_tokens: int,
) -> list[CVChunk]:
    """chunk_size_tokens & chunk_overlap_tokens WAJIB di-pass dari caller
    (nilai default diambil dari settings di layer service/API, bukan
    di-hardcode di sini) sesuai keputusan bahwa threshold ini configurable."""
    chunks: list[CVChunk] = []

    for section in sections:
        language = detect_language(section.content)
        token_count = _count_tokens(section.content)

        if token_count <= chunk_size_tokens:
            pieces = [section.content]
        else:
            pieces = _split_by_tokens(section.content, chunk_size_tokens, chunk_overlap_tokens)

        for piece in pieces:
            chunks.append(
                CVChunk(
                    chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                    document_id=document_id,
                    source_filename=source_filename,
                    section_type=section.section_type,
                    language=language,
                    content=piece,
                    order_index=section.order_index,
                    char_count=len(piece),
                    extraction_method=extraction_method,
                )
            )

    return chunks
