from app.chunking.section_detector import detect_sections


def test_detect_experience_section_id():
    text = (
        "Ringkasan\n"
        "Backend engineer dengan 5 tahun pengalaman.\n\n"
        "Pengalaman Kerja\n"
        "Backend Engineer di PT Contoh (2021-2024)\n"
        "Memimpin migrasi ke microservices.\n"
    )
    sections = detect_sections(text)
    section_types = [s.section_type for s in sections]
    assert "experience" in section_types


def test_detect_education_section_en():
    text = "Education\nBachelor of Computer Science, University X, 2019\n"
    sections = detect_sections(text)
    assert any(s.section_type == "education" for s in sections)
