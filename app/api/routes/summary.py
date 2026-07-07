from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.summary import SummaryRequest, SummaryResponse
from app.db.models import Document
from app.db.session import get_db_session
from app.services.summary_service import generate_summary

router = APIRouter(prefix="/api/v1/documents", tags=["summary"])


@router.post("/{document_id}/summary", response_model=SummaryResponse)
async def get_summary(
    document_id: str,
    request: SummaryRequest,
    db: AsyncSession = Depends(get_db_session),
):
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Dokumen '{document_id}' tidak ditemukan"},
        )
    if document.status != "ready":
        raise HTTPException(
            status_code=409,
            detail={"code": "DOCUMENT_NOT_READY", "message": f"Dokumen masih berstatus '{document.status}'"},
        )

    # TODO: cek cache summary yang sudah ada di DB kalau force_regenerate=False
    # (skeleton ini belum menyimpan summary hasil generate sebelumnya).

    return await generate_summary(
        db=db,
        document_id=document_id,
        response_language=request.response_language,
    )
