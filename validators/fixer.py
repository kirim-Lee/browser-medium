from pathlib import Path


def apply_fixes(translated_path, issues: list) -> int:
    """issues의 suggestion을 index.md에 반영. 수정된 단락 수 반환."""
    path = Path(translated_path)
    content = path.read_text(encoding="utf-8")

    fixed = 0
    for issue in issues:
        tgt_text = issue.get("tgt_text", "")
        suggestion = issue.get("suggestion", "")
        if not tgt_text or not suggestion:
            continue
        if tgt_text in content:
            content = content.replace(tgt_text, suggestion, 1)
            fixed += 1

    if fixed:
        path.write_text(content, encoding="utf-8")

    return fixed
