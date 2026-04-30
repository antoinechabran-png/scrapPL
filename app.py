import streamlit as st
import pandas as pd
import random
import os
from seleniumbase import SB

# --- THE FIX FOR PERMISSION ERROR ---
# This forces SeleniumBase to use the /tmp folder which is writable on Streamlit Cloud
os.environ["SELENIUMBASE_DRIVERS_PATH"] = "/tmp/seleniumbase/drivers"

st.set_page_config(page_title="Auchan Scraper", layout="wide")

def scrape_auchan(category_url, num_products):
    results = []
    
    # We use basic selenium mode but with stealth-enhancing options
    with SB(uc=False, xvfb=True, headless=True) as sb:
        try:
            st.info("🌐 Initializing Stealth Connection...")
            
            # Using CDP Mode to bypass anti-bot without needing to patch files
            sb.activate_cdp_mode(category_url)
            sb.sleep(5) 
            
            # Scroll down to load lazy-loaded products
            sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sb.sleep(2)

            # 1. Collect Product URLs
            elements = sb.find_elements("a[href*='/product/']")
            urls = list(set([el.get_attribute("href") for el in elements]))[:num_products]
            
            if not urls:
                st.error("No product links found. Site might be blocking the IP.")
                return pd.DataFrame()

            progress_bar = st.progress(0)
            for i, url in enumerate(urls):
                st.write(f"🔍 Parsing product {i+1} of {len(urls)}...")
                sb.open(url)
                sb.sleep(random.uniform(3, 5))
                
                try:
                    # Extraction Logic - targeting Auchan's specific layout
                    name = sb.get_text("h1")
                    
                    # Brand/Sub-brand often found in breadcrumbs or specific spans
                    brand = sb.get_text("span[itemprop='brand']") if sb.is_element_visible("span[itemprop='brand']") else "N/A"
                    
                    # Manufacturer info/Description
                    details = sb.get_text("#product-description") if sb.is_element_visible("#product-description") else "N/A"
                    
                    results.append({
                        "Name": name,
                        "Brand": brand,
                        "Information": details,
                        "URL": url
                    })
                except Exception as e:
                    st.warning(f"Skipped {url}: Data not found.")
                    continue
                    
                progress_bar.progress((i + 1) / len(urls))
                
        except Exception as e:
            st.error(f"Critical Error: {e}")
            
    return pd.DataFrame(results)

# --- Streamlit UI ---
st.title("🛒 Auchan PL - Data Vacuum")
st.markdown("This tool bypasses read-only restrictions and anti-bot headers.")

url_input = st.text_input("Category URL", "https://zakupy.auchan.pl/categories/higiena-i-kosmetyki/piel%C4%99gnacja-w%C5%82os%C3%B3w/3939")
count = st.number_input("Limit (items)", 1, 50, 5)

if st.button("🚀 Start Extraction"):
    data = scrape_auchan(url_input, count)
    if not data.empty:
        st.subheader("Data Preview")
        st.dataframe(data)
        
        # Export
        data.to_excel("auchan_export.xlsx", index=False)
        with open("auchan_export.xlsx", "rb") as f:
            st.download_button("📥 Download Excel File", f, "auchan_results.xlsx")
