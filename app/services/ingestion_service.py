from app.chunking.chunker import chunk_sections
from app.chunking.section_detector import detect_sections
from app.config import settings
from app.db.models import Chunk, Document
from app.db.session import async_session_factory
from app.parsing.dispatcher import parse_document
from app.services.llm_client import generate_embedding


async def ingest_document(
    document_id: str,
    file_bytes: bytes,
    filename: str,
    chunk_size_tokens: int | None,
    chunk_overlap_tokens: int | None,
) -> None:
    """Dipanggil sebagai background task setelah upload. Update status
    Document di DB seiring progres (processing -> ready/failed)."""
    async with async_session_factory() as db:
        document = await db.get(Document, document_id)
        if document is None:
            return

        try:
            parsed = parse_document(file_bytes, filename)

            if not parsed.raw_text.strip():
                document.status = "failed"
                document.error_message = "NO_EXTRACTABLE_TEXT: tidak ada teks terekstrak setelah parsing/OCR"
                await db.commit()
                return

            sections = detect_sections(parsed.raw_text)

            # TODO: untuk section bertipe "other" yang signifikan ukurannya,
            # panggil fallback LLM classification di sini (lihat Design doc Sec. 4.1 Step 3)
            # sebelum lanjut ke chunking.

            chunks = chunk_sections(
                sections=sections,
                document_id=document_id,
                source_filename=filename,
                extraction_method=parsed.extraction_method,
                chunk_size_tokens=chunk_size_tokens or settings.default_chunk_size_tokens,
                chunk_overlap_tokens=chunk_overlap_tokens or settings.default_chunk_overlap_tokens,
            )

            for chunk in chunks:
                embedding = await generate_embedding(chunk.content)
                db.add(
                    Chunk(
                        id=chunk.chunk_id,
                        document_id=document_id,
                        section_type=chunk.section_type,
                        language=chunk.language,
                        content=chunk.content,
                        order_index=chunk.order_index,
                        embedding=embedding,
                    )
                )

            document.status = "ready"
            document.extraction_method = parsed.extraction_method
            await db.commit()

        except Exception as exc:  # noqa: BLE001
            document.status = "failed"
            document.error_message = str(exc)
            await db.commit()
