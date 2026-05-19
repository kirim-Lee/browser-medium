import os
import subprocess
import tempfile


def fetch_article_html(url: str) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    script = f"""
import time
new_tab("{url}")
wait_for_load()
time.sleep(2)
html = js("document.querySelector('article.meteredContent') ? document.querySelector('article.meteredContent').outerHTML : ''")
if not html:
    print("ERROR:article_not_found")
else:
    open('{tmp}', 'w', encoding='utf-8').write(html)
    print("OK")
"""
    proc = subprocess.run(
        "browser-harness",
        input=script,
        capture_output=True,
        text=True,
        shell=True,
        timeout=60,
    )
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
