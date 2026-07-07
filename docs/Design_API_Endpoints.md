# Technical Design: API Endpoints & Kontrak — Internal Tool

**Referensi:** `PRD_RAG_CV_Summarization.md` v0.2, `Design_Parsing_Chunking_CV_Bilingual.md` v0.2
**Status:** Draft v0.1

---

## 1. Prinsip Desain

- Konsumen API ini adalah **internal tool/dashboard**, bukan HRD langsung — jadi kontrak boleh sedikit "teknis" (tidak perlu didesain untuk end-user awam).
- Proses **ingestion CV** (parsing → section detection → chunking → embedding) bisa memakan waktu, apalagi kalau upload banyak file sekaligus atau ada fallback OCR/LLM classification. Jadi pola **HTTP 202 + polling status** dipakai di sini — sama dengan pola yang sudah kamu pakai di service lain di `ecommerce-platform`.
- Proses **Q&A/query** ditargetkan sinkron (< 5 detik sesuai NFR di PRD), jadi tidak perlu polling.
- Semua endpoint pakai Pydantic v2 untuk request/response schema.

---

## 2. Resource Model

Tiga resource utama:

1. **Document** — representasi 1 file CV yang diupload.
2. **Summary** — ringkasan terstruktur dari 1 Document.
3. **Query** — pertanyaan bebas terhadap 1 atau banyak Document.

---

## 3. Endpoint: Upload CV

### `POST /api/v1/documents`

Upload satu file CV. Untuk multi-file, internal tool memanggil endpoint ini berkali-kali (bukan 1 endpoint batch) supaya progress per-file bisa dipantau independen.

**Request:** `multipart/form-data`

| Field | Tipe | Wajib | Keterangan |
|-------|------|-------|------------|
| `file` | file (PDF/DOCX/MD) | Ya | Max size perlu ditentukan (usulan: 10MB) |
| `chunk_size_tokens` | int | Tidak | Default 500, sesuai keputusan chunking |
| `chunk_overlap_tokens` | int | Tidak | Default 50 |

**Response `202 Accepted`:**

```json
{
  "document_id": "doc_9f8a2b",
  "filename": "budi_santoso_cv.pdf",
  "status": "processing",
  "created_at": "2026-07-06T10:15:00Z"
}
```

**Pydantic:**

```python
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus
    created_at: datetime
```

---

## 4. Endpoint: Cek Status Dokumen

### `GET /api/v1/documents/{document_id}`

**Response `200 OK`:**

```json
{
  "document_id": "doc_9f8a2b",
  "filename": "budi_santoso_cv.pdf",
  "status": "ready",
  "extraction_method": "native",
  "detected_languages": ["id", "en"],
  "chunk_count": 14,
  "created_at": "2026-07-06T10:15:00Z",
  "updated_at": "2026-07-06T10:15:42Z",
  "error_message": null
}
```

Kalau `status = "failed"`, `error_message` diisi (misal: "parsing gagal: file corrupt" atau "tidak ada teks terekstrak setelah OCR").

```python
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
```

---

## 5. Endpoint: List Dokumen

### `GET /api/v1/documents`

Query params: `status` (filter opsional), `limit`, `offset`.

**Response `200 OK`:**

```json
{
  "items": [ { "document_id": "doc_9f8a2b", "filename": "budi_santoso_cv.pdf", "status": "ready" } ],
  "total": 27,
  "limit": 20,
  "offset": 0
}
```

---

## 6. Endpoint: Generate/Ambil Ringkasan

### `POST /api/v1/documents/{document_id}/summary`

Idempotent — kalau ringkasan sudah pernah digenerate dan `force_regenerate=false` (default), langsung kembalikan hasil cache, bukan panggil LLM lagi (hemat biaya).

**Request body:**

```python
class SummaryRequest(BaseModel):
    force_regenerate: bool = False
    response_language: str = "en"   # updated: default English
```

**Response `200 OK`:**

```json
{
  "document_id": "doc_9f8a2b",
  "summary": {
    "name": "Budi Santoso",
    "total_experience_years": 5.5,
    "current_or_last_role": "Backend Engineer",
    "key_skills": ["Python", "FastAPI", "Kubernetes"],
    "education": [
      { "degree": "S1 Teknik Informatika", "institution": "Universitas X", "year": 2019 }
    ],
    "experience_highlights": [
      "Led migration from monolith to microservices architecture (2023-2024)"
    ],
    "notes": "CV contains content in two languages (ID for work history, EN for profile summary)."
  },
  "citations": [
    { "section_type": "experience", "chunk_id": "chunk_004" },
    { "section_type": "education", "chunk_id": "chunk_011" }
  ],
  "generated_at": "2026-07-06T10:16:00Z"
}
```

`summary` sengaja berupa **structured object** (bukan teks bebas) supaya internal tool bisa render dalam bentuk kartu/tabel, bukan cuma paragraf.

```python
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

class SummaryResponse(BaseModel):
    document_id: str
    summary: CVSummary
    citations: list[Citation]
    generated_at: datetime
```

---

## 7. Endpoint: Query / Q&A (single atau multi-CV)

### `POST /api/v1/query`

Satu endpoint untuk single-CV maupun multi-CV — dibedakan lewat jumlah item di `document_ids`.

**Request body:**

```python
class QueryRequest(BaseModel):
    question: str
    document_ids: list[str]          # 1 item = single-CV, >1 = perbandingan/multi
    response_language: str = "en"
    top_k: int = 5                   # jumlah chunk yang di-retrieve per dokumen
```

**Response `200 OK`:**

```json
{
  "answer": "Candidate Budi Santoso led a team on an architecture migration project for the past year in the Backend Engineer role.",
  "grounded": true,
  "citations": [
    { "document_id": "doc_9f8a2b", "section_type": "experience", "chunk_id": "chunk_004" }
  ],
  "per_document_notes": [
    { "document_id": "doc_9f8a2b", "note": "Information found directly in the experience section." }
  ]
}
```

Field **`grounded`**: boolean hasil self-check dari LLM (atau heuristik retrieval-score) — kalau retrieval tidak menemukan chunk relevan di atas threshold similarity, `grounded=false` dan `answer` berisi klarifikasi "informasi tidak ditemukan di CV", bukan jawaban dikarang. Ini instrumen penting untuk metric groundedness yang ada di PRD (Sec. 9).

```python
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
```

---

## 8. Endpoint: Hapus Dokumen

### `DELETE /api/v1/documents/{document_id}`

**Response `204 No Content`.** Menghapus dokumen, chunk, dan embedding terkait dari pgvector (cascade delete berbasis `document_id` sebagai foreign key).

---

## 9. Error Handling — Konvensi

Semua error pakai format konsisten:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Dokumen dengan id 'doc_xxx' tidak ditemukan"
  }
}
```

| HTTP Status | Kode | Kapan |
|-------------|------|-------|
| 400 | `INVALID_FILE_FORMAT` | Upload selain PDF/DOCX/MD |
| 404 | `DOCUMENT_NOT_FOUND` | Query/summary ke document_id yang tidak ada |
| 409 | `DOCUMENT_NOT_READY` | Query/summary dipanggil saat status masih `processing` |
| 422 | `NO_EXTRACTABLE_TEXT` | Parsing + OCR tetap gagal ekstrak teks |
| 500 | `INTERNAL_ERROR` | Kegagalan tak terduga (LLM API error, dsb — sebaiknya di-log dengan detail) |

---

## 10. Ringkasan Kontrak (Overview Table)

| Endpoint | Method | Sync/Async | Fungsi |
|----------|--------|------------|--------|
| `/api/v1/documents` | POST | Async (202) | Upload & mulai ingestion CV |
| `/api/v1/documents/{id}` | GET | Sync | Cek status ingestion |
| `/api/v1/documents` | GET | Sync | List semua dokumen |
| `/api/v1/documents/{id}/summary` | POST | Sync (cached) | Generate/ambil ringkasan terstruktur |
| `/api/v1/query` | POST | Sync | Q&A single/multi-CV |
| `/api/v1/documents/{id}` | DELETE | Sync | Hapus dokumen |

---

## 11. Catatan Implementasi

- Untuk POC, ingestion (`POST /documents`) bisa dijalankan **background task FastAPI biasa** (`BackgroundTasks`) dulu tanpa Celery penuh — sesuai keputusan sebelumnya bahwa POC ini belum perlu observability stack lengkap. Celery baru relevan kalau volume upload sudah tinggi/perlu retry-queue yang robust.
- `response_language` di-pass ke prompt LLM (lewat LiteLLM) sebagai instruksi eksplisit, bukan hasil auto-translate output — supaya kualitas bahasa lebih natural.
- Field `grounded` di `QueryResponse` sebaiknya dites dengan skenario pertanyaan jebakan (pertanyaan yang jawabannya memang tidak ada di CV) sebagai bagian dari acceptance test sebelum dianggap "selesai".

---

*Selanjutnya: mau saya buatkan skeleton project (struktur folder, `pyproject.toml`, module untuk parsing/chunking/API di atas), atau ada bagian kontrak ini yang mau direvisi dulu?*
