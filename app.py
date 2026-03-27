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
st.set_page_config(page_title="Wine Watcher V3-Rev", page_icon="🍷", layout="wide")

WINES_FILE = "wines_list.json"
HISTORY_FILE = "price_history.json"
PASSWORD = "CodulEsteVinul"

SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/index/?q={q}"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product"},
    {"store": "CrushWine", "search_url": "https://www.crushwineshop.ro/catalogsearch/result/?q={q}"},
    {"store": "Drinkz", "search_url": "https://drinkz.ro/catalogsearch/result/?q={q}"},
    {"store": "AlcoolScont", "search_url": "https://www.alcoolscont.ro/catalogsearch/result/?q={q}"},
    {"store": "eMAG", "search_url": "https://www.emag.ro/search/{q}"}
]

# --- 2. LOGICA DE EXTRACȚIE V3 (CEA CARE A FUNCȚIONAT) ---
def get_price_v3_logic(soup, url):
    text_pret = ""
    # Metoda specifică pe domenii care a dat rezultate
    if "vinimondo.ro" in url:
        meta = soup.find("meta", property="product:price:amount")
        text_pret = meta["content"] if meta else ""
    elif "king.ro" in url:
        tag = soup.find("span", {"data-price-type": "finalPrice"})
        text_pret = tag.text if tag else ""
    elif "crushwineshop.ro" in url:
        tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
        text_pret = tag.text if tag else ""
    
    # Fallback Universal V3
    if not text_pret:
        for sel in [".price-new", ".woocommerce-Price-amount", ".current-price", ".price"]:
            tag = soup.select_one(sel)
            if tag: 
                text_pret = tag.get_text()
                break

    if text_pret:
        clean = re.sub(r'[^\d.,]', '', text_pret).replace(',', '.')
        nums = re.findall(r"\d+\.\d+|\d+", clean)
        if nums:
            val = float(nums[0])
            if val > 5000 and "emag" not in url: val /= 100
            return round(val, 2)
    return None

# --- 3. ANALIZĂ DETALII (AN/FORMAT) ---
def get_wine_meta(text):
    year_match = re.search(r'\b(19|20)\d{2}\b', text)
    year = year_match.group(0) if year_match else "N/A"
    fmt = "0.75L"
    if any(x in text.lower() for x in ["1.5", "magnum"]): fmt = "1.5L"
    elif any(x in text.lower() for x in ["3l", "double"]): fmt = "3L"
    return year, fmt

# --- 4. CĂUTARE RAPIDĂ V3 ---
def fast_scan_v3(site, query, scraper):
    url = site["search_url"].format(q=query.replace(" ", "+"))
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
    try:
        res = scraper.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Căutăm primul container de produs relevant direct în pagina de search
        # (Evităm intrarea pe pagini individuale pentru a nu fi blocați)
        items = []
        # Căutăm link-uri care conțin cuvintele cheie
        for a in soup.find_all("a", href=True):
            title = a.get_text().strip()
            if len(title) > 10 and any(word.lower() in title.lower() for word in query.split()):
                price = get_price_v3_logic(soup, url) # Încearcă să ia prețul din contextul paginii
                if price:
                    year, fmt = get_wine_meta(title)
                    items.append({
                        "Magazin": site["store"],
                        "Vin Complet": title,
                        "An": year,
                        "Format": fmt,
                        "Preț (RON)": price,
                        "Link": a["href"] if a["href"].startswith("http") else url
                    })
                    break # Luăm doar prima potrivire per site pentru viteză/stabilitate
        return items
    except: return []

# --- 5. INTERFAȚĂ ---
if "auth" not in st.session_state:
    st.title("🔐 Wine Watcher V3")
    pwd = st.text_input("Parolă:", type="password")
    if st.button("Log In"):
        if pwd == PASSWORD: st.session_state["auth"] = True; st.rerun()
else:
    st.title("🍷 Scrutin Național: Mod Stabil V3")
    
    if not os.path.exists(WINES_FILE): json.dump(["Le Volte"], open(WINES_FILE, 'w'))
    wines = json.load(open(WINES_FILE, 'r'))
    
    with st.sidebar:
        new_w = st.text_input("Adaugă vin:")
        if st.button("Adaugă") and new_w:
            wines.append(new_w); json.dump(wines, open(WINES_FILE, 'w')); st.rerun()
        sel_wine = st.selectbox("Selectează:", wines)
        if st.button("Șterge"):
            wines.remove(sel_wine); json.dump(wines, open(WINES_FILE, 'w')); st.rerun()

    if st.button(f"🔍 Scanare Rapidă: {sel_wine}"):
        scraper = cloudscraper.create_scraper()
        results = []
        prog = st.progress(0)
        
        for i, site in enumerate(SITES):
            st.write(f"Verificăm {site['store']}...")
            found = fast_scan_v3(site, sel_wine, scraper)
            results.extend(found)
            prog.progress((i + 1) / len(SITES))
            time.sleep(1) # Pauză minimă de siguranță

        if results:
            df = pd.DataFrame(results)
            for fmt in df["Format"].unique():
                st.subheader(f"📦 Format: {fmt}")
                fmt_df = df[df["Format"] == fmt].sort_values("Preț (RON)")
                st.table(fmt_df[["An", "Vin Complet", "Magazin", "Preț (RON)"]])
                
                # Link-uri
                for _, row in fmt_df.iterrows():
                    st.link_button(f"🛒 {row['Magazin']} - {row['Preț (RON)']} RON", row['Link'])
        else:
            st.error("Niciun rezultat găsit. Site-urile pot fi protejate.")
