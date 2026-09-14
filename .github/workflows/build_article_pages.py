#!/usr/bin/env python3
from pathlib import Path
import re, html, subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_DIR = ROOT / "articles"
PER_PAGE = 9

def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")

def strip_tags(value):
    value = re.sub(r"<script\\b[^>]*>.*?</script>", "", value, flags=re.I|re.S)
    value = re.sub(r"<style\\b[^>]*>.*?</style>", "", value, flags=re.I|re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\\s+", " ", html.unescape(value)).strip()

def attr(tag, name):
    m = re.search(rf'\\b{name}\\s*=\\s*(["\\\'])(.*?)\\1', tag, flags=re.I|re.S)
    return html.unescape(m.group(2).strip()) if m else ""

def meta_value(text, key, prop=False):
    field = "property" if prop else "name"
    for tag in re.findall(r"<meta\\b[^>]*>", text, flags=re.I):
        if attr(tag, field).lower() == key.lower():
            return attr(tag, "content")
    return ""

def first_match(text, patterns):
    for pat in patterns:
        m = re.search(pat, text, flags=re.I|re.S)
        if m:
            return strip_tags(m.group(1))
    return ""

def normalize_asset_path(src):
    src = src.strip()
    if src.startswith(("http://","https://","//")):
        return src
    while src.startswith("../"):
        src = src[3:]
    return src.lstrip("./")

def image_from_html(text):
    og = meta_value(text, "og:image", prop=True)
    if og:
        return normalize_asset_path(og)
    for pat in [
        r'<img\\b[^>]*class=["\\\'][^"\\\']*(?:hero|feature|article-image)[^"\\\']*["\\\'][^>]*\\bsrc=["\\\']([^"\\\']+)["\\\']',
        r'<figure\\b[^>]*>.*?<img\\b[^>]*\\bsrc=["\\\']([^"\\\']+)["\\\']'
    ]:
        m = re.search(pat, text, flags=re.I|re.S)
        if m:
            return normalize_asset_path(html.unescape(m.group(1)))
    for tag in re.findall(r"<img\\b[^>]*>", text, flags=re.I):
        src = attr(tag, "src")
        low = src.lower()
        if src and "favicon" not in low and "logo" not in low:
            return normalize_asset_path(src)
    return "assets/favicon.png"

def parse_date(text, path):
    vals = [
        meta_value(text, "article:published_time", prop=True),
        meta_value(text, "date"),
        first_match(text, [
            r'<time\\b[^>]*datetime=["\\\']([^"\\\']+)["\\\']',
            r'<time\\b[^>]*>(.*?)</time>',
            r'([A-Z][a-z]+\\s+\\d{1,2},\\s+\\d{4})'
        ])
    ]
    for raw in vals:
        if not raw:
            continue
        raw = raw.strip().replace("Z","+00:00")
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=None)
        except:
            pass
        for fmt in ("%B %d, %Y","%b %d, %Y","%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except:
                pass
    try:
        ts = subprocess.check_output(
            ["git","log","-1","--format=%ct","--",str(path.relative_to(ROOT))],
            cwd=ROOT, text=True
        ).strip()
        if ts:
            return datetime.fromtimestamp(int(ts))
    except:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)

def parse_article(path):
    text = read_text(path)
    title = meta_value(text,"og:title",prop=True) or first_match(text,[
        r'<h1\\b[^>]*>(.*?)</h1>', r'<title\\b[^>]*>(.*?)</title>'
    ]) or path.stem.replace("-"," ").title()
    title = re.sub(r"\\s*[|–—-]\\s*Massachusetts Distance Project\\s*$","",title,flags=re.I).strip()
    deck = meta_value(text,"description") or meta_value(text,"og:description",prop=True) or first_match(text,[
        r'<p\\b[^>]*class=["\\\'][^"\\\']*(?:deck|dek|subtitle|article-subtitle)[^"\\\']*["\\\'][^>]*>(.*?)</p>'
    ]) or "Read the latest Massachusetts high school distance running coverage."
    category = first_match(text,[
        r'<div\\b[^>]*class=["\\\'][^"\\\']*(?:category|eyebrow|kicker)[^"\\\']*["\\\'][^>]*>(.*?)</div>',
        r'<span\\b[^>]*class=["\\\'][^"\\\']*(?:category|eyebrow|kicker)[^"\\\']*["\\\'][^>]*>(.*?)</span>'
    ]) or "XC"
    return {
        "title": title, "deck": deck, "category": category,
        "date": parse_date(text,path),
        "href": f"articles/{path.name}",
        "image": image_from_html(text),
    }

def page_filename(n):
    return "articles.html" if n == 1 else f"articles-page-{n}.html"

def card(a):
    return f"""
          <article class="article-card">
            <a class="card-image-link" href="{html.escape(a['href'], quote=True)}">
              <img src="{html.escape(a['image'], quote=True)}" alt="{html.escape(a['title'], quote=True)}">
            </a>
            <div class="card-body">
              <div class="card-category">{html.escape(a['category'])}</div>
              <h2><a href="{html.escape(a['href'], quote=True)}">{html.escape(a['title'])}</a></h2>
              <p>{html.escape(a['deck'])}</p>
              <a class="text-link" href="{html.escape(a['href'], quote=True)}">Read Article →</a>
            </div>
          </article>"""

def pagination(current,total):
    if total <= 1:
        return ""
    parts = []
    parts.append(
        f'<a class="page-arrow" href="{page_filename(current-1)}">← Previous</a>'
        if current > 1 else '<span class="page-arrow disabled">← Previous</span>'
    )
    for n in range(1,total+1):
        if n == current:
            parts.append(f'<span class="page-number active" aria-current="page">{n}</span>')
        else:
            parts.append(f'<a class="page-number" href="{page_filename(n)}">{n}</a>')
    parts.append(
        f'<a class="page-arrow" href="{page_filename(current+1)}">Next →</a>'
        if current < total else '<span class="page-arrow disabled">Next →</span>'
    )
    return '<nav class="pagination" aria-label="Article pages">' + "".join(parts) + '</nav>'

def render(page_num,total_pages,items):
    cards = "\n".join(card(a) for a in items)
    pager = pagination(page_num,total_pages)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Articles{' – Page '+str(page_num) if page_num>1 else ''} | Massachusetts Distance Project</title>
<meta name="description" content="Massachusetts Distance Project articles covering Massachusetts high school cross country and distance running.">
<link rel="icon" type="image/png" href="assets/favicon.png">
<style>
:root{{--blue:#1f6feb;--black:#080808;--soft-black:#111;--text:#f5f5f5;--muted:#a8a8a8;--border:#252525}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--black);color:var(--text);font-family:Arial,Helvetica,sans-serif;line-height:1.5}}
a{{color:inherit;text-decoration:none}} img{{display:block;width:100%}} .container{{width:min(1180px,calc(100% - 40px));margin:0 auto}}
header{{position:sticky;top:0;z-index:50;background:rgba(8,8,8,.96);border-bottom:1px solid var(--border)}} .nav{{min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:28px}}
.brand{{font-size:1rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}} .brand span{{color:var(--blue)}} .nav-links{{display:flex;gap:24px;font-size:.82rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em}} .nav-links a:hover,.nav-links a.active{{color:var(--blue)}}
.page-hero{{padding:82px 0 42px;border-bottom:1px solid var(--border)}} .eyebrow{{color:var(--blue);font-size:.78rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px}}
h1{{margin:0;font-size:clamp(2.4rem,6vw,5rem);line-height:.95;letter-spacing:-.05em}} .page-hero p{{max-width:700px;color:var(--muted);margin:18px 0 0;font-size:1.04rem}}
.articles-section{{padding:48px 0 70px}} .articles-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:28px}}
.article-card{{background:var(--soft-black);border:1px solid var(--border);overflow:hidden;min-width:0}} .card-image-link{{display:block;aspect-ratio:16/10;overflow:hidden;background:#181818}}
.article-card img{{width:100%;height:100%;object-fit:cover;transition:transform .25s ease}} .article-card:hover img{{transform:scale(1.025)}} .card-body{{padding:20px}}
.card-category{{color:var(--blue);font-size:.72rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase;margin-bottom:9px}} .article-card h2{{margin:0;font-size:1.32rem;line-height:1.12;letter-spacing:-.025em}}
.article-card h2 a:hover{{color:var(--blue)}} .article-card p{{color:var(--muted);font-size:.93rem;margin:12px 0 18px}} .text-link{{color:var(--blue);font-size:.78rem;font-weight:900;text-transform:uppercase;letter-spacing:.06em}}
.pagination{{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:9px;margin-top:48px}} .pagination a,.pagination span{{min-width:42px;height:42px;padding:0 13px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--border);background:var(--soft-black);font-size:.82rem;font-weight:900}}
.pagination a:hover{{border-color:var(--blue);color:var(--blue)}} .pagination .active{{background:var(--blue);border-color:var(--blue);color:white}} .pagination .disabled{{opacity:.35;cursor:default}} .page-arrow{{min-width:105px!important}}
footer{{border-top:1px solid var(--border);padding:30px 0;color:var(--muted);font-size:.82rem;text-align:center}}
@media(max-width:900px){{.articles-grid{{grid-template-columns:repeat(2,1fr)}}}} @media(max-width:640px){{.container{{width:min(100% - 24px,1180px)}}.nav-links{{display:none}}.articles-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header><div class="container nav"><a class="brand" href="index.html">Massachusetts <span>Distance Project</span></a><nav class="nav-links"><a href="index.html">Home</a><a class="active" href="articles.html">Articles</a><a href="index.html#photos">Photos</a><a href="index.html#moments">Memorable Moments</a></nav></div></header>
<main>
<section class="page-hero"><div class="container"><div class="eyebrow">MDP Coverage</div><h1>Articles</h1><p>Massachusetts high school cross country and distance running stories, previews, rankings and recaps.</p></div></section>
<section class="articles-section"><div class="container"><div class="articles-grid">
{cards}
</div>{pager}</div></section>
</main>
<footer><div class="container">Massachusetts Distance Project · The stories behind the finish line.</div></footer>
</body>
</html>"""

def main():
    paths = sorted(ARTICLES_DIR.glob("*.html"))
    articles = [parse_article(p) for p in paths]
    articles.sort(key=lambda x:x["date"], reverse=True)
    if not articles:
        raise SystemExit("No article HTML files found in articles/.")
    total = (len(articles)+PER_PAGE-1)//PER_PAGE
    for old in ROOT.glob("articles-page-*.html"):
        old.unlink()
    for n in range(1,total+1):
        subset = articles[(n-1)*PER_PAGE:n*PER_PAGE]
        (ROOT/page_filename(n)).write_text(render(n,total,subset),encoding="utf-8")
        print(f"Wrote {page_filename(n)} with {len(subset)} articles")
    print(f"{len(articles)} total articles -> {total} archive pages")

if __name__ == "__main__":
    main()
