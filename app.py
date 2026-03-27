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
st.set_page_config(page_title="Wine Watcher V5", page_icon="🍷", layout="wide")

WINES_FILE = "wines_list.json"
HISTORY_FILE = "price_history.json"
PASSWORD = "CodulEsteVinul"

SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/index/?q={q}", "base": "https://king.ro"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product", "base": "https://www.finestore.ro"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product", "base": "https://vinimondo.ro"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product", "base": "https://www.winemag.ro"},
    {"store": "CrushWine", "search_url": "https://www.crushwineshop.ro/catalogsearch/result/?q={q}", "base": "https://www.crushwineshop.ro"},
    {"store": "Drinkz", "search_url": "https://drinkz.ro/catalogsearch/result/?q={q}", "base": "https://drinkz.ro"},
    {"store": "AlcoolScont", "search_url": "https://www.alcoolscont.ro/catalogsearch/result/?q={q}", "base": "https://www.alcoolscont.ro"}
]

# --- 2. LOGICĂ PARSARE (AN & FORMAT) ---
def parse_details(name):
    year_match = re.search(r'\b(19|20)\d{2}\b', name)
    year = year_match.group(0) if year_match else "N/A"
    
    fmt = "0.75L"
    name_low = name.lower()
    if "1.5" in name_low or "magnum" in name_low: fmt = "1.5L"
    elif "3l" in name_low or "double magnum" in name_low: fmt = "3L"
    elif "0.375" in name_low or "375" in name_low: fmt = "0.375L"
    elif "0.5" in name_low: fmt = "0.5L"
    
    return year, fmt

# --- 3. EXTRACTORUL ROBUST V3 (PENTRU PAGINA PRODUSULUI) ---
def extract_price_from_product_page(soup, url):
    text_pret = ""
    # Logica ta de succes
    if "king.ro" in url:
        tag = soup.find("span", {"data-price-type": "finalPrice"})
        text_pret = tag.text if tag else ""
    elif "vinimondo.ro" in url:
        meta = soup.find("meta", property="product:price:amount")
        text_pret = meta["content"] if meta else ""
    else:
        # Selectori universali pentru pagini de produs
        for sel in [".price-new", ".woocommerce-Price-amount bdi", ".product-price", ".current-price", ".price"]:
            tag = soup.select_one(sel)
            if tag: 
                text_pret = tag.get_text()
                break

    if text_pret:
        clean = re.sub(r'[^\d.,]', '', text_pret).replace(',', '.')
        nums = re.findall(r"\d+\.\d+|\d+", clean)
        if nums:
            val = float(nums[0])
            if val > 5000: val /= 100
            return round(val, 2)
    return None

# --- 4. DEEP SEARCH ENGINE ---
def deep_scan_site(site, query, scraper):
    search_url = site["search_url"].format(q=query.replace(" ", "+"))
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
    
    try:
        res = scraper.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Colectăm link-urile care par a fi produse
        potential_links = []
        for a in soup.find_all("a", href=True):
            link = a["href"] if a["href"].startswith("http") else site["base"] + a["href"]
            # Filtrăm link-urile inutile
            if any(x in link.lower() for x in ["cart", "checkout", "account", "contact", "wishlist", "catalogsearch"]): continue
            
            # Verificăm relevanța numelui în link sau în textul ancoră
            if any(word.lower() in a.get_text().lower() for word in query.split()):
                potential_links.append(link)
        
        # Luăm doar link-uri unice și limităm la top 4 pentru a nu fi blocați
        unique_links = list(dict.fromkeys(potential_links))[:4]
        
        results = []
        for p_url in unique_links:
            time.sleep(random.uniform(1, 2)) # Pauză între pagini
            p_res = scraper.get(p_url, headers=headers, timeout=10)
            p_soup = BeautifulSoup(p_res.content, "html.parser")
            
            # EXTRACȚIE NUME COMPLET (din H1)
            h1 = p_soup.find("h1")
            full_name = h1.get_text().strip() if h1 else "Produs fără nume"
            
            # EXTRACȚIE PREȚ
            price = extract_price_from_product_page(p_soup, p_url)
            
            if price and price > 10: # Validare minimă
                year, fmt = parse_details(full_name)
                results.append({
                    "Magazin": site["store"],
                    "Vin Complet": full_name,
                    "An": year,
                    "Format": fmt,
                    "Preț (RON)": price,
                    "Link": p_url
                })
        return results
    except: return []

# --- 5. INTERFAȚĂ ---
if "auth" not in st.session_state:
    st.title("🔐 Wine Watcher V5")
    pwd = st.text_input("Parolă:", type="password")
    if st.button("Intră"):
        if pwd == PASSWORD: st.session_state["auth"] = True; st.rerun()
else:
    st.title("🍷 Scrutin Național: Deep Dive Mode")
    
    if not os.path.exists(WINES_FILE): json.dump(["Le Volte dell'Ornellaia"], open(WINES_FILE, 'w'))
    wines = json.load(open(WINES_FILE, 'r'))
    
    with st.sidebar:
        st.header("⚙️ Setări")
        new_w = st.text_input("Cuvinte cheie vin:")
        if st.button("Adaugă") and new_w:
            wines.append(new_w); json.dump(wines, open(WINES_FILE, 'w')); st.rerun()
        
        st.divider()
        sel_wine = st.selectbox("Alege vinul:", wines)
        if st.button("🗑️ Șterge"):
            wines.remove(sel_wine); json.dump(wines, open(WINES_FILE, 'w')); st.rerun()

    if st.button(f"🚀 Scanează în profunzime pentru: {sel_wine}"):
        scraper = cloudscraper.create_scraper()
        all_data = []
        
        main_progress = st.progress(0)
        status = st.empty()
        
        for i, site in enumerate(SITES):
            status.info(f"🔎 Căutăm și intrăm pe paginile de pe {site['store']}...")
            site_results = deep_scan_site(site, sel_wine, scraper)
            all_data.extend(site_results)
            main_progress.progress((i + 1) / len(SITES))
        
        status.empty()
        
        if all_data:
            df = pd.DataFrame(all_data)
            
            # Grupare și afișare pe Formate
            for fmt in sorted(df["Format"].unique()):
                st.markdown(f"### 📦 Format: {fmt}")
                fmt_df = df[df["Format"] == fmt].sort_values(["An", "Preț (RON)"])
                
                # Afișăm tabelul cu denumirile COMPLETE de pe site-uri
                st.dataframe(fmt_df[["An", "Vin Complet", "Magazin", "Preț (RON)"]], 
                             use_container_width=True, hide_index=True)
                
                # Grid de butoane
                cols = st.columns(3)
                for idx, row in fmt_df.reset_index().iterrows():
                    cols[idx % 3].link_button(f"{row['Magazin']} ({row['An']}): {row['Preț (RON)']} RON", row['Link'], use_container_width=True)
        else:
            st.error("Nu am găsit nicio pagină de produs validă. Încearcă cu un nume mai simplu.")
