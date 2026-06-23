from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BLOCKED_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".mp4", ".mp3",
    ".doc", ".docx", ".xls", ".exe",
)


def is_fetchable_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        path = (parsed.path or "").lower()
        return not any(path.endswith(ext) for ext in BLOCKED_EXTENSIONS)
    except Exception:
        return False


def fetch_page_text(url: str, timeout: float = 8.0) -> str:
    """Заходит на сайт и извлекает текстовое содержимое."""
    if not is_fetchable_url(url):
        return ""

    if "wikipedia.org/wiki/" in url:
        wiki_text = _fetch_wikipedia_extract(url, timeout)
        if wiki_text:
            return wiki_text

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
        limits=httpx.Limits(max_connections=10),
    ) as client:
        for attempt in range(2):
            try:
                response = client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "html" not in content_type and "text" not in content_type:
                    return ""
                if len(response.content) > 2_000_000:
                    return ""
                encoding = response.encoding or "utf-8"
                html = response.content.decode(encoding, errors="replace")
                return extract_article_text(html)
            except Exception:
                if attempt == 0:
                    continue
                return ""
    return ""


def extract_article_text(html: str) -> str:
    """Извлекает основной текст со страницы, убирая меню и скрипты."""
    html = unescape(html)
    html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    html = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)

    chunks: list[str] = []

    for tag in ("article", "main"):
        for block in re.findall(rf"(?is)<{tag}[^>]*>(.*?)</{tag}>", html):
            text = _strip_tags(block)
            if len(text) > 200:
                chunks.append(text)

    if not chunks:
        for block in re.findall(
            r'(?is)<div[^>]+(?:class|id)=["\'][^"\']*'
            r"(?:content|article|post|entry|text|body)[^\"']*[\"'][^>]*>(.*?)</div>",
            html,
        ):
            text = _strip_tags(block)
            if len(text) > 300:
                chunks.append(text)

    if chunks:
        best = max(chunks, key=len)
        return _clean_text(best)[:3000]

    body_match = re.search(r"(?is)<body[^>]*>(.*?)</body>", html)
    if body_match:
        return _clean_text(_strip_tags(body_match.group(1)))[:3000]

    return _clean_text(_strip_tags(html))[:3000]


def _strip_tags(html: str) -> str:
    html = re.sub(r"(?is)<(nav|header|footer|aside|form)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return html


def _clean_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_wikipedia_extract(url: str, timeout: float) -> str:
    try:
        from urllib.parse import unquote, urlparse

        parsed = urlparse(url)
        lang = parsed.netloc.split(".")[0]
        title = unquote(parsed.path.split("/wiki/", 1)[-1]).replace("_", " ")
        api = f"https://{lang}.wikipedia.org/w/api.php"
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            r = client.get(api, params={
                "action": "query",
                "titles": title,
                "prop": "extracts",
                "explaintext": True,
                "exintro": False,
                "exchars": 3000,
                "format": "json",
                "origin": "*",
            })
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            for page in pages.values():
                extract = page.get("extract", "")
                if extract:
                    return extract[:3000]
    except Exception:
        pass
    return ""


def extract_urls_from_text(text: str) -> list[str]:
    raw = re.findall(r"https?://[^\s\]>\"')]+", text)
    cleaned = []
    for url in raw:
        url = url.rstrip(".,;:!?)")
        if is_fetchable_url(url):
            cleaned.append(url)
    return list(dict.fromkeys(cleaned))