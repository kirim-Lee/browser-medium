from pathlib import Path
from urllib.parse import urlparse

import httpx


def download_images(blocks: list, images_dir: Path) -> list:
    images_dir.mkdir(parents=True, exist_ok=True)
    result = []

    for block in blocks:
        if block["type"] != "image":
            result.append(block)
            continue

        src = block["src"]
        try:
            filename = urlparse(src).path.split("/")[-1]
            if "." not in filename:
                filename += ".jpg"
            local_path = images_dir / filename

            resp = httpx.get(src, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)

            result.append({**block, "local_path": f"./images/{filename}"})
        except Exception as e:
            print(f"[warn] 이미지 다운로드 실패 ({src}): {e}")
            result.append(block)

    return result
