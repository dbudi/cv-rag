from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.query import QueryRequest, QueryResponse
from app.db.models import Document
from app.db.session import get_db_session
from app.services.query_service import answer_query

router = APIRouter(prefix="/api/v1/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query_documents(request: QueryRequest, db: AsyncSession = Depends(get_db_session)):
    stmt = select(Document).where(Document.id.in_(request.document_ids))
    result = await db.execute(stmt)
    documents = result.scalars().all()

    found_ids = {d.id for d in documents}
    missing = set(request.document_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Dokumen tidak ditemukan: {', '.join(missing)}"},
        )

    not_ready = [d.id for d in documents if d.status != "ready"]
    if not_ready:
        raise HTTPException(
            status_code=409,
            detail={"code": "DOCUMENT_NOT_READY", "message": f"Dokumen belum siap: {', '.join(not_ready)}"},
        )

    return await answer_query(
        db=db,
        question=request.question,
        document_ids=request.document_ids,
        response_language=request.response_language,
        top_k=request.top_k,
    )
