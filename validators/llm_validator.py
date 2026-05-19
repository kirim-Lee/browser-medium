import json

import anthropic

_PROMPT = """\
아래는 영어 원문과 한국어 번역입니다.
다음 항목을 검증하고 JSON으로만 응답하세요. 다른 텍스트는 출력하지 마세요.

원문:
{src}

번역:
{tgt}

응답 형식:
{{
    "missing_sentences": true or false,
    "meaning_distorted": true or false,
    "issue_description": null or "문제 설명",
    "suggestion": null or "수정 제안"
}}"""


def validate_with_llm(flagged: list, auth_key: str, skip_short: int = 100) -> list:
    """플래그된 단락만 Claude API로 검증. 토큰 절약을 위해 짧은 단락은 스킵."""
    client = anthropic.Anthropic(api_key=auth_key)
    results = []

    for item in flagged:
        src = item["src_text"]
        tgt = item["tgt_text"]

        if len(src) < skip_short:
            results.append({**item, "llm_confirmed": False, "skipped": True})
            continue

        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": _PROMPT.format(src=src, tgt=tgt)}],
            )
            parsed = json.loads(msg.content[0].text)
            results.append(
                {
                    **item,
                    "llm_confirmed": bool(parsed.get("missing_sentences") or parsed.get("meaning_distorted")),
                    "issue_description": parsed.get("issue_description"),
                    "suggestion": parsed.get("suggestion"),
                    "skipped": False,
                }
            )
        except Exception as e:
            print(f"[warn] LLM 검증 실패 (단락 {item['index']}): {e}")
            results.append({**item, "llm_confirmed": None, "skipped": False, "error": str(e)})

    return results
