from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.document import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.db.models import Document
from app.db.session import async_session_factory, get_db_session
from app.services.ingestion_service import ingest_document

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "md", "markdown"}


@router.post("", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE_FORMAT", "message": f"Format '.{ext}' tidak didukung"},
        )

    document = Document(filename=file.filename, status="processing")
    db.add(document)
    await db.commit()
    await db.refresh(document)

    file_bytes = await file.read()
    background_tasks.add_task(
        ingest_document,
        document.id,
        file_bytes,
        file.filename,
        chunk_size_tokens,
        chunk_overlap_tokens,
    )

    return DocumentUploadResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db_session)):
    stmt = select(Document).where(Document.id == document_id).options(selectinload(Document.chunks))
    result = await db.execute(stmt)
    document = result.scalars().first()
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Dokumen '{document_id}' tidak ditemukan"},
        )

    return DocumentDetailResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        extraction_method=document.extraction_method,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
        updated_at=document.updated_at,
        error_message=document.error_message,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Document)
    if status:
        stmt = stmt.where(Document.status == status)
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    documents = result.scalars().all()

    total_stmt = select(Document)
    if status:
        total_stmt = total_stmt.where(Document.status == status)
    total = len((await db.execute(total_stmt)).scalars().all())

    return DocumentListResponse(
        items=[
            DocumentListItem(document_id=d.id, filename=d.filename, status=d.status)
            for d in documents
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db_session)):
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Dokumen '{document_id}' tidak ditemukan"},
        )
    await db.delete(document)  # cascade ke chunks lewat relationship
    await db.commit()
