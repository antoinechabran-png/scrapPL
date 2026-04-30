import streamlit as st
import pandas as pd
import random
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

st.set_page_config(page_title="Auchan Scraper", layout="wide")

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Standard stealth headers to avoid being blocked immediately
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    # Path to the driver installed by packages.txt
    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

def scrape_auchan(category_url, num_products):
    driver = get_driver()
    results = []
    
    try:
        st.info("🌐 Connecting to Auchan...")
        driver.get(category_url)
        # Give it time to load dynamic elements
        st.write("Waiting for page content...")
        import time
        time.sleep(7)
        
        # Scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)

        # 1. Gather Links
        # Targeting product card links
        links = driver.find_elements("css selector", "a[href*='/product/']")
        urls = list(set([el.get_attribute("href") for el in links]))[:num_products]
        
        if not urls:
            st.error("No product links found. This usually means the bot-check blocked the IP.")
            # Let's show a snippet of the page to debug
            # st.code(driver.page_source[:500]) 
            return pd.DataFrame()

        progress_bar = st.progress(0)
        for i, url in enumerate(urls):
            st.write(f"🔍 Parsing: {url.split('/')[-1]}")
            driver.get(url)
            time.sleep(random.uniform(4, 7))
            
            try:
                name = driver.find_element("css selector", "h1").text
                # Brand and Manufacturer are often in specific divs/spans
                brand = driver.find_element("css selector", "span[itemprop='brand']").text if driver.find_elements("css selector", "span[itemprop='brand']") else "N/A"
                
                results.append({
                    "Product Name": name,
                    "Brand": brand,
                    "Link": url
                })
            except:
                continue
                
            progress_bar.progress((i + 1) / len(urls))
            
    except Exception as e:
        st.error(f"Scraper Error: {e}")
    finally:
        driver.quit()
            
    return pd.DataFrame(results)

# --- UI ---
st.title("🛒 Auchan PL - Data Vacuum")
url_input = st.text_input("Auchan Category Link", "https://zakupy.auchan.pl/categories/higiena-i-kosmetyki/piel%C4%99gnacja-w%C5%82os%C3%B3w/3939")
count = st.slider("Products to scrape", 1, 20, 5)

if st.button("Start Extraction"):
    data = scrape_auchan(url_input, count)
    if not data.empty:
        st.dataframe(data)
        data.to_excel("auchan_results.xlsx", index=False)
        with open("auchan_results.xlsx", "rb") as f:
            st.download_button("Download Excel", f, "auchan_results.xlsx")
