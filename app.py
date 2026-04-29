import streamlit as st
import pandas as pd
import random
from seleniumbase import SB

st.set_page_config(page_title="Auchan Scraper", layout="wide")

def scrape_auchan(category_url, num_products):
    results = []
    
    # We use 'uc=False' here because 'activate_cdp_mode' handles the stealth 
    # without the need for the file-patching that causes PermissionError.
    with SB(uc=False, xvfb=True, headless=True) as sb:
        try:
            st.info("🌐 Opening Auchan via CDP Stealth...")
            sb.activate_cdp_mode(category_url)
            sb.sleep(5) 
            
            # Find Links
            elements = sb.find_elements("a[href*='/product/']")
            urls = list(set([el.get_attribute("href") for el in elements]))[:num_products]
            
            if not urls:
                st.error("No product links found. The site structure may have changed.")
                return pd.DataFrame()

            progress_bar = st.progress(0)
            for i, url in enumerate(urls):
                st.write(f"🔍 Parsing product {i+1}...")
                sb.open(url)
                sb.sleep(random.uniform(2, 4))
                
                try:
                    # Extraction logic (Updated selectors)
                    name = sb.get_text("h1")
                    brand = sb.get_text(".product-brand-name") if sb.is_element_visible(".product-brand-name") else "N/A"
                    # Manufacturer/Description often in this div
                    details = sb.get_text(".product-description") if sb.is_element_visible(".product-description") else "N/A"
                    
                    results.append({
                        "Name": name,
                        "Brand": brand,
                        "Information": details,
                        "URL": url
                    })
                except:
                    continue
                    
                progress_bar.progress((i + 1) / len(urls))
                
        except Exception as e:
            st.error(f"Error: {e}")
            
    return pd.DataFrame(results)

st.title("Auchan Poland Vacuum")
url_input = st.text_input("Auchan Category Link", "https://zakupy.auchan.pl/categories/higiena-i-kosmetyki/piel%C4%99gnacja-w%C5%82os%C3%B3w/3939")
count = st.number_input("Items to scrape", 1, 20, 5)

if st.button("Start Scraper"):
    data = scrape_auchan(url_input, count)
    if not data.empty:
        st.dataframe(data)
        # Excel Export
        data.to_excel("export.xlsx", index=False)
        with open("export.xlsx", "rb") as f:
            st.download_button("Download Excel", f, "auchan_data.xlsx")
