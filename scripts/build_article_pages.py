#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import html
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_DIR = ROOT / "articles"
OUTPUT = ROOT / "assets" / "articles-data.js"

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)

def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")

def strip_tags(value):
    value = re.sub(r"<script\b[^>]*>.*?</script>", "", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", "", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()

def attr(tag, name):
    match = re.search(rf'\b{name}\s*=\s*(["\'])(.*?)\1', tag, flags=re.I | re.S)
    return html.unescape(match.group(2).strip()) if match else ""

def meta_value(text, key, prop=False):
    field = "property" if prop else "name"
    for tag in re.findall(r"<meta\b[^>]*>", text, flags=re.I):
        if attr(tag, field).lower() == key.lower():
            return attr(tag, "content")
    return ""

def first_match(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return strip_tags(match.group(1))
    return ""

def normalize_asset(src):
    src = html.unescape(src.strip())
    if src.startswith(("http://", "https://", "//")):
        return src
    while src.startswith("../"):
        src = src[3:]
    return src.lstrip("./")

def find_image(text):
    og = meta_value(text, "og:image", prop=True)
    if og:
        return normalize_asset(og), ""

    for tag in re.findall(r"<img\b[^>]*>", text, flags=re.I):
        src = attr(tag, "src")
        alt = attr(tag, "alt")
        lowered = src.lower()
        if not src or "favicon" in lowered or "logo" in lowered:
            continue
        return normalize_asset(src), alt

    return "assets/favicon.png", ""

def parse_date(text, path):
    candidates = [
        meta_value(text, "article:published_time", prop=True),
        meta_value(text, "date"),
        first_match(text, [
            rf'(({MONTHS})\s+\d{{1,2}},\s+\d{{4}})',
            r'<time\b[^>]*datetime=["\']([^"\']+)["\']',
        ]),
    ]

    for raw in candidates:
        if not raw:
            continue
        raw = raw.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=None)
        except ValueError:
            pass
        for fmt in ("%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                pass

    # Fallback: date of the article's first Git commit.
    try:
        timestamp = subprocess.check_output(
            ["git", "log", "--follow", "--diff-filter=A", "-1", "--format=%ct", "--", str(path.relative_to(ROOT))],
            cwd=ROOT,
            text=True,
        ).strip()
        if timestamp:
            return datetime.fromtimestamp(int(timestamp))
    except Exception:
        pass

    return datetime.fromtimestamp(path.stat().st_mtime)

def parse_article(path):
    text = read_text(path)

    title = (
        meta_value(text, "og:title", prop=True)
        or first_match(text, [
            r"<h1\b[^>]*>(.*?)</h1>",
            r"<title\b[^>]*>(.*?)</title>",
        ])
        or path.stem.replace("-", " ").title()
    )
    title = re.sub(
        r"\s*[|–—-]\s*Massachusetts Distance Project\s*$",
        "",
        title,
        flags=re.I,
    ).strip()

    deck = (
        meta_value(text, "description")
        or meta_value(text, "og:description", prop=True)
        or first_match(text, [
            r'<p\b[^>]*class=["\'][^"\']*(?:deck|dek|subtitle|article-subtitle)[^"\']*["\'][^>]*>(.*?)</p>',
        ])
        or "Read the latest Massachusetts high school distance running coverage."
    )

    category = (
        first_match(text, [
            r'<div\b[^>]*class=["\'][^"\']*(?:card-category|category|eyebrow|kicker)[^"\']*["\'][^>]*>(.*?)</div>',
            r'<span\b[^>]*class=["\'][^"\']*(?:card-category|category|eyebrow|kicker)[^"\']*["\'][^>]*>(.*?)</span>',
        ])
        or "XC"
    )

    image, alt = find_image(text)

    return {
        "title": title,
        "deck": deck,
        "category": category,
        "href": f"articles/{path.name}",
        "image": image,
        "alt": alt or title,
        "_date": parse_date(text, path),
    }

def main():
    paths = sorted(ARTICLES_DIR.glob("*.html"))
    if not paths:
        raise SystemExit("No HTML article files found in /articles.")

    articles = [parse_article(path) for path in paths]
    articles.sort(key=lambda item: item["_date"], reverse=True)

    for article in articles:
        article.pop("_date", None)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "window.MDP_ARTICLES = " + json.dumps(articles, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Wrote {OUTPUT.relative_to(ROOT)} with {len(articles)} articles.")
    print(f"Homepage pages needed: {(len(articles) + 8) // 9}")

if __name__ == "__main__":
    main()
