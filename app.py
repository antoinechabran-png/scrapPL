import streamlit as st
import pandas as pd
import time
import random

st.set_page_config(page_title="Auchan Scraper", layout="wide")

try:
    import httpx
    USE_HTTPX = True
except ImportError:
    import requests
    USE_HTTPX = False

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Headers — no Accept-Encoding so the library handles decompression itself
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://zakupy.auchan.pl/",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "Connection": "keep-alive",
}


def make_client():
    if USE_HTTPX:
        return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25, http2=True)
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch(client, url: str):
    """Returns (status_code, decoded_text, raw_bytes)."""
    try:
        r = client.get(url)
        return r.status_code, r.text, r.content
    except Exception as exc:
        return 0, str(exc), b""


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def is_binary(text: str) -> bool:
    if not text:
        return False
    sample = text[:500]
    bad = sum(1 for c in sample if ord(c) > 127 or ord(c) < 9)
    return bad / len(sample) > 0.10


def is_blocked(html: str) -> bool:
    lower = html.lower()
    return any(s in lower for s in [
        "just a moment", "enable javascript", "checking your browser",
        "cf-browser-verification", "ray id", "perimeterx", "px-captcha",
        "human verification", "access denied", "_cf_chl",
    ])


# ---------------------------------------------------------------------------
# Link discovery & detail extraction
# ---------------------------------------------------------------------------

def find_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    from urllib.parse import urlparse
    base = "{0.scheme}://{0.netloc}".format(urlparse(base_url))
    found: set[str] = set()
    for sel in ["a[href*='/product/']", "a[href*='/p/']",
                "a.product-tile__name", "a[data-testid='product-name']",
                "a.product-card__link"]:
        for tag in soup.select(sel):
            href = tag.get("href", "")
            if href.startswith("http"):
                found.add(href)
            elif href.startswith("/"):
                found.add(base + href)
    skip = {"/cart", "/login", "/account", "/search", "/categories"}
    return [u for u in found if not any(s in u for s in skip)]


def extract(soup: BeautifulSoup, url: str) -> dict:
    def t(*sels):
        for s in sels:
            el = soup.select_one(s)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        return "N/A"
    return {
        "Product Name": t("h1", "[data-testid='product-name']", ".product-name"),
        "Brand":        t("span[itemprop='brand']", "[data-testid='product-brand']", ".product-brand"),
        "Price":        t("[data-testid='product-price']", ".product-price", ".price", "span[itemprop='price']"),
        "Link": url,
    }


# ---------------------------------------------------------------------------
# Diagnosis panel
# ---------------------------------------------------------------------------

def show_diagnosis(html: str, raw: bytes, status: int):
    with st.expander("🔬 Diagnosis — click to expand"):
        if is_binary(html):
            st.error(
                f"**Binary/garbled response (HTTP {status}).**\n\n"
                "The server returned compressed data that couldn't be decoded, "
                "OR a Cloudflare JS challenge page. "
                "The hex dump below confirms this."
            )
        elif is_blocked(html):
            st.warning("**Bot-detection page detected** (Cloudflare / PerimeterX challenge).")
        else:
            st.info("Response looks like HTML but no product links were found — "
                    "the page structure may have changed.")

        st.markdown("""
### Root cause

Auchan PL is protected by **Cloudflare with JS challenges**.  
A plain HTTP client cannot execute JavaScript, so Cloudflare serves a challenge instead of real content.

### Fix options

| Solution | Effort | Cost |
|---|---|---|
| **Run locally** — your home IP is not flagged | ⭐ Easy | Free |
| **ScraperAPI / ZenRows / Bright Data** — managed proxy that solves JS challenges | ⭐⭐ Medium | ~$50/mo |
| **Playwright + stealth** on a VPS + residential proxy | ⭐⭐⭐ Hard | ~$20/mo |
| **Reverse the XHR API** — open DevTools → Network → Fetch/XHR on Auchan, find the JSON product endpoint, call it directly | ⭐⭐ Medium | Free |

The XHR API route is the most reliable long-term: modern SPAs like Auchan load product data via internal JSON APIs that are much simpler to call than scraping rendered HTML.
        """)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**HTML preview (first 1 000 chars):**")
            st.code(html[:1000] or "(empty)", language="html")
        with c2:
            st.markdown("**Hex dump (first 80 bytes):**")
            st.code(raw[:80].hex() if raw else "(empty)")


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

def scrape(category_url: str, num_products: int) -> pd.DataFrame:
    client = make_client()
    results = []

    # Warm-up
    st.info("🌐 Visiting homepage to collect cookies…")
    sc, html, raw = fetch(client, "https://zakupy.auchan.pl/")
    if is_binary(html) or is_blocked(html):
        st.error("🚫 Blocked at homepage.")
        show_diagnosis(html, raw, sc)
        return pd.DataFrame()
    st.success(f"Homepage OK — HTTP {sc}, {len(html):,} chars")
    time.sleep(random.uniform(2, 4))

    # Category page
    st.info("📂 Loading category page…")
    sc, html, raw = fetch(client, category_url)
    if is_binary(html) or is_blocked(html):
        st.error("🚫 Blocked at category page.")
        show_diagnosis(html, raw, sc)
        return pd.DataFrame()

    soup = BeautifulSoup(html, "lxml")
    links = find_links(soup, category_url)[:num_products]

    if not links:
        st.error("No product links found.")
        show_diagnosis(html, raw, sc)
        return pd.DataFrame()

    st.success(f"✅ {len(links)} product link(s) found.")

    # Product pages
    bar = st.progress(0)
    for i, url in enumerate(links):
        st.write(f"🔍 [{i+1}/{len(links)}] {url.split('/')[-1][:70]}")
        sc2, h2, _ = fetch(client, url)
        if not is_binary(h2) and not is_blocked(h2):
            results.append(extract(BeautifulSoup(h2, "lxml"), url))
        else:
            results.append({"Product Name": "BLOCKED", "Brand": "N/A", "Price": "N/A", "Link": url})
        bar.progress((i + 1) / len(links))
        time.sleep(random.uniform(2, 5))

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🛒 Auchan PL — Data Vacuum")

url_input = st.text_input(
    "Auchan Category URL",
    "https://zakupy.auchan.pl/categories/higiena-i-kosmetyki/piel%C4%99gnacja-w%C5%82os%C3%B3w/3939",
)
count = st.slider("Max products to scrape", 1, 20, 5)

if st.button("▶ Start Extraction"):
    data = scrape(url_input, count)
    if not data.empty:
        st.dataframe(data)
        data.to_excel("auchan_results.xlsx", index=False)
        with open("auchan_results.xlsx", "rb") as f:
            st.download_button("⬇ Download Excel", f, "auchan_results.xlsx")
    else:
        st.warning("No data collected.")
