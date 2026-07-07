from pydantic import BaseModel

from app.config import settings


class QueryRequest(BaseModel):
    question: str
    document_ids: list[str]
    response_language: str = settings.default_response_language
    top_k: int = 5


class QueryCitation(BaseModel):
    document_id: str
    section_type: str
    chunk_id: str


class PerDocumentNote(BaseModel):
    document_id: str
    note: str


class QueryResponse(BaseModel):
    answer: str
    grounded: bool
    citations: list[QueryCitation]
    per_document_notes: list[PerDocumentNote] = []
