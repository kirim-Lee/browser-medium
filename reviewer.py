"""개발 관점 번역 리뷰(C 패스).

`--review`에서만 실행. 동작:
  1. 원문 EN ↔ 번역 KO 단락을 나란히 LLM(claude -p)에 보내 '개발자가 읽기에
     기술적으로 맞고 자연스러운가'를 검토 (용어집 일치 여부가 아니라 의미·의도 기준).
  2. 고칠 단락은 수정안을 받아 index.md에 자동 반영.
  3. 부산물로 용어집 변경(추가/좁히기/삭제)을 제안받아 glossary.json에 자동 반영.

적용은 묻지 않고 바로 한다. 되돌리기는 main.py가 작업 완료 후 끝 게이트에서 처리.
"""

import json
import re
import subprocess

from validators.nltk_filter import extract_paragraphs

_CHUNK = 12  # 한 번의 claude 호출에 넣을 단락 수 (프롬프트 크기 제한)

_PROMPT = """\
너는 한국어 기술 번역을 검토하는 시니어 프론트엔드 개발자다.
아래는 영어 원문과 한국어 번역 단락들이다. 각 단락을 '개발자 독자' 관점에서 검토하라.

검토 기준:
- 기술 용어가 문맥에 맞게 번역됐는가 (예: "state"를 행정구역 '주'가 아니라 '상태'로).
- 아키텍처/패턴 고유 용어가 일반어로 뭉개지지 않았는가 (예: "feature component" → '주요 구성 요소' (X)).
- 의미 왜곡·누락이 없는가. 코드/식별자가 깨지지 않았는가.

또한, 이 문서에서 반복될 만한 '코어 기술 용어' 중 번역을 고정해두면 좋을 것을 용어집 변경으로 제안하라.
- add: DeepL이 자주 틀리는 다단어 영문 표현만. 단독 일상어(예: "state", "page")는 넣지 마라(오적용 위험).
- narrow: 기존 용어집 항목이 너무 광범위하면 다단어로 좁힐 것을 제안.
- remove: 잘못됐거나 무의미한 항목.

현재 용어집(참고):
{glossary}

검토할 단락들(JSON 배열, 각 항목은 {{id, src, tgt}}):
{pairs}

JSON으로만 응답하라. 다른 텍스트 금지.
{{
  "edits": [
    {{"id": <단락 id>, "fixed_ko": "<수정된 한국어 전체 단락. tgt를 그대로 두면 안 고침>", "reason": "<한 줄 사유>"}}
  ],
  "glossary_add": {{"<영문 표현>": "<한국어>"}},
  "glossary_narrow": {{"<기존 영문 표현>": "<더 좁힌 영문 표현>"}},
  "glossary_remove": ["<영문 표현>"]
}}
edits에는 실제로 고쳐야 하는 단락만 포함하라. 문제 없으면 edits는 빈 배열."""


def _call_claude(prompt: str) -> dict:
    # stdin=DEVNULL: claude 서브프로세스가 부모의 stdin(끝 게이트 확인 입력)을
    # 가로채지 않도록 차단. 없으면 파이프 입력 시 click.confirm이 EOF로 Abort된다.
    proc = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=180,
        stdin=subprocess.DEVNULL,
    )
    raw = proc.stdout.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    raw = match.group(1) if match else raw
    return json.loads(raw)


def review_translation(index_path, original_path, glossary: dict) -> dict:
    """리뷰 실행. 적용은 하지 않고 변경안만 모아 반환."""
    src = extract_paragraphs(open(original_path, encoding="utf-8").read())
    tgt = extract_paragraphs(open(index_path, encoding="utf-8").read())
    pairs = list(zip(src, tgt))

    edits = []            # {"tgt": 원본 한국어, "new": 수정본, "reason": ...}
    g_add, g_narrow, g_remove = {}, {}, []
    glossary_json = json.dumps(glossary, ensure_ascii=False, indent=2)

    for start in range(0, len(pairs), _CHUNK):
        chunk = pairs[start:start + _CHUNK]
        payload = [{"id": start + j, "src": s, "tgt": t} for j, (s, t) in enumerate(chunk)]
        prompt = _PROMPT.format(
            glossary=glossary_json,
            pairs=json.dumps(payload, ensure_ascii=False, indent=2),
        )
        try:
            resp = _call_claude(prompt)
        except Exception as e:
            print(f"[warn] 리뷰 실패 (단락 {start}~), 스킵: {e}")
            continue

        for e in resp.get("edits", []):
            idx = e.get("id")
            new = (e.get("fixed_ko") or "").strip()
            if idx is None or not new:
                continue
            old = pairs[idx][1]
            if new and new != old:
                edits.append({"tgt": old, "new": new, "reason": e.get("reason", "")})

        g_add.update(resp.get("glossary_add", {}) or {})
        g_narrow.update(resp.get("glossary_narrow", {}) or {})
        g_remove.extend(resp.get("glossary_remove", []) or [])

    return {
        "edits": edits,
        "glossary": {"add": g_add, "narrow": g_narrow, "remove": g_remove},
    }


def apply_content_edits(index_path, edits: list) -> int:
    """수정안을 index.md에 반영. 적용된 건수 반환."""
    text = open(index_path, encoding="utf-8").read()
    applied = 0
    for e in edits:
        if e["tgt"] and e["tgt"] in text:
            text = text.replace(e["tgt"], e["new"], 1)
            applied += 1
        else:
            print(f"[warn] 수정 대상 단락을 찾지 못해 스킵: {e['tgt'][:40]}...")
    if applied:
        open(index_path, "w", encoding="utf-8").write(text)
    return applied
