import streamlit as st
import pandas as pd
import random
from seleniumbase import SB

# --- Page Configuration ---
st.set_page_config(page_title="Auchan PL Scraper", page_icon="🛒")

def scrape_auchan(category_url, num_products):
    results = []
    
    # uc=True: Enables Undetected-Chromedriver (bypass anti-bot)
    # xvfb=True: Required for running on Linux/Streamlit Cloud (virtual display)
    # headless=True: Run without a visible window
    with SB(uc=True, xvfb=True, headless=True) as sb:
        try:
            st.info("🚀 Opening Auchan... (Bypassing anti-bot checks)")
            sb.activate_cdp_mode(category_url)
            sb.sleep(5) # Wait for cloudflare/datadome to settle
            
            # 1. Gather Product URLs
            # We look for links containing '/product/' or within the product grid
            st.text("🔎 Finding product links...")
            elements = sb.find_elements("a[href*='/product/']")
            urls = list(set([el.get_attribute("href") for el in elements]))[:num_products]
            
            if not urls:
                st.error("No products found. The site might be blocking the request or the selectors changed.")
                return pd.DataFrame()

            progress_bar = st.progress(0)
            
            # 2. Iterate through products
            for i, url in enumerate(urls):
                st.write(f"📄 Processing: {url.split('/')[-1]}")
                sb.open(url)
                sb.sleep(random.uniform(3, 6)) # Random delay to stay undetected
                
                # Extraction Logic
                # We use try/except for each field in case one is missing
                try:
                    name = sb.get_text("h1")
                    
                    # Brand is often in a specific span or data-attribute
                    brand = sb.get_text(".product-brand") if sb.is_element_visible(".product-brand") else "N/A"
                    
                    # Manufacturer info often hidden in details or 'producent' section
                    # We grab the main details container
                    info = sb.get_text("#product-details") if sb.is_element_visible("#product-details") else "N/A"
                    
                    results.append({
                        "Product Name": name,
                        "Brand": brand,
                        "Manufacturer Info": info,
                        "Link": url
                    })
                except Exception as e:
                    st.warning(f"Skipped an item due to error: {e}")
                
                progress_bar.progress((i + 1) / len(urls))
                
        except Exception as e:
            st.error(f"A critical error occurred: {e}")
            
    return pd.DataFrame(results)

# --- Streamlit UI ---
st.title("🛒 Auchan Poland Product Vacuum")
st.markdown("Extract product data directly into Excel while staying under the radar.")

with st.sidebar:
    st.header("Settings")
    url_input = st.text_input("Category URL", value="https://zakupy.auchan.pl/categories/higiena-i-kosmetyki/piel%C4%99gnacja-w%C5%82os%C3%B3w/3939")
    count = st.slider("Number of products to scrape", 1, 30, 5)

if st.button("Start Scraping"):
    if url_input:
        df = scrape_auchan(url_input, count)
        
        if not df.empty:
            st.success(f"Successfully scraped {len(df)} products!")
            st.dataframe(df)
            
            # Excel Export logic
            output_file = "auchan_data.xlsx"
            df.to_excel(output_file, index=False, engine='openpyxl')
            
            with open(output_file, "rb") as f:
                st.download_button(
                    label="📥 Download Excel Report",
                    data=f,
                    file_name="auchan_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.warning("Please provide a valid URL.")
