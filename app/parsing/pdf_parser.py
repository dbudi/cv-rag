from io import BytesIO

import pdfplumber

from app.parsing.base import ParsedDocument, needs_ocr


def _ocr_page(page) -> str:
    """Fallback OCR untuk halaman PDF hasil scan. Membutuhkan pytesseract +
    pdf2image terpasang beserta binary tesseract & poppler di sistem."""
    import pytesseract
    from pdf2image import convert_from_bytes

    # NOTE: implementasi penuh perlu akses ke bytes file asli per halaman.
    # Di skeleton ini, konversi dilakukan di level dokumen (lihat parse_pdf).
    raise NotImplementedError("Dipanggil lewat parse_pdf(), lihat implementasi di sana.")


def parse_pdf(file_bytes: bytes, filename: str) -> ParsedDocument:
    pages_text: list[str] = []
    any_ocr_used = False

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if needs_ocr(text):
                # Fallback OCR per halaman
                import pytesseract
                from pdf2image import convert_from_bytes

                images = convert_from_bytes(file_bytes)
                page_index = pdf.pages.index(page)
                if page_index < len(images):
                    text = pytesseract.image_to_string(images[page_index])
                    any_ocr_used = True
            pages_text.append(text)

    return ParsedDocument(
        source_filename=filename,
        raw_text="\n\n".join(pages_text),
        pages=pages_text,
        extraction_method="ocr" if any_ocr_used else "native",
    )
