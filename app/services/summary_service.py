import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TYPE_CHECKING, Any

from app.api.schemas.summary import Citation, CVSummary, SummaryResponse
from app.db.models import Chunk
from app.services.llm_client import generate_completion

SYSTEM_PROMPT = (
    "You extract structured information from CV text chunks. "
    "Respond ONLY with a JSON object matching this schema (no markdown, no preamble): "
    '{"name": str|null, "total_experience_years": float|null, '
    '"current_or_last_role": str|null, "key_skills": [str], '
    '"education": [{"degree": str, "institution": str, "year": int|null}], '
    '"experience_highlights": [str], "notes": str|null}'
)


async def generate_summary(
    db: AsyncSession,
    document_id: str,
    response_language: str,
) -> SummaryResponse:
    stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.order_index)
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    context_text = "\n\n---\n\n".join(
        f"[section={c.section_type}]\n{c.content}" for c in chunks
    )

    raw_response = await generate_completion(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=context_text,
        response_language=response_language,
    )

    # TODO: tambahkan error handling yang lebih defensif untuk kasus LLM
    # tidak strict mengikuti format JSON (misal retry dengan instruksi lebih tegas).
    parsed = json.loads(raw_response)
    summary = CVSummary(**parsed)

    citations = [
        Citation(section_type=c.section_type, chunk_id=c.id)
        for c in chunks
        if c.section_type in ("experience", "education")
    ]

    return SummaryResponse(
        document_id=document_id,
        summary=summary,
        citations=citations,
        generated_at=datetime.utcnow(),
    )
