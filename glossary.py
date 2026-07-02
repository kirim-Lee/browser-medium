"""용어집(glossary) 관리.

`glossary.json`은 프로젝트 공유 자산이다. 모든 번역에 반복 등장하는 '코어 용어'만
담는다 — DeepL 기본 번역이 실제로 틀리고, 그 차이가 중요한 다단어 표현 위주.
일회성 전문어는 넣지 않는다(목록이 무한정 자라는 것을 막기 위함).

번역(A)은 이 파일을 '읽기만' 한다. 추가/삭제/좁히기는 `--review`(C)에서만 일어난다.
"""

import fcntl
import json
import uuid
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


def make_deepl_glossary(translator, glossary: dict, source_lang: str, target_lang: str):
    """글로서리 dict로 DeepL 서버 글로서리 객체 생성. 실패/빈 경우 None.

    호출 측은 사용 후 반드시 translator.delete_glossary(obj)로 정리해야 한다.

    이름은 실행마다 고유(medium-translate-<uuid>)하게 만든다. 동시 번역 시
    프로세스끼리 같은 이름을 공유하지 않아 서로 간섭/삭제하지 않는다.
    """
    if not glossary:
        return None

    try:
        return translator.create_glossary(
            f"medium-translate-{uuid.uuid4().hex[:8]}",
            source_lang=source_lang,
            target_lang=target_lang,
            entries=glossary,
        )
    except Exception as e:
        print(f"[warn] DeepL 글로서리 생성 실패, 미적용으로 진행: {e}")
        return None
