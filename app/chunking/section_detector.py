import re

from pydantic import BaseModel

SECTION_PATTERNS: dict[str, list[str]] = {
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

_COMPILED_PATTERNS = {
    section_type: [re.compile(p, re.IGNORECASE) for p in patterns]
    for section_type, patterns in SECTION_PATTERNS.items()
}


class CVSection(BaseModel):
    section_type: str
    content: str
    language: str = "unknown"  # diisi oleh language_detector
    detection_method: str  # "heading_match" | "llm_fallback"
    order_index: int


def looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    return not stripped.endswith((".", ",")) and len(stripped.split()) <= 6


def match_section_type(line: str) -> str | None:
    for section_type, patterns in _COMPILED_PATTERNS.items():
        if any(p.search(line) for p in patterns):
            return section_type
    return None


def detect_sections(raw_text: str) -> list[CVSection]:
    """Heuristik heading-match. Baris yang tidak ter-assign ke section manapun
    dikumpulkan sebagai section 'other' untuk kemudian dipertimbangkan masuk
    fallback LLM classification di layer atasnya (lihat services/summary_service.py)."""
    lines = raw_text.split("\n")
    sections: list[CVSection] = []

    current_type = "other"
    current_content: list[str] = []
    order_index = 0

    def flush():
        nonlocal current_content, order_index
        content = "\n".join(current_content).strip()
        if content:
            sections.append(
                CVSection(
                    section_type=current_type,
                    content=content,
                    detection_method="heading_match",
                    order_index=order_index,
                )
            )
            order_index += 1
        current_content = []

    for line in lines:
        if looks_like_heading(line):
            matched = match_section_type(line)
            if matched:
                flush()
                current_type = matched
                continue
        current_content.append(line)

    flush()
    return sections
