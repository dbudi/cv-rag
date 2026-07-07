from langdetect import DetectorFactory, detect

DetectorFactory.seed = 0  # hasil deteksi konsisten antar-run


def detect_language(text: str, min_chars: int = 15) -> str:
    if len(text.strip()) < min_chars:
        return "unknown"
    try:
        return detect(text)
    except Exception:
        return "unknown"
