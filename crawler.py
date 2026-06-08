import os
import subprocess
import tempfile
import time

_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_PROFILE_DIR = os.path.expanduser("~/.config/chrome-medium")


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
