"""용어집(glossary) 관리.

`glossary.json`은 프로젝트 공유 자산이다. 모든 번역에 반복 등장하는 '코어 용어'만
담는다 — DeepL 기본 번역이 실제로 틀리고, 그 차이가 중요한 다단어 표현 위주.
일회성 전문어는 넣지 않는다(목록이 무한정 자라는 것을 막기 위함).

번역(A)은 이 파일을 '읽기만' 한다. 추가/삭제/좁히기는 `--review`(C)에서만 일어난다.
"""

import fcntl
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

GLOSSARY_PATH = Path("glossary.json")


@contextmanager
def _lock(path: Path):
    """glossary.json에 대한 배타 락. 동시 리뷰의 read-modify-write를 직렬화한다."""
    lock_path = Path(str(path) + ".lock")
    f = open(lock_path, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def merge_glossary_changes(changes: dict, path: Path = GLOSSARY_PATH) -> tuple:
    """동시 안전. 락을 걸고 디스크의 현재 glossary를 '다시 읽어' 델타만 병합 저장한다.

    메모리 스냅샷을 통째로 덮어쓰지 않으므로, 다른 리뷰가 그 사이 추가한 용어를
    지우지 않는다(갱신 유실 방지). (사람이 읽을 summary, 되돌리기용 inverse) 반환.
    inverse를 다시 merge_glossary_changes에 넘기면 이번 변경분만 정확히 되돌린다.
    """
    path = Path(path)
    with _lock(path):
        new = load_glossary(path)
        summary = []
        inverse = {"add": {}, "narrow": {}, "remove": []}

        for en, ko in (changes.get("add") or {}).items():
            if en not in new:
                new[en] = ko
                summary.append(f'+ 추가: "{en}" → "{ko}"')
                inverse["remove"].append(en)

        for old_en, narrowed_en in (changes.get("narrow") or {}).items():
            if old_en in new and narrowed_en not in new:
                new[narrowed_en] = new.pop(old_en)
                summary.append(f'~ 좁힘: "{old_en}" → "{narrowed_en}"')
                inverse["narrow"][narrowed_en] = old_en

        for en in (changes.get("remove") or []):
            if en in new:
                inverse["add"][en] = new[en]
                del new[en]
                summary.append(f'- 삭제: "{en}"')

        save_glossary(new, path)
    return summary, inverse


def load_glossary(path: Path = GLOSSARY_PATH) -> dict:
    """{영문 표현: 한국어 표현} 사전 반환. 없으면 빈 dict."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[warn] glossary.json 로드 실패, 무시: {e}")
        return {}


def save_glossary(glossary: dict, path: Path = GLOSSARY_PATH) -> None:
    """소스 표현 기준 정렬 후 저장 (diff를 깔끔하게)."""
    path = Path(path)
    ordered = {k: glossary[k] for k in sorted(glossary, key=str.lower)}
    path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


CACHE_PATH = Path(".glossary_cache.json")


def _glossary_hash(glossary: dict, source_lang: str, target_lang: str) -> str:
    payload = json.dumps(
        {"g": glossary, "s": source_lang, "t": target_lang}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _create_with_cleanup(translator, glossary, source_lang, target_lang, old_id):
    name = f"medium-shared-{source_lang}-{target_lang}"

    def _create():
        return translator.create_glossary(
            name, source_lang=source_lang, target_lang=target_lang, entries=glossary
        )

    if old_id:  # 내용이 바뀌었을 때만 기존 공유 글로서리 교체
        try:
            translator.delete_glossary(old_id)
        except Exception:
            pass
    try:
        return _create()
    except Exception as e:
        # 한도 초과("Too many glossaries") → 우리가 만든 medium-* 잔재를 싹 정리 후 1회 재시도
        if "glossar" in str(e).lower() or "quota" in str(e).lower():
            try:
                for g in translator.list_glossaries():
                    if g.name.startswith("medium-"):
                        try:
                            translator.delete_glossary(g)
                        except Exception:
                            pass
            except Exception:
                pass
            return _create()
        raise


def get_or_create_shared_glossary(
    translator, glossary: dict, source_lang: str, target_lang: str, cache_path: Path = CACHE_PATH
):
    """병렬 안전한 '공유' DeepL 글로서리. 실패/빈 경우 None.

    내용+언어쌍 해시로 캐시(.glossary_cache.json)해 서버 글로서리를 **1개만** 유지·재사용한다.
    실행마다 만들지/지우지 않으므로 병렬 실행 시 'Too many glossaries' 한도를 넘지 않는다.
    락으로 read-modify-write를 직렬화해, 동시에 여러 프로세스가 떠도 최초 1개만 생성된다.
    (공유 자산이므로 호출 측은 삭제하지 않는다.)
    """
    if not glossary:
        return None

    key = f"{source_lang}->{target_lang}"
    h = _glossary_hash(glossary, source_lang, target_lang)
    cache_path = Path(cache_path)
    try:
        with _lock(cache_path):
            cache = {}
            if cache_path.exists():
                try:
                    cache = json.loads(cache_path.read_text(encoding="utf-8"))
                except Exception:
                    cache = {}
            entry = cache.get(key)

            # 캐시 적중 + 내용 동일 → 서버에 아직 있으면 그대로 재사용
            if entry and entry.get("hash") == h:
                try:
                    return translator.get_glossary(entry["id"])
                except Exception:
                    pass  # 서버에서 사라졌으면 아래에서 재생성

            obj = _create_with_cleanup(
                translator, glossary, source_lang, target_lang, entry.get("id") if entry else None
            )
            cache[key] = {"hash": h, "id": obj.glossary_id}
            cache_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return obj
    except Exception as e:
        print(f"[warn] DeepL 글로서리 준비 실패, 미적용으로 진행: {e}")
        return None
