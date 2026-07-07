# Technical Design: Parsing & Chunking CV Bilingual (ID/EN)

**Referensi:** `PRD_RAG_CV_Summarization.md` v0.2
**Status:** Draft v0.1

---

## 1. Tujuan

Mendesain pipeline yang bisa:
1. Mem-parsing CV dari format PDF, DOCX, Markdown menjadi teks bersih.
2. Mendeteksi bahasa (ID/EN, bisa campuran dalam satu dokumen).
3. Mendeteksi struktur/section CV (Pengalaman, Pendidikan, Skill, dll — istilah ID maupun EN).
4. Memecah teks jadi chunk yang semantically meaningful, dengan metadata yang cukup untuk retrieval yang akurat.

---

## 2. Layer 1 — Document Parsing

### 2.1 Strategi per format

| Format | Library utama | Fallback |
|--------|---------------|----------|
| PDF | `pdfplumber` (lebih baik untuk layout kolom & tabel) | `pypdf` untuk PDF simpel; OCR (`pytesseract` + `pdf2image`) kalau halaman tidak punya extractable text (CV hasil scan) |
| DOCX | `python-docx` | — |
| Markdown | baca langsung sebagai teks | — |

### 2.2 Deteksi halaman butuh OCR

```python
def needs_ocr(page_text: str) -> bool:
    """Heuristik sederhana: kalau extractable text terlalu sedikit
    relatif terhadap ukuran halaman, kemungkinan itu hasil scan/gambar."""
    return len(page_text.strip()) < 20
```

### 2.3 Output Layer 1

Semua parser (apapun formatnya) diseragamkan ke satu struktur output, supaya layer berikutnya (section detection & chunking) tidak perlu tahu format asalnya:

```python
from pydantic import BaseModel

class ParsedDocument(BaseModel):
    source_filename: str
    raw_text: str
    pages: list[str] | None = None  # khusus PDF, per halaman
    extraction_method: str  # "native" | "ocr"
```

Ini penting untuk **observability**: field `extraction_method` berguna untuk logging/metrik nanti — kamu bisa tahu berapa persen CV yang butuh OCR (indikator kualitas dokumen input).

---

## 3. Layer 2 — Language Detection

CV bilingual bisa berarti dua hal:
- **Dokumen campuran** (ringkasan diri pakai EN, tapi riwayat kerja pakai ID) → deteksi bahasa **per section**, bukan per dokumen.
- **Query juga bisa dalam 2 bahasa** → ini ranah desain prompt di layer generation, bukan chunking, tapi metadata bahasa tetap perlu disimpan agar retrieval bisa dipertimbangkan.

**Library usulan:** `langdetect` (ringan, cukup akurat untuk teks >20 karakter) atau `fasttext` (`lid.176.bin`, lebih akurat tapi butuh model file ~1GB — overkill untuk POC). Untuk POC, `langdetect` cukup.

```python
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # hasil konsisten

def detect_language(text: str) -> str:
    try:
        return detect(text) if len(text.strip()) > 15 else "unknown"
    except Exception:
        return "unknown"
```

Deteksi dilakukan **setelah section detection** (Layer 3), diterapkan per section — supaya lebih presisi daripada deteksi 1x untuk seluruh dokumen.

---

## 4. Layer 3 — Section Detection

Ini bagian paling krusial karena chunking CV yang baik = chunking berbasis section, bukan sekadar potong per N karakter.

### 4.1 Pendekatan hybrid (bukan cuma regex, bukan cuma LLM)

**Step 1 — Heading dictionary (cepat & murah):**
Kumpulan pola heading umum dalam ID & EN, dicocokkan dengan regex terhadap baris yang polanya mirip heading (baris pendek, huruf besar semua/title case, sering diikuti garis kosong).

```python
SECTION_PATTERNS = {
    "experience": [
        r"pengalaman\s*kerja", r"riwayat\s*pekerjaan",
        r"work\s*experience", r"employment\s*history",
    ],
    "education": [
        r"pendidikan", r"riwayat\s*pendidikan",
        r"education", r"academic\s*background",
    ],
    "skills": [
        r"keahlian", r"kemampuan", r"skill(s)?",
        r"technical\s*skills", r"kompetensi",
    ],
    "summary": [
        r"ringkasan", r"tentang\s*saya", r"profil",
        r"summary", r"profile", r"about\s*me",
    ],
    "certifications": [
        r"sertifikasi", r"certifications?", r"pelatihan", r"training",
    ],
    "contact": [
        r"kontak", r"contact\s*(information)?", r"data\s*diri",
    ],
}
```

**Step 2 — Heuristik baris heading:**
```python
def looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    # Heading biasanya pendek, tanpa tanda baca akhir kalimat
    return not stripped.endswith((".", ",")) and len(stripped.split()) <= 6
```

**Step 3 — Fallback LLM classification (kalau heuristik gagal / ambigu):**
Kalau setelah Step 1–2 masih ada blok teks besar yang tidak ter-assign ke section manapun (misal karena CV pakai desain kreatif/tabel), kirim blok itu ke LLM (lewat LiteLLM) dengan prompt klasifikasi ringan:

> "Klasifikasikan potongan teks CV berikut ke salah satu kategori: experience, education, skills, summary, certifications, contact, other. Hanya jawab satu kata kategori."

Ini dipakai **sebagai fallback**, bukan default, supaya biaya API tetap rendah untuk mayoritas CV yang formatnya standar.

### 4.2 Output Layer 3

```python
class CVSection(BaseModel):
    section_type: str        # "experience" | "education" | "skills" | ...
    content: str
    language: str             # hasil dari Layer 2, per-section
    detection_method: str      # "heading_match" | "llm_fallback"
    order_index: int          # urutan kemunculan di dokumen asli
```

---

## 5. Layer 4 — Chunking

### 5.1 Prinsip

- **Section = unit chunk utama.** Section pendek (skill, contact) → 1 section = 1 chunk.
- **Section panjang** (experience dengan banyak pengalaman kerja) → dipecah lebih lanjut per **sub-entry** (misal per posisi pekerjaan), baru kalau masih terlalu panjang, dipecah lagi berbasis token dengan overlap.

### 5.2 Aturan ukuran

| Kondisi | Aksi |
|---------|------|
| Section < 500 token | 1 chunk langsung |
| Section 500–1500 token, ada sub-struktur jelas (bullet/tanggal per entry) | Split per entry (misal per pekerjaan/per gelar) |
| Section > 1500 token tanpa sub-struktur jelas | Sliding window token-based, chunk ~500 token, overlap ~50 token |

### 5.3 Metadata per chunk (final, siap masuk vector store)

```python
class CVChunk(BaseModel):
    chunk_id: str
    document_id: str          # id CV asal
    source_filename: str
    section_type: str
    language: str
    content: str
    order_index: int
    char_count: int
    extraction_method: str    # diwariskan dari ParsedDocument
```

Metadata ini penting untuk retrieval yang **filterable** — misalnya nanti HRD tanya "pengalaman kerja kandidat ini apa saja", retrieval bisa di-bias/filter ke `section_type="experience"` dulu sebelum semantic search, supaya hasilnya lebih presisi daripada full semantic search ke semua chunk.

---

## 6. Pipeline End-to-End (ringkasan alur)

```
[File CV] 
   → Layer 1: Parsing (format-specific) → ParsedDocument
   → Layer 3: Section Detection (heading dict → heuristik → LLM fallback) → list[CVSection]
   → Layer 2: Language Detection (per section)
   → Layer 4: Chunking (per section, dengan sub-split kalau perlu) → list[CVChunk]
   → Embedding (via LiteLLM) → simpan ke vector store dengan metadata di atas
```

Catatan urutan: Language Detection saya taruh **setelah** Section Detection secara eksekusi (walau ditulis Layer 2), karena akurasinya lebih baik dievaluasi per section daripada per dokumen utuh.

---

## 7. Edge Cases yang Perlu Diantisipasi

| Kasus | Penanganan |
|-------|-----------|
| CV desain kreatif (2 kolom, infografis) | pdfplumber bisa salah urutan baca kolom → perlu deteksi layout kolom atau fallback OCR + LLM section classification |
| CV tanpa heading eksplisit (paragraf naratif) | Fallback ke LLM full-document section classification (bagi teks jadi paragraf, klasifikasi masing-masing) |
| Section campur bahasa dalam satu section (satu bullet EN, bullet lain ID) | Deteksi bahasa cukup dilakukan di level section (bukan sub-kalimat) untuk POC — cukup granular, dan menghindari over-engineering |
| CV sangat pendek (1 halaman padat) | Section-based chunking tetap dipakai, threshold "section besar" jarang tercapai jadi tidak masalah |

---

## 8. Keputusan (Update v0.2)

1. **Vector store**: **pgvector**. Konsekuensi: metadata chunk (`section_type`, `language`, `document_id`, dll) disimpan sebagai kolom biasa di tabel Postgres yang sama dengan kolom `embedding vector(N)`, sehingga filtering (`WHERE section_type = 'experience'`) bisa digabung langsung dengan `ORDER BY embedding <=> query_embedding` dalam satu query SQL — tidak perlu vector DB terpisah.
2. **Threshold token chunking**: **dijadikan parameter input**, bukan nilai fix. `CVChunk` generation menerima `chunk_size_tokens` dan `chunk_overlap_tokens` sebagai argumen (dengan default value ~500/50 kalau tidak diisi), supaya bisa dieksperimen tanpa ubah kode.
3. **Bahasa jawaban default**: **Bahasa Indonesia**. Kalau HRD bertanya dalam EN, sistem tetap bisa retrieve chunk apapun bahasanya, tapi jawaban akhir dari LLM di-generate dalam ID kecuali diminta eksplisit sebaliknya.

Ini akan tercermin di kontrak API pada dokumen desain endpoint berikutnya.

---

*Lanjut ke desain API endpoint & kontrak untuk internal tool — lihat `Design_API_Endpoints.md`.*
