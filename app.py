import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import json
import os
import random
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURARE ---
st.set_page_config(page_title="Wine Watcher V4", page_icon="🍷", layout="wide")

WINES_FILE = "wines_list.json"
HISTORY_FILE = "price_history.json"
PASSWORD = "CodulEsteVinul"

# --- 2. LISTA EXTINSĂ DE SITE-URI (RETAIL + SPECIALIZATE) ---
SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/index/?q={q}"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product"},
    {"store": "eMAG", "search_url": "https://www.emag.ro/search/{q}"},
    {"store": "AlcoolScont", "search_url": "https://www.alcoolscont.ro/catalogsearch/result/?q={q}"},
    {"store": "Drinkz", "search_url": "https://drinkz.ro/catalogsearch/result/?q={q}"},
    {"store": "CrushWine", "search_url": "https://www.crushwineshop.ro/catalogsearch/result/?q={q}"},
    {"store": "WinePoint", "search_url": "https://www.winepoint.ro/?s={q}&post_type=product"},
    {"store": "ProduseMoldovenesti", "search_url": "https://produsemoldovenesti.ro/cauta?q={q}"},
    {"store": "LiquorHub", "search_url": "https://www.liquorhub.ro/catalogsearch/result/?q={q}"}
]

# --- 3. LOGICĂ DE PARSARE AN ȘI FORMAT ---
def parse_wine_details(full_name):
    # Căutăm anul (4 cifre care încep cu 19 sau 20)
    year_match = re.search(r'\b(19|20)\d{2}\b', full_name)
    year = year_match.group(0) if year_match else "N/A"
    
    # Căutăm formatul
    format_val = "0.75L" # Default
    if "magnum" in full_name.lower() or "1.5" in full_name: format_val = "1.5L (Magnum)"
    elif "3l" in full_name.lower() or "double magnum" in full_name.lower(): format_val = "3L"
    elif "0.375" in full_name or "375" in full_name: format_val = "0.375L"
    
    return year, format_val

# --- 4. MOTORUL DE EXTRACȚIE V3 ROBUST ---
def extract_price_v3(soup, url):
    text_pret = ""
    # Păstrăm logica ta de succes
    if "king.ro" in url:
        tag = soup.find("span", {"data-price-type": "finalPrice"})
        text_pret = tag.text if tag else ""
    elif "vinimondo.ro" in url:
        meta = soup.find("meta", property="product:price:amount")
        text_pret = meta["content"] if meta else ""
    else:
        # Selectori universali
        for sel in [".price-new", ".woocommerce-Price-amount", ".product-price", ".current-price"]:
            tag = soup.select_one(sel)
            if tag: 
                text_pret = tag.get_text()
                break

    if not text_pret:
        match = re.search(r'(\d{2,4}[\.,]\d{2})\s?(?:lei|RON)', soup.get_text(), re.IGNORECASE)
        if match: text_pret = match.group(1)

    if text_pret:
        clean = text_pret.replace(',', '.').replace(' ', '')
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", clean)
        if nums:
            val = float(nums[0])
            if val > 5000 and "emag" not in url: val /= 100
            return round(val, 2)
    return None

# --- 5. LOGICĂ DE CĂUTARE AVANSATĂ ---
def deep_search(site, query, scraper):
    search_url = site["search_url"].format(q=query.replace(" ", "+"))
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
    
    try:
        res = scraper.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        domain = "/".join(search_url.split("/")[:3])
        
        found_items = []
        # Căutăm primele 3 link-uri cele mai relevante pentru a acoperi ani/formate diferite
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"] if a["href"].startswith("http") else domain + a["href"]
            if any(word in a.get_text().lower() for word in query.lower().split()):
                links.append((a.get_text().strip(), href))
        
        # Luăm primele 3 rezultate unice
        seen_urls = set()
        for name, url in links[:5]:
            if url not in seen_urls and len(seen_urls) < 3:
                seen_urls.add(url)
                res_p = scraper.get(url, headers=headers, timeout=10)
                soup_p = BeautifulSoup(res_p.content, "html.parser")
                
                # Numele real de pe site (de obicei în H1)
                h1 = soup_p.find("h1")
                real_name = h1.get_text().strip() if h1 else name
                
                price = extract_price_v3(soup_p, url)
                if price:
                    year, fmt = parse_wine_details(real_name)
                    found_items.append({
                        "Magazin": site["store"],
                        "Vin Complet": real_name,
                        "An": year,
                        "Format": fmt,
                        "Preț (RON)": price,
                        "Link": url
                    })
        return found_items
    except: return []

# --- 6. UI ---
if "auth" not in st.session_state:
    st.title("🔐 Wine Watcher V4")
    pwd = st.text_input("Parola Crama:", type="password")
    if st.button("Log In"):
        if pwd == PASSWORD: st.session_state["auth"] = True; st.rerun()
else:
    st.title("🍷 Scrutin Național V4: Toate Site-urile & Toate Formatele")
    
    # Persistență
    if not os.path.exists(WINES_FILE): save_data(WINES_FILE, ["Le Volte dell'Ornellaia", "Tignanello"])
    wines = json.load(open(WINES_FILE, 'r'))
    
    with st.sidebar:
        st.header("🛒 Adaugă Vin Nou")
        new_w = st.text_input("Cuvinte cheie (ex: Purcari Nocturne):")
        if st.button("Adaugă") and new_w:
            wines.append(new_w); save_data(WINES_FILE, wines); st.rerun()
        
        st.divider()
        sel_wine = st.selectbox("Alege vinul:", wines)
        if st.button("Șterge Vin"):
            wines.remove(sel_wine); save_data(WINES_FILE, wines); st.rerun()

    if st.button(f"🔍 Începe Căutarea Națională pentru: {sel_wine}"):
        scraper = cloudscraper.create_scraper()
        all_results = []
        
        progress = st.progress(0)
        status = st.empty()
        
        for i, site in enumerate(SITES):
            status.info(f"Se caută pe {site['store']}...")
            res = deep_search(site, sel_wine, scraper)
            all_results.extend(res)
            time.sleep(random.uniform(1.5, 2.5))
            progress.progress((i + 1) / len(SITES))
        
        status.empty()
        
        if all_results:
            df = pd.DataFrame(all_results)
            
            # --- AFIȘARE REZULTATE PE FORMATE ---
            for fmt in df["Format"].unique():
                st.subheader(f"📦 Format: {fmt}")
                fmt_df = df[df["Format"] == fmt].sort_values(["An", "Preț (RON)"])
                
                # Tabel curat cu denumirea găsită pe site
                st.dataframe(fmt_df[["An", "Vin Complet", "Magazin", "Preț (RON)"]], 
                             use_container_width=True, hide_index=True)
                
                # Butoane de cumpărare
                cols = st.columns(4)
                for idx, row in fmt_df.iterrows():
                    cols[idx % 4].link_button(f"🛒 {row['Magazin']} ({row['An']}): {row['Preț (RON)']} RON", row['Link'])
        else:
            st.error("Nu am găsit rezultate. Încearcă cu cuvinte cheie mai simple.")
