import re

import deepl
from markdownify import markdownify as md


_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_NO_TRANSLATE = {"code", "image"}


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

    for block in blocks:
        btype = block["type"]

        if btype in _NO_TRANSLATE:
            result.append(block)
            continue

        raw = block.get("text", "")
        if not raw.strip():
            result.append(block)
            continue

        try:
            if btype == "paragraph":
                text = _paragraph_to_md(block["html"])
                protected, codes = _protect_inline_code(text)
                translated = translator.translate_text(protected, target_lang=target_lang).text
                translated = _restore_inline_code(translated, codes)
            else:
                translated = translator.translate_text(raw, target_lang=target_lang).text

            result.append({**block, "translated": translated})

        except Exception as e:
            print(f"[warn] 번역 실패, 원문 유지: {e}")
            result.append({**block, "translated": raw})

    return result
