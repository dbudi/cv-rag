# CV RAG POC

RAG system untuk summarization & Q&A CV kandidat (internal tool HRD).

Referensi desain:
- `PRD_RAG_CV_Summarization.md`
- `Design_Parsing_Chunking_CV_Bilingual.md`
- `Design_API_Endpoints.md`

## Struktur Project

```
app/
  main.py                 # entry point FastAPI
  config.py               # pydantic-settings, baca dari .env
  api/
    routes/                # documents, summary, query endpoints
    schemas/                # Pydantic request/response models
  parsing/                 # PDF/DOCX/MD parser -> ParsedDocument
  chunking/                 # section detection, language detection, chunker
  services/
    llm_client.py            # wrapper LiteLLM (LLM + embedding)
    ingestion_service.py      # orkestrasi parsing -> chunking -> embedding
    summary_service.py        # generate ringkasan terstruktur
    query_service.py          # retrieval + generation + groundedness
  db/
    models.py                 # SQLAlchemy models (Document, Chunk + pgvector)
    session.py                 # async session factory
tests/
scripts/init_db.sql         # enable extension pgvector
docker-compose.yml           # Postgres + pgvector untuk dev lokal
```

## Setup Lokal

```bash
# 1. Jalankan Postgres + pgvector
docker compose up -d

# 2. Enable extension pgvector (sekali saja; lewati jika DB baru — auto dari init script)
docker compose exec db psql -U postgres -d cv_rag_poc -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. Install dependencies
poetry install

# 4. Copy & isi environment variables
cp .env.example .env   # PowerShell: Copy-Item .env.example .env
# isi LITELLM_BASE_URL / LITELLM_API_KEY sesuai proxy LiteLLM Anda

# 5. Jalankan server (tabel dibuat otomatis via lifespan startup app/main.py)
poetry run uvicorn app.main:app --reload
```

Dokumentasi API interaktif tersedia di `http://localhost:8000/docs`.

## Endpoint API

| Method   | Path                                | Keterangan                                                                 |
|----------|-------------------------------------|----------------------------------------------------------------------------|
| `GET`    | `/health`                           | Health check, return `{"status": "ok"}`                                    |
| `POST`   | `/api/v1/documents`                 | Upload CV (PDF/DOCX/MD), proses ingestion async di background              |
| `GET`    | `/api/v1/documents`                 | List semua dokumen (filter status, pagination `limit`/`offset`)            |
| `GET`    | `/api/v1/documents/{document_id}`   | Detail satu dokumen (status, chunk count, extraction method, error)        |
| `DELETE` | `/api/v1/documents/{document_id}`   | Hapus dokumen beserta chunk-nya (cascade)                                  |
| `POST`   | `/api/v1/documents/{document_id}/summary` | Generate ringkasan terstruktur CV (bahasa bisa dipilih di body)     |
| `POST`   | `/api/v1/query`                     | Q&A atas satu/beberapa CV (retrieval + generation + groundedness)          |

## Yang Masih Perlu Dikerjakan (belum termasuk di skeleton ini)

- [ ] Fallback LLM classification untuk section yang tidak ter-assign lewat heading-match (lihat `ingestion_service.py`, ada TODO).
- [ ] Caching summary di DB (saat ini `POST /summary` selalu generate ulang; `force_regenerate` belum efektif).
- [ ] Groundedness check yang lebih robust di `query_service.py` (saat ini masih placeholder `True`).
- [ ] Migrasi Alembic (saat ini pakai `create_all` langsung untuk kecepatan POC).
- [ ] Test coverage untuk parsing, chunking dengan sample CV nyata.
- [ ] Validasi ukuran file upload (`MAX_UPLOAD_SIZE_MB` sudah ada di config, belum di-enforce di route).

## Catatan Desain Penting

- **Threshold chunking** (`chunk_size_tokens`, `chunk_overlap_tokens`) sengaja bisa dioverride per-request lewat query param di `POST /api/v1/documents`, bukan nilai fix — default diambil dari `.env`.
- **Bahasa jawaban default**: English (`response_language="en"`), bisa di-override per-request.
- **Vector store**: pgvector, filtering metadata (`section_type`, `document_id`) dan similarity search digabung dalam satu query SQL (lihat `query_service.py`).
