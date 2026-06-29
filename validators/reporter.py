import json
from datetime import datetime
from pathlib import Path

from validators.nltk_filter import (
    detect_suspicious_paragraphs,
    detect_untranslated_paragraphs,
    extract_paragraphs,
)
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

    # 미번역(영문 원문 그대로) 단락은 객관적 판정이므로 LLM 없이 바로 이슈로 등록
    untranslated = detect_untranslated_paragraphs(src_paragraphs, tgt_paragraphs)
    untranslated_idx = {u["index"] for u in untranslated}
    for u in untranslated:
        issues.append(
            {
                "paragraph_index": u["index"],
                "untranslated": True,
                "llm_confirmed": False,
                "issue_description": "단락이 번역되지 않고 영문 원문이 그대로 남아 있습니다 (DeepL 호출 실패 추정).",
                "suggestion": None,
                "src_text": u["src_text"],
                "tgt_text": u["tgt_text"],
            }
        )

    # 미번역으로 이미 잡힌 단락은 문장 수 LLM 검증에서 제외 (중복 방지)
    flagged = [f for f in flagged if f["index"] not in untranslated_idx]

    if not nltk_only and flagged:
        llm_results = validate_with_llm(flagged, skip_short)
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
            "untranslated": len(untranslated),
            "llm_confirmed_issues": len([i for i in issues if i.get("llm_confirmed")]),
            "total_issues": len(issues),
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
