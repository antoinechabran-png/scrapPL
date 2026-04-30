import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import random
import re

st.set_page_config(page_title="Auchan Scraper", layout="wide")

# ---------------------------------------------------------------------------
# Stealth session
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    """Return a session that looks like a real browser."""
    session = requests.Session()
    session.headers.update({
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
        "Accept-Encoding": "gzip, deflate, br",
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
    })
    return session


# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------

def fetch_page(session: requests.Session, url: str, label: str = "") -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = session.get(url, timeout=20, allow_redirects=True)
        if resp.status_code != 200:
            st.warning(f"HTTP {resp.status_code} for {label or url}")
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        st.warning(f"Request failed for {label or url}: {exc}")
        return None


def find_product_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """
    Try multiple CSS selectors that Auchan PL has used historically.
    Returns a deduplicated list of absolute product URLs.
    """
    selectors = [
        "a[href*='/product/']",          # older product path
        "a[href*='/p/']",                # shortened path variant
        "a.product-tile__name",          # named class variant
        "a[data-testid='product-name']", # test-id variant
        "a.product-card__link",          # card link variant
    ]
    found: set[str] = set()
    for sel in selectors:
        for tag in soup.select(sel):
            href = tag.get("href", "")
            if href:
                if href.startswith("http"):
                    found.add(href)
                elif href.startswith("/"):
                    # Build absolute URL from the base
                    from urllib.parse import urlparse
                    parsed = urlparse(base_url)
                    found.add(f"{parsed.scheme}://{parsed.netloc}{href}")
    return list(found)


def extract_product_details(soup: BeautifulSoup, url: str) -> dict:
    """Best-effort extraction of name, brand, price from a product page."""
    def try_select_text(*selectors) -> str:
        for sel in selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        return "N/A"

    name = try_select_text(
        "h1",
        "[data-testid='product-name']",
        ".product-name",
        ".product-title",
    )
    brand = try_select_text(
        "span[itemprop='brand']",
        "[data-testid='product-brand']",
        ".product-brand",
        ".brand-name",
    )
    price = try_select_text(
        "[data-testid='product-price']",
        ".product-price",
        ".price",
        "span[itemprop='price']",
        ".price-new",
    )

    return {"Product Name": name, "Brand": brand, "Price": price, "Link": url}


# ---------------------------------------------------------------------------
# Main scraping workflow
# ---------------------------------------------------------------------------

def scrape_auchan(category_url: str, num_products: int) -> pd.DataFrame:
    session = make_session()
    results = []

    # --- 1. Warm up: hit the homepage first (builds cookies, looks natural) ---
    st.info("🌐 Warming up session on Auchan homepage…")
    home_soup = fetch_page(session, "https://zakupy.auchan.pl/", "homepage")
    if home_soup is None:
        st.error("Cannot reach Auchan.pl at all — the site may be blocking this IP outright.")
        return pd.DataFrame()
    time.sleep(random.uniform(2, 4))

    # --- 2. Fetch category page ---
    st.info(f"📂 Loading category page…")
    cat_soup = fetch_page(session, category_url, "category page")
    if cat_soup is None:
        st.error("Category page fetch failed.")
        return pd.DataFrame()

    # --- 3. Find product links ---
    links = find_product_links(cat_soup, category_url)[:num_products]

    if not links:
        st.error(
            "No product links found on the category page.\n\n"
            "This usually means one of:\n"
            "- Bot detection blocked the request (Cloudflare / PerimeterX)\n"
            "- The page renders via JavaScript (links are injected after load)\n"
            "- The CSS selectors need updating for the current site structure\n\n"
            "See the **Debug** section below for the raw HTML snippet."
        )
        with st.expander("🔍 Debug: raw page HTML (first 3000 chars)"):
            st.code(str(cat_soup)[:3000], language="html")
        return pd.DataFrame()

    st.success(f"Found {len(links)} product links.")

    # --- 4. Scrape each product page ---
    progress = st.progress(0)
    for i, url in enumerate(links):
        st.write(f"🔍 [{i+1}/{len(links)}] {url.split('/')[-1][:60]}")
        prod_soup = fetch_page(session, url, f"product {i+1}")
        if prod_soup:
            results.append(extract_product_details(prod_soup, url))
        progress.progress((i + 1) / len(links))
        time.sleep(random.uniform(2, 5))   # polite crawl delay

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🛒 Auchan PL — Data Vacuum")

st.info(
    "⚠️ **Note:** Auchan's product pages are heavily JavaScript-rendered. "
    "If product details show as *N/A*, the page content is injected by JS after load — "
    "in that case only a full browser (Selenium) can extract it, but that approach "
    "is reliably blocked on shared cloud IPs. "
    "Running locally or with a residential proxy gives much better results."
)

url_input = st.text_input(
    "Auchan Category URL",
    "https://zakupy.auchan.pl/categories/higiena-i-kosmetyki/piel%C4%99gnacja-w%C5%82os%C3%B3w/3939",
)
count = st.slider("Max products to scrape", 1, 20, 5)

if st.button("▶ Start Extraction"):
    data = scrape_auchan(url_input, count)
    if not data.empty:
        st.dataframe(data)
        data.to_excel("auchan_results.xlsx", index=False)
        with open("auchan_results.xlsx", "rb") as f:
            st.download_button("⬇ Download Excel", f, "auchan_results.xlsx")
    else:
        st.warning("No data collected.")
