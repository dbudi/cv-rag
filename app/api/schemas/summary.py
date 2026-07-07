from datetime import datetime

from pydantic import BaseModel

from app.config import settings


class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: int | None = None


class CVSummary(BaseModel):
    name: str | None = None
    total_experience_years: float | None = None
    current_or_last_role: str | None = None
    key_skills: list[str] = []
    education: list[EducationEntry] = []
    experience_highlights: list[str] = []
    notes: str | None = None


class Citation(BaseModel):
    section_type: str
    chunk_id: str


class SummaryRequest(BaseModel):
    force_regenerate: bool = False
    response_language: str = settings.default_response_language


class SummaryResponse(BaseModel):
    document_id: str
    summary: CVSummary
    citations: list[Citation]
    generated_at: datetime
