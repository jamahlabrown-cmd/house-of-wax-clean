#!/usr/bin/env python3
"""Generate static, crawlable HTML pages for House Of Wax listings.

The real marketplace is a single-URL Streamlit app (JS-rendered, one
generic /rest/v1 backend) -- search engines have nothing to index for the
hundreds of real records in inventory, since there's no per-item page.
This script fixes that: it reads Live (and previously-live) listings
straight from Supabase using the same public, RLS-scoped anon key the
live app itself uses, and writes one real static HTML page per listing
under docs/listings/, plus a browsable index and a full sitemap.xml.

Every generated page is discovery/SEO surface only -- the actual "buy"
action always links back to the real transactional listing on the live
app (?open_product=<id>). Pages are never deleted once generated, even
after an item sells; they're marked sold instead, so nothing 404s and
already-indexed pages keep their SEO value.

Runs on a schedule via .github/workflows/generate_listings.yml, which
commits its own output back to the repo so GitHub Pages serves the
latest version -- this is meant to be fully automatic going forward,
not a one-time export.

Required environment variables:
  SUPABASE_URL, SUPABASE_ANON_KEY -- same values the live app itself uses
"""
import os
import re
import html
import json
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
APP_URL = "https://house-of-wax-clean-5rqkikwpyr3xrappzemzjcb.streamlit.app"
SITE_URL = "https://shophouseofwax.com"
REQUEST_TIMEOUT = 30

REPO_ROOT = os.environ.get(
    "HOUSE_OF_WAX_REPO_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
LISTINGS_DIR = os.path.join(DOCS_DIR, "listings")

HEADERS = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
# Every field here is already on the public/anon-safe select list app.py
# itself uses (PRODUCTS_ANON_SAFE_SELECT) -- nothing pulled here is data a
# real anonymous site visitor couldn't already see in the live app.
PRODUCTS_SELECT = (
    "id,seller_id,category,artist,title,format,label,release_year,genre,"
    "media_grade,sleeve_grade,description,price,image_url,listing_status,updated_at"
)
# Anything the listing was ever publicly reachable as. Draft never was, so
# Draft items get no page -- nothing to index that a buyer could ever see.
PUBLIC_EVER_STATUSES = {"Live", "Pending Pickup/Payment", "Sold"}


def fetch_all(table, select, extra_params=None):
    params = {"select": select}
    if extra_params:
        params.update(extra_params)
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()


def money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return ""


def render_listing_page(p, seller_name):
    pid = p["id"]
    artist = html.escape(p.get("artist") or "")
    title = html.escape(p.get("title") or "")
    fmt = html.escape(p.get("format") or "")
    label = html.escape(p.get("label") or "")
    year = html.escape(str(p.get("release_year") or ""))
    genre = html.escape(p.get("genre") or "")
    media_grade = html.escape(p.get("media_grade") or "")
    sleeve_grade = html.escape(p.get("sleeve_grade") or "")
    desc_raw = (p.get("description") or "").strip()
    price = p.get("price") or 0
    image = (p.get("image_url") or "").strip()
    status = p.get("listing_status") or ""
    available = status == "Live"

    heading = f"{p.get('artist','').strip()} — {p.get('title','').strip()}".strip(" —") or f"Listing #{pid}"
    page_title = f"{html.escape(heading)} | House Of Wax"
    meta_desc_bits = [b for b in [p.get("artist"), p.get("title"), p.get("format"), money(price)] if b]
    meta_desc = html.escape(", ".join(meta_desc_bits)) or "Vinyl record for sale on House Of Wax."
    buy_url = f"{APP_URL}/?open_product={pid}"
    canonical = f"{SITE_URL}/listings/{pid}.html"

    json_ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": heading,
        "description": desc_raw or meta_desc,
        "category": p.get("category") or "Vinyl Records",
        "brand": {"@type": "Brand", "name": p.get("label") or "House Of Wax"},
        "offers": {
            "@type": "Offer",
            "url": buy_url,
            "priceCurrency": "USD",
            "price": f"{float(price):.2f}" if price else "0.00",
            "availability": "https://schema.org/InStock" if available else "https://schema.org/OutOfStock",
            "seller": {"@type": "Organization", "name": seller_name or "House Of Wax seller"},
        },
    }
    if image:
        json_ld["image"] = image

    status_banner = "" if available else (
        '<p style="color:#b45309;font-weight:600;">This item has sold. '
        'See what else is currently available on House Of Wax.</p>'
    )
    image_tag = (
        f'<img src="{html.escape(image)}" alt="{artist} — {title}" '
        f'style="max-width:100%;height:auto;border-radius:8px;">'
    ) if image else ""
    og_image = f'<meta property="og:image" content="{html.escape(image)}">' if image else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{page_title}</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="product">
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{canonical}">
{og_image}
<meta name="twitter:card" content="summary_large_image">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="application/ld+json">{json.dumps(json_ld)}</script>
<style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#171717;background:#fff;}}
a.buy{{display:inline-block;background:#caa14a;color:#0b0b0b;font-weight:700;padding:12px 24px;border-radius:8px;text-decoration:none;margin-top:16px;}}
a.back{{color:#666;text-decoration:none;}}
dl{{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;}}
dt{{font-weight:600;color:#555;}}
</style>
</head>
<body>
<p><a class="back" href="/listings/">&larr; All House Of Wax listings</a></p>
<h1>{artist} — {title}</h1>
{image_tag}
{status_banner}
<dl>
<dt>Format</dt><dd>{fmt or '&mdash;'}</dd>
<dt>Label</dt><dd>{label or '&mdash;'}</dd>
<dt>Year</dt><dd>{year or '&mdash;'}</dd>
<dt>Genre</dt><dd>{genre or '&mdash;'}</dd>
<dt>Vinyl condition</dt><dd>{media_grade or 'Not graded yet'}</dd>
<dt>Sleeve condition</dt><dd>{sleeve_grade or 'Not graded yet'}</dd>
<dt>Seller</dt><dd>{html.escape(seller_name or '')}</dd>
<dt>Price</dt><dd>{money(price) or 'Contact seller'}</dd>
</dl>
<p>{html.escape(desc_raw)}</p>
<a class="buy" href="{buy_url}">{"View &amp; buy on House Of Wax" if available else "See similar listings"}</a>
</body>
</html>
"""


def render_index_page(entries):
    entries = sorted(entries, key=lambda e: (not e["available"], (e["artist"] or "").lower()))
    available_count = sum(1 for e in entries if e["available"])
    rows = "\n".join(
        f'<li><a href="/listings/{e["id"]}.html">{html.escape(e["artist"])} — {html.escape(e["title"])}</a>'
        f'{" — " + money(e["price"]) if e["available"] and e["price"] else ""}'
        f'{"" if e["available"] else " (sold)"}</li>'
        for e in entries
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>All Listings | House Of Wax</title>
<meta name="description" content="Browse every record currently listed on House Of Wax, the marketplace built by crate-diggers for crate-diggers.">
<link rel="canonical" href="{SITE_URL}/listings/">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:720px;margin:40px auto;padding:0 20px;}}li{{margin:8px 0;}}</style>
</head><body>
<p><a href="/">&larr; House Of Wax</a></p>
<h1>All House Of Wax Listings</h1>
<p>{available_count} available now, {len(entries)} record{'s' if len(entries) != 1 else ''} tracked.</p>
<ul>
{rows}
</ul>
</body></html>
"""


def render_sitemap(urls):
    url_xml = "\n".join(
        f"  <url>\n    <loc>{loc}</loc>\n    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>"
        for loc, freq, pri in urls
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{url_xml}\n</urlset>\n'


def main():
    os.makedirs(LISTINGS_DIR, exist_ok=True)

    products = fetch_all("products", PRODUCTS_SELECT, {"order": "updated_at.desc"})
    sellers = {s["id"]: s.get("store_name") for s in fetch_all("sellers", "id,store_name")}

    relevant = [p for p in products if (p.get("listing_status") or "") in PUBLIC_EVER_STATUSES]

    entries = []
    sitemap_urls = [
        (f"{SITE_URL}/", "weekly", "1.0"),
        (f"{SITE_URL}/faq.html", "monthly", "0.7"),
        (f"{SITE_URL}/listings/", "daily", "0.9"),
    ]

    for p in relevant:
        pid = p["id"]
        seller_name = sellers.get(p.get("seller_id"), "")
        page_html = render_listing_page(p, seller_name)
        with open(os.path.join(LISTINGS_DIR, f"{pid}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)
        available = (p.get("listing_status") or "") == "Live"
        entries.append({
            "id": pid, "artist": p.get("artist") or "", "title": p.get("title") or "",
            "price": p.get("price") or 0, "available": available,
        })
        sitemap_urls.append((f"{SITE_URL}/listings/{pid}.html", "weekly", "0.6" if available else "0.3"))

    with open(os.path.join(LISTINGS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_index_page(entries))

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(render_sitemap(sitemap_urls))

    available_count = sum(1 for e in entries if e["available"])
    print(f"Generated {len(relevant)} listing page(s), {available_count} currently available.")


if __name__ == "__main__":
    main()
