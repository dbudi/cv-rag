from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    created_at: datetime


class DocumentDetailResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    extraction_method: str | None = None
    detected_languages: list[str] = []
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    total: int
    limit: int
    offset: int
