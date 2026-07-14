"""번역 이력 로그.

`translations.json`에 slug 기준으로 upsert한다. 재번역하면 해당 slug 항목이
최신 시각으로 갱신된다. "마지막으로 번역한 글 이후"를 브라우저 대조 없이
이 파일만 보고 판단하기 위한 용도.

병렬 안전: glossary와 동일하게 fcntl 파일 락으로 read-modify-write를 직렬화한다.
"""

import fcntl
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("translations.json")


@contextmanager
def _lock(path: Path):
    lock_path = Path(str(path) + ".lock")
    f = open(lock_path, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def record_translation(
    slug: str,
    url: str,
    title: str,
    blocks: int,
    issues=None,
    path: Path = LOG_PATH,
) -> None:
    """번역 완료 1건을 기록. issues는 검증 미실행 시 None."""
    path = Path(path)
    with _lock(path):
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}

        data[slug] = {
            "url": url,
            "title": title,
            "translated_at": datetime.now().isoformat(timespec="seconds"),
            "blocks": blocks,
            "issues": issues,
        }

        # translated_at 내림차순 정렬 — 최신 번역이 위로.
        ordered = dict(
            sorted(data.items(), key=lambda kv: kv[1].get("translated_at", ""), reverse=True)
        )
        path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
