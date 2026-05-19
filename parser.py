from bs4 import BeautifulSoup


_SKIP_CLASSES = {"pw-author-name", "pw-follower-count"}
_SKIP_PHRASES = {"not a member", "read this story for free"}


def _has_class(el, cls):
    return cls in (el.get("class") or [])


def _is_skip_heading(el):
    classes = set(el.get("class") or [])
    return bool(classes & _SKIP_CLASSES)


def _is_skip_blockquote(el):
    text = el.get_text().lower()
    return any(p in text for p in _SKIP_PHRASES)


def parse_article(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article", class_="meteredContent")
    if not article:
        raise ValueError("아티클 컨테이너를 찾을 수 없습니다.")

    title_el = article.find("h1", class_="pw-post-title")
    title = title_el.get_text(strip=True) if title_el else ""

    blocks = []
    for el in article.find_all(["h1", "h2", "h3", "h4", "p", "pre", "blockquote", "figure"]):
        tag = el.name

        if tag == "h1":
            if _has_class(el, "pw-post-title"):
                continue  # 제목은 별도 처리
            if _is_skip_heading(el):
                continue
            blocks.append({"type": "heading", "level": 1, "text": el.get_text(strip=True)})

        elif tag in ("h2", "h3", "h4"):
            if _is_skip_heading(el):
                continue
            if _has_class(el, "pw-subtitle-paragraph"):
                blocks.append({"type": "subtitle", "text": el.get_text(strip=True)})
            else:
                blocks.append({"type": "heading", "level": int(tag[1]), "text": el.get_text(strip=True)})

        elif tag == "p":
            if not _has_class(el, "pw-post-body-paragraph"):
                continue
            blocks.append({"type": "paragraph", "html": str(el), "text": el.get_text(strip=True)})

        elif tag == "pre":
            blocks.append({"type": "code", "text": el.get_text()})

        elif tag == "blockquote":
            if _is_skip_blockquote(el):
                continue
            blocks.append({"type": "blockquote", "text": el.get_text(strip=True)})

        elif tag == "figure":
            img = el.find("img")
            if img and img.get("src"):
                blocks.append({"type": "image", "src": img["src"], "alt": img.get("alt", "")})

    return {"title": title, "blocks": blocks}
