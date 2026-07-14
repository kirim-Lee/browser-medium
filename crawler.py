import fcntl
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager

_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_PROFILE_DIR = os.path.expanduser("~/.config/chrome-medium")

# 크롤 직렬화용 프로세스 간 락. 크롤러는 포트 9222의 '단일 공유 Chrome'을 조작하는데,
# new_tab 직후 js()가 활성 탭을 읽으므로 동시에 여러 프로세스가 크롤하면 서로의 탭을
# 읽어 콘텐츠가 뒤섞인다. 크롤 구간(new_tab~읽기)만 락으로 묶어 오염을 막는다. 크롤은
# 몇 초라 병렬성 손해가 거의 없다(느린 구간은 DeepL 번역이며 그건 락 밖에서 병렬 유지).
_CRAWL_LOCK_PATH = os.path.join(tempfile.gettempdir(), "medium-crawl.lock")


@contextmanager
def _crawl_lock():
    f = open(_CRAWL_LOCK_PATH, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def _launch_chrome():
    subprocess.Popen(
        [
            _CHROME_PATH,
            "--remote-debugging-port=9222",
            f"--user-data-dir={_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("Chrome 실행 중... 잠시 대기")
    time.sleep(3)


def _run_harness(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        "browser-harness",
        input=script,
        capture_output=True,
        text=True,
        shell=True,
        timeout=60,
    )


def fetch_article_html(url: str) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    script = f"""
import time
new_tab("{url}")
wait_for_load()
time.sleep(2)
html = js("document.querySelector('article.meteredContent, article') ? document.querySelector('article.meteredContent, article').outerHTML : ''")
if not html:
    print("ERROR:article_not_found")
else:
    open('{tmp}', 'w', encoding='utf-8').write(html)
    print("OK")
"""
    # 크롤 구간만 직렬화 — 병렬 실행 시 탭 간 콘텐츠 오염 방지.
    with _crawl_lock():
        proc = _run_harness(script)

        # Chrome 미실행 감지 → 자동 실행 후 1회 재시도
        if proc.returncode != 0 and "DevToolsActivePort" in proc.stderr:
            _launch_chrome()
            proc = _run_harness(script)

    stdout = proc.stdout.strip()
    if proc.returncode != 0 or "ERROR" in stdout:
        stderr = proc.stderr.strip()
        raise RuntimeError(f"크롤링 실패: {stderr or stdout}")

    try:
        with open(tmp, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
