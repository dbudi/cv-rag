# PRD: RAG System untuk CV Summarization (HRD)

**Status:** Draft v0.1 — Tahap Eksplorasi/POC
**Tanggal:** 6 Juli 2026

---

## 1. Latar Belakang & Problem Statement

Tim HRD saat ini membaca CV kandidat satu per satu secara manual untuk memahami profil, pengalaman, dan kesesuaian dengan posisi yang dibuka. Proses ini:

- Memakan waktu, terutama saat volume pelamar tinggi.
- Rentan inkonsistensi — reviewer berbeda bisa menyoroti aspek berbeda dari CV yang sama.
- Sulit untuk melakukan pencarian cepat ("siapa saja kandidat yang punya pengalaman Kubernetes 3+ tahun?").

**Solusi yang diusulkan:** Sistem RAG (Retrieval-Augmented Generation) yang membaca dokumen CV (PDF/Word/Markdown), mengindeksnya, dan menghasilkan ringkasan terstruktur + menjawab pertanyaan ad-hoc dari HRD berbasis isi CV yang diunggah.

---

## 2. Goals & Non-Goals

### Goals (POC)
- Upload 1 atau banyak CV (PDF/DOCX/MD) → sistem menghasilkan **ringkasan terstruktur** (nama, pengalaman kerja, skill, pendidikan, highlight relevan).
- HRD bisa mengajukan **pertanyaan bebas** terhadap satu CV atau kumpulan CV ("Apakah kandidat ini pernah pegang tim?", "Bandingkan pengalaman leadership kandidat A vs B").
- Jawaban harus **grounded** pada isi CV asli (bukan halusinasi), idealnya dengan sitasi ke bagian CV yang relevan.

### Non-Goals (untuk versi POC ini)
- Bukan sistem ATS (Applicant Tracking System) penuh — tidak menangani workflow rekrutmen, scheduling interview, dll.
- Belum menangani scoring/ranking otomatis kandidat secara final (bisa jadi fase berikutnya, tapi berisiko bias — perlu keputusan produk terpisah).
- Belum multi-tenant / multi-perusahaan.
- Belum perlu observability stack lengkap (Prometheus/Grafana/Tempo) — cukup logging dasar untuk debugging selama POC.

---

## 3. Target Pengguna

- **Primary:** Tim HRD/recruiter internal yang melakukan screening CV.
- **Sekunder (opsional):** Hiring manager yang ingin query cepat tanpa baca CV mentah.

---

## 4. User Stories

1. Sebagai recruiter, saya ingin upload CV (PDF/DOCX) dan langsung mendapat ringkasan singkat, supaya saya tidak perlu baca semua halaman.
2. Sebagai recruiter, saya ingin bertanya "Berapa tahun pengalaman total kandidat ini?" dan dapat jawaban akurat berdasarkan isi CV.
3. Sebagai recruiter, saya ingin membandingkan beberapa kandidat sekaligus berdasarkan kriteria tertentu (skill, jenjang, dsb).
4. Sebagai recruiter, saya ingin tahu bagian CV mana yang jadi dasar jawaban sistem (sitasi/reference), supaya saya bisa verifikasi manual.

---

## 5. Functional Requirements

| ID | Requirement | Prioritas |
|----|-------------|-----------|
| FR1 | Upload dokumen CV format PDF, DOCX, Markdown | Must |
| FR2 | Ekstraksi teks dari dokumen (termasuk PDF yang mungkin hasil scan → OCR fallback) | Must |
| FR3 | Chunking teks CV secara semantik (per section: pengalaman, pendidikan, skill, dll) | Must |
| FR4 | Generate embedding per chunk & simpan ke vector store | Must |
| FR5 | Endpoint untuk generate ringkasan otomatis per CV (structured output: nama, skill, pengalaman, pendidikan) | Must |
| FR6 | Endpoint Q&A: pertanyaan bebas → retrieval chunk relevan → jawaban dari LLM | Must |
| FR7 | Multi-CV query (bandingkan/cari di banyak CV sekaligus) | Should |
| FR8 | Sitasi/reference ke bagian CV asli dalam jawaban | Should |
| FR9 | Riwayat CV yang sudah diupload (list & re-query) | Could |
| FR10 | Re-index otomatis kalau CV diupdate/diganti | Could |

---

## 6. Non-Functional Requirements

- **Akurasi/Groundedness:** Jawaban tidak boleh halusinasi — jika informasi tidak ada di CV, sistem harus bilang "tidak ditemukan", bukan mengarang.
- **Latency:** Untuk POC, target respons Q&A < 5 detik untuk 1 CV; belum perlu optimasi agresif.
- **Skalabilitas:** POC cukup untuk puluhan–ratusan CV. Desain vector store sebaiknya tetap kompatibel untuk scale-up nanti (ribuan CV).
- **Privasi & Keamanan data:** CV berisi data pribadi (PII) — perlu dipikirkan sejak awal (enkripsi at-rest, retensi data, akses terbatas), meski untuk POC bisa disederhanakan.
- **Portabilitas:** Karena masih eksplorasi, hindari lock-in ke satu vendor LLM/vector DB tertentu selama belum ada keputusan final.

---

## 7. Arsitektur High-Level (Usulan Awal)

```
[Upload CV: PDF/DOCX/MD]
        │
        ▼
[Ingestion Service] --extract text--> [Parser: pypdf / python-docx / markdown]
        │
        ▼
[Chunking + Metadata Tagging] (per section CV)
        │
        ▼
[Embedding Model] --> [Vector Store: Chroma/Qdrant/pgvector]
        │
        ▼
[Retrieval Layer] <---- [Query dari HRD]
        │
        ▼
[LLM (Claude API)] --generate--> [Ringkasan / Jawaban + Sitasi]
        │
        ▼
[API Response ke Frontend/HRD]
```

Karena kamu sudah punya monorepo `ecommerce-platform` dengan pola FastAPI + Celery + shared-kernel, untuk POC ini saya sarankan **service terpisah dan ringan dulu** (bukan langsung masuk monorepo), supaya iterasi cepat tanpa terikat pola observability penuh yang dipakai di service lain. Bisa diintegrasikan belakangan kalau sudah matang.

---

## 8. Tech Stack Usulan (POC)

| Komponen | Opsi | Catatan |
|----------|------|---------|
| Parsing dokumen | `pypdf`/`pdfplumber` (PDF), `python-docx` (DOCX), native (MD) | pdfplumber lebih baik untuk layout kompleks |
| Chunking | Custom, berbasis heuristik section CV (regex/heading detection) | CV punya struktur semi-konsisten (Pengalaman, Pendidikan, dll) |
| Embedding | OpenAI/Voyage/Cohere embedding API, atau lokal (sentence-transformers) | Tergantung budget & concern privasi data |
| Vector store | Chroma (paling ringan untuk POC) atau pgvector (kalau mau selaras dengan Postgres yang sudah dipakai di service lain) | pgvector lebih mudah nanti kalau integrasi ke platform existing |
| LLM untuk generation | Claude API (Sonnet) | Untuk ringkasan & Q&A grounded |
| API Layer | FastAPI (konsisten dengan stack kamu) | Async endpoint untuk upload & query |
| Background processing | Celery (opsional untuk POC; bisa sync dulu kalau volume kecil) | Berguna kalau proses embedding banyak CV sekaligus |

---

## 9. Metrics Keberhasilan (POC)

- **Akurasi ringkasan**: HRD menilai ringkasan "cukup akurat" untuk ≥ 80% sample CV (evaluasi manual/spot-check).
- **Groundedness Q&A**: 0% jawaban yang mengarang informasi yang tidak ada di CV (diuji dengan pertanyaan jebakan).
- **Adopsi**: minimal 1 tim HRD mau pakai untuk screening batch nyata selama masa uji.
- **Waktu hemat**: estimasi pengurangan waktu screening per CV (baseline manual vs pakai sistem).

---

## 10. Risiko & Asumsi

| Risiko | Mitigasi |
|--------|----------|
| CV format tidak konsisten (desain kreatif, tabel, kolom ganda) → parsing gagal | Mulai dengan subset format umum, tambah fallback OCR |
| Data pribadi (PII) di CV — risiko compliance | Batasi akses, jangan kirim ke third-party LLM tanpa kebijakan data jelas |
| Halusinasi LLM saat CV tidak lengkap | Wajib sitasi + instruksi eksplisit "jawab tidak tahu jika tidak ada di konteks" |
| Bias jika nantinya dipakai untuk scoring/ranking otomatis | Sengaja di-exclude dari scope POC ini |

**Asumsi:** CV yang diupload berbahasa Indonesia dan/atau Inggris, volume awal masih kecil (puluhan dokumen), belum butuh multi-user concurrent yang berat.

---

## 11. Roadmap Bertahap

**Fase 1 (POC — fokus sekarang):**
Upload CV → parsing → chunking → embedding → ringkasan otomatis single-CV.

**Fase 2:**
Q&A per CV dengan sitasi + evaluasi groundedness.

**Fase 3:**
Multi-CV query & perbandingan kandidat.

**Fase 4 (kalau POC berhasil):**
Integrasi ke `ecommerce-platform`-style architecture — observability stack, database-per-service, dsb, sesuai kebutuhan skala nyata.

---

## 12. Keputusan (Update v0.2)

| Pertanyaan | Keputusan |
|------------|-----------|
| LLM & embedding model | Menggunakan **LiteLLM** sebagai abstraction layer, supaya provider (Claude/OpenAI/model lain) bisa diganti-ganti tanpa ubah kode inti. Model spesifik belum di-lock dari awal. |
| Bahasa CV | **Bilingual (ID + EN)** — parsing, chunking, dan Q&A harus bisa menangani CV maupun pertanyaan dalam kedua bahasa. Default bahasa jawaban: **English** (`response_language="en"`), bisa di-override per request. |
| Akses pengguna | Lewat **internal tool** (bukan akses langsung HRD ke API) — jadi butuh lapisan UI/dashboard internal sederhana di depan API. |
| Audit trail | **Belum diperlukan** untuk POC ini. Bisa jadi item roadmap lanjutan kalau nanti masuk tahap production/compliance. |

### Dampak ke desain sebelumnya:

- **Tech stack (Sec. 8)**: LLM & embedding call di-wrap lewat LiteLLM, jadi FastAPI service tidak manggil SDK provider tertentu secara langsung — cukup konfigurasi model string di `pydantic-settings` (selaras dengan pola konfigurasi yang biasa kamu pakai).
- **Chunking & parsing (Sec. 8 & Roadmap)**: perlu deteksi bahasa per dokumen/section, dan prompt untuk ringkasan/Q&A perlu instruksi eksplisit soal bilingual (jawab dalam bahasa yang sama dengan pertanyaan, atau selalu ID — ini jadi keputusan desain teknis berikutnya).
- **Arsitektur (Sec. 7)**: perlu tambahan komponen "Internal Tool/Dashboard" di depan API sebagai consumer, bukan HRD langsung hit endpoint.
- **Non-goals (Sec. 2)**: audit trail resmi masuk non-goals eksplisit untuk versi ini.

---

*Dokumen ini sudah update ke v0.2 dengan keputusan di atas. Bagian mana yang mau kita perdalam duluan — arsitektur teknis (parsing & chunking CV bilingual + integrasi LiteLLM), atau desain API endpoint & kontrak untuk internal tool?*
