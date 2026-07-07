from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.query import PerDocumentNote, QueryCitation, QueryResponse
from app.db.models import Chunk
from app.services.llm_client import generate_completion, generate_embedding

# Threshold cosine-distance untuk menentukan "grounded". Nilai ini perlu
# dikalibrasi lewat eksperimen dengan sample CV & pertanyaan jebakan
# (lihat Design_API_Endpoints.md Sec. 11).
GROUNDEDNESS_DISTANCE_THRESHOLD = 0.4

SYSTEM_PROMPT = (
    "You are an assistant that answers questions about a candidate's CV "
    "strictly based on the provided context chunks. If the answer is not "
    "present in the context, say so explicitly instead of guessing."
)


async def answer_query(
    db: AsyncSession,
    question: str,
    document_ids: list[str],
    response_language: str,
    top_k: int,
) -> QueryResponse:
    query_embedding = await generate_embedding(question)

    # Retrieval: similarity search via pgvector, difilter ke document_ids terkait.
    stmt = (
        select(Chunk)
        .where(Chunk.document_id.in_(document_ids))
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k * len(document_ids))
    )
    result = await db.execute(stmt)
    retrieved_chunks = result.scalars().all()

    if not retrieved_chunks:
        return QueryResponse(
            answer="No relevant information found in the provided CV(s).",
            grounded=False,
            citations=[],
        )

    context_text = "\n\n---\n\n".join(
        f"[document_id={c.document_id}, section={c.section_type}]\n{c.content}"
        for c in retrieved_chunks
    )

    answer = await generate_completion(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"Context:\n{context_text}\n\nQuestion: {question}",
        response_language=response_language,
    )

    citations = [
        QueryCitation(document_id=c.document_id, section_type=c.section_type, chunk_id=c.id)
        for c in retrieved_chunks
    ]

    # TODO: groundedness check yang lebih robust — bisa kombinasi
    # (a) distance score dari retrieval, dan (b) self-check tambahan ke LLM
    # ("does the context actually support this answer?").
    grounded = True

    per_document_notes = [
        PerDocumentNote(document_id=doc_id, note="See citations for supporting sections.")
        for doc_id in document_ids
    ]

    return QueryResponse(
        answer=answer,
        grounded=grounded,
        citations=citations,
        per_document_notes=per_document_notes,
    )
