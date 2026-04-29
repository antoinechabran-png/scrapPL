import streamlit as st
import pandas as pd
import time
import random
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure Page
st.set_page_config(page_title="Auchan Scraper", layout="wide")

def init_driver():
    """Initializes an undetected chrome driver."""
    return Driver(uc=True, headless=True)

def scrape_auchan_category(url, max_items):
    driver = init_driver()
    data = []
    
    try:
        st.info("🔗 Connecting to Auchan...")
        driver.get(url)
        time.sleep(random.uniform(5, 8)) # Initial wait for anti-bot
        
        # 1. Collect Product Links
        # Selector for the product cards - might need adjustment if Auchan updates UI
        links_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
        product_urls = list(set([el.get_attribute("href") for el in links_elements]))[:max_items]
        
        progress_bar = st.progress(0)
        
        for index, p_url in enumerate(product_urls):
            st.write(f"🕵️ Scraping: {p_url}")
            driver.get(p_url)
            time.sleep(random.uniform(3, 6)) # Human-like pause
            
            try:
                # 2. Extract specific fields
                # Note: CSS selectors are examples; inspect the page for exact matches
                name = driver.find_element(By.TAG_NAME, "h1").text
                
                # Auchan often puts brand/manufacturer in a table or specific span
                brand = driver.find_element(By.CSS_SELECTOR, "span.product-brand").text if driver.find_elements(By.CSS_SELECTOR, "span.product-brand") else "N/A"
                
                # Manufacturer info is usually in the 'Description' or 'Technical' section
                details = driver.find_element(By.ID, "product-details-tab").text if driver.find_elements(By.ID, "product-details-tab") else "N/A"

                data.append({
                    "Product Name": name,
                    "Brand": brand,
                    "Details/Manufacturer": details,
                    "Link": p_url
                })
            except Exception as e:
                st.warning(f"Could not parse product {index}: {e}")
            
            progress_bar.progress((index + 1) / len(product_urls))
            
    finally:
        driver.quit()
        
    return pd.DataFrame(data)

# --- UI Interface ---
st.title("🛒 Auchan PL - Data Vacuum")
st.markdown("Enter a subcategory URL to extract product details into Excel.")

category_link = st.text_input("Category URL", placeholder="https://zakupy.auchan.pl/categories/...")
item_count = st.number_input("Number of items to scrape", min_value=1, max_value=50, value=5)

if st.button("🚀 Start Scraping"):
    if category_link:
        results_df = scrape_auchan_category(category_link, item_count)
        
        if not results_df.empty:
            st.success("✅ Scraping Complete!")
            st.dataframe(results_df)
            
            # Export to Excel
            output_file = "auchan_products.xlsx"
            results_df.to_excel(output_file, index=False)
            
            with open(output_file, "rb") as f:
                st.download_button(
                    label="📥 Download Excel File",
                    data=f,
                    file_name="auchan_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.error("Please enter a valid URL.")
