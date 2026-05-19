import json
import os
from datetime import datetime
from pathlib import Path

from validators.nltk_filter import detect_suspicious_paragraphs, extract_paragraphs
from validators.llm_validator import validate_with_llm


def run_validator(
    translated_path,
    original_path,
    threshold: int = 1,
    nltk_only: bool = False,
    skip_short: int = 100,
    report_dir=Path("reports"),
) -> dict:
    translated_path = Path(translated_path)
    original_path = Path(original_path)

    src_paragraphs = extract_paragraphs(original_path.read_text(encoding="utf-8"))
    tgt_paragraphs = extract_paragraphs(translated_path.read_text(encoding="utf-8"))

    flagged = detect_suspicious_paragraphs(src_paragraphs, tgt_paragraphs, threshold)

    issues = []
    nltk_only_flags = []

    if not nltk_only and flagged:
        auth_key = os.getenv("ANTHROPIC_API_KEY")
        if not auth_key:
            print("[warn] ANTHROPIC_API_KEY 없음 — nltk 결과만 사용")
            nltk_only = True

    if not nltk_only and flagged:
        llm_results = validate_with_llm(flagged, auth_key, skip_short)
        for r in llm_results:
            if r.get("llm_confirmed"):
                issues.append(
                    {
                        "paragraph_index": r["index"],
                        "src_sentence_count": r["src_count"],
                        "tgt_sentence_count": r["tgt_count"],
                        "llm_confirmed": True,
                        "issue_description": r.get("issue_description"),
                        "suggestion": r.get("suggestion"),
                        "src_text": r["src_text"],
                        "tgt_text": r["tgt_text"],
                    }
                )
            else:
                note = "LLM 검증 결과 문제 없음 (오탐)" if r.get("llm_confirmed") is False else "LLM 검증 스킵"
                nltk_only_flags.append({"paragraph_index": r["index"], "note": note})
    else:
        for f in flagged:
            nltk_only_flags.append({"paragraph_index": f["index"], "note": "LLM 검증 미실행"})

    report = {
        "file": str(translated_path),
        "validated_at": datetime.now().isoformat(),
        "summary": {
            "total_paragraphs": len(src_paragraphs),
            "nltk_flagged": len(flagged),
            "llm_confirmed_issues": len(issues),
        },
        "issues": issues,
        "nltk_only_flags": nltk_only_flags,
    }

    if report_dir is not None:
        report_dir = Path(report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        slug = translated_path.parent.name
        report_path = report_dir / f"{slug}_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)

    return report
