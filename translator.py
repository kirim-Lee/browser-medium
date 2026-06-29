import re
import time

import deepl
from markdownify import markdownify as md


_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_NO_TRANSLATE = {"code", "image"}
_MAX_RETRIES = 2
_RETRY_BACKOFF = 1.5  # 초, 시도마다 곱연산


def _translate_text(translator, text: str, target_lang: str) -> str:
    """일시적 오류(rate-limit·네트워크)에 대비해 재시도. 끝까지 실패하면 예외 전파."""
    last_exc = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return translator.translate_text(text, target_lang=target_lang).text
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BACKOFF * (attempt + 1)
                print(f"[retry] 번역 실패({attempt + 1}/{_MAX_RETRIES}), {wait:.1f}s 후 재시도: {e}")
                time.sleep(wait)
    raise last_exc


def _protect_inline_code(text: str) -> tuple:
    codes = []

    def replace(m):
        codes.append(m.group(0))
        return f"[INLINE_{len(codes) - 1}]"

    return _INLINE_CODE_RE.sub(replace, text), codes


def _restore_inline_code(text: str, codes: list) -> str:
    for i, code in enumerate(codes):
        text = text.replace(f"[INLINE_{i}]", code)
    return text


def _paragraph_to_md(html: str) -> str:
    return md(html, strip=["a"]).strip()


def translate_blocks(blocks: list, auth_key: str, target_lang: str = "KO") -> list:
    translator = deepl.Translator(auth_key)
    result = []
    failures = []

    for i, block in enumerate(blocks):
        btype = block["type"]

        if btype in _NO_TRANSLATE:
            result.append(block)
            continue

        if btype == "list":
            try:
                translated_items = [
                    _translate_text(translator, item, target_lang)
                    for item in block.get("items", [])
                ]
                result.append({**block, "translated_items": translated_items})
            except Exception as e:
                print(f"[warn] 리스트 번역 실패, 원문 유지: {e}")
                failures.append({"index": i, "type": btype, "error": str(e)})
                result.append({**block, "translated_items": block.get("items", []), "translation_failed": True})
            continue

        raw = block.get("text", "")
        if not raw.strip():
            result.append(block)
            continue

        try:
            if btype == "paragraph":
                text = _paragraph_to_md(block["html"])
                protected, codes = _protect_inline_code(text)
                translated = _translate_text(translator, protected, target_lang)
                translated = _restore_inline_code(translated, codes)
            else:
                translated = _translate_text(translator, raw, target_lang)

            result.append({**block, "translated": translated})

        except Exception as e:
            print(f"[warn] 번역 실패, 원문 유지: {e}")
            failures.append({"index": i, "type": btype, "error": str(e)})
            result.append({**block, "translated": raw, "translation_failed": True})

    if failures:
        print(f"[warn] 번역 실패 단락 {len(failures)}개 (원문 유지): "
              + ", ".join(f"#{f['index']}({f['type']})" for f in failures))

    return result
