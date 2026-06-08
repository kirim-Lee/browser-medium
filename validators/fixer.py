from pathlib import Path


def apply_fixes(translated_path, issues: list) -> dict:
    """issues의 suggestion을 index.md에 반영. {fixed: [...], skipped: [...]} 반환."""
    path = Path(translated_path)
    content = path.read_text(encoding="utf-8")

    fixed = []
    skipped = []
    for issue in issues:
        idx = issue.get("paragraph_index")
        tgt_text = issue.get("tgt_text", "")
        suggestion = issue.get("suggestion", "")
        if not tgt_text or not suggestion:
            skipped.append({"index": idx, "reason": "suggestion 없음"})
            continue
        if tgt_text in content:
            content = content.replace(tgt_text, suggestion, 1)
            fixed.append({"index": idx, "tgt_text": tgt_text, "suggestion": suggestion})
        else:
            skipped.append({"index": idx, "reason": "원문 텍스트를 파일에서 찾지 못함"})

    if fixed:
        path.write_text(content, encoding="utf-8")

    return {"fixed": fixed, "skipped": skipped}
