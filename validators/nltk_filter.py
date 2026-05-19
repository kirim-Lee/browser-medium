import nltk


def extract_paragraphs(md_text: str) -> list:
    """마크다운에서 번역 대상 단락만 추출 (코드블록·헤딩·이미지·인용구 제외)."""
    paragraphs = []
    in_code = False
    current = []

    for line in md_text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            if current:
                text = " ".join(current).strip()
                if text:
                    paragraphs.append(text)
                current = []
            continue

        if in_code:
            continue

        stripped = line.strip()
        is_skippable = (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("![")
            or stripped.startswith(">")
            or stripped == "---"
            or (stripped.startswith("**") and stripped.endswith("**"))
        )

        if is_skippable:
            if current:
                text = " ".join(current).strip()
                if text:
                    paragraphs.append(text)
                current = []
        else:
            current.append(stripped)

    if current:
        text = " ".join(current).strip()
        if text:
            paragraphs.append(text)

    return paragraphs


def _import_kss():
    import io
    import sys

    buf = io.StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf
    try:
        import kss

        return kss
    except ImportError:
        return None
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


_kss = _import_kss()


def _count_sentences(text: str, language: str = "english") -> int:
    if language != "english" and _kss is not None:
        return len(_kss.split_sentences(text))
    return len(nltk.sent_tokenize(text, language=language))


def detect_suspicious_paragraphs(src_paragraphs: list, tgt_paragraphs: list, threshold: int = 1) -> list:
    """단락별 문장 수를 비교해 threshold 초과 차이가 나는 단락을 반환."""
    flagged = []
    for i, (src, tgt) in enumerate(zip(src_paragraphs, tgt_paragraphs)):
        src_count = _count_sentences(src, language="english")
        tgt_count = _count_sentences(tgt, language="korean")

        if abs(src_count - tgt_count) > threshold:
            flagged.append(
                {
                    "index": i,
                    "src_count": src_count,
                    "tgt_count": tgt_count,
                    "diff": abs(src_count - tgt_count),
                    "src_text": src,
                    "tgt_text": tgt,
                }
            )

    return flagged
