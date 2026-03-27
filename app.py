import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import json
import os
import random
from datetime import datetime

# Configurare pagină
st.set_page_config(page_title="Wine Watcher Pro RO", page_icon="🍷", layout="wide")

# Fișiere pentru persistența datelor
WINES_FILE = "wines_list.json"
HISTORY_FILE = "price_history.json"

# --- LISTA EXTINSĂ DE SITE-URI DIN ROMÂNIA ---
SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/?q={q}", "platform": "magento"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "Drinkz", "search_url": "https://drinkz.ro/catalogsearch/result/?q={q}", "platform": "magento"},
    {"store": "AlcoolScont", "search_url": "https://www.alcoolscont.ro/catalogsearch/result/?q={q}", "platform": "magento"},
    {"store": "WinePoint", "search_url": "https://www.winepoint.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "NobilWine", "search_url": "https://nobilwine.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "E-Bauturi", "search_url": "https://www.e-bauturi.ro/cauta?q={q}", "platform": "custom"}
]

# --- LOGICĂ DE CURĂȚARE ȘI EXTRACȚIE ---

def clean_price(text):
    if not text: return None
    # Eliminăm valută și spații, convertim virgula în punct
    s = re.sub(r'[^\d.,]', '', str(text)).strip().replace(',', '.')
    try:
        # Dacă avem multiple puncte (ex: 1.250.00), păstrăm doar structura de zecimală
        if s.count('.') > 1:
            parts = s.split('.')
            s = "".join(parts[:-1]) + "." + parts[-1]
        val = float(s)
        # Filtru de siguranță: un vin premium nu costă 10 RON, dar nici 50.000
        if 20 < val < 10000: return round(val, 2)
    except: return None
    return None

def get_price_from_page(soup, platform):
    """
    Strategie de extracție: Prioritizăm prețul final afișat (cel cu TVA).
    """
    # 1. Specific pentru King.ro și alte platforme Magento (Preț FINAL cu TVA)
    if platform == "magento":
        tag = soup.select_one('span[data-price-type="finalPrice"] .price')
        if tag:
            p = clean_price(tag.get_text())
            if p: return p

    # 2. Selectori standard WooCommerce
    for sel in [".woocommerce-Price-amount bdi", ".price-new", ".current-price", ".product-price"]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.get_text())
            if p: return p

    # 3. Fallback pe Meta Tags (Atenție: aici poate apărea prețul fără TVA la unele site-uri)
    meta = soup.find("meta", property="product:price:amount")
    if meta:
        p = clean_price(meta.get("content"))
        if p: return p
        
    return None

def name_score(text, wine_name):
    stop_words = {"le", "la", "di", "del", "dell", "de", "the", "vin", "rosu", "alb", "0.75l", "075l"}
    words = [w for w in wine_name.lower().split() if w not in stop_words and len(w) > 2]
    text_l = text.lower()
    return sum(1 for w in words if w in text_l)

def search_wine(site, wine_name, scraper):
    query = wine_name.replace(" ", "+")
    url = site["search_url"].format(q=query)
    try:
        # Simulare comportament uman
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        res = scraper.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None, None, f"Eroare {res.status_code}"
        
        soup = BeautifulSoup(res.content, "html.parser")
        domain = "/".join(url.split("/")[:3])
        
        # Căutăm cel mai relevant link de produs
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"): href = domain + href
            if any(x in href.lower() for x in ["cart", "wishlist", "contact", "account"]): continue
            
            score = name_score(a.get_text() + " " + href, wine_name)
            if score >= 1:
                links.append((score, href))
        
        if not links: return None, None, "Nu am găsit produsul"
        
        # Mergem pe cel mai bun link
        links.sort(key=lambda x: x[0], reverse=True)
        best_url = links[0][1]
        
        res_prod = scraper.get(best_url, headers=headers, timeout=15)
        soup_prod = BeautifulSoup(res_prod.content, "html.parser")
        price = get_price_from_page(soup_prod, site["platform"])
        
        return price, best_url, None
    except Exception as e:
        return None, None, str(e)[:50]

# --- PERSISTENȚĂ ---

def load_data(file, default):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

# --- INTERFAȚĂ ---

st.title("🍷 Scrutin Național: Vinuri în România")
wines = load_data(WINES_FILE, ["Le Volte dell'Ornellaia", "Rosa dei Frati"])

with st.sidebar:
    st.header("⚙️ Administrare")
    new_wine = st.text_input("Adaugă vin nou:")
    if st.button("Adaugă în listă") and new_wine:
        if new_wine not in wines:
            wines.append(new_wine)
            save_data(WINES_FILE, wines)
            st.rerun()
    
    st.divider()
    if st.button("Șterge vinul selectat"):
        # Logică de ștergere dacă e nevoie
        pass

selected_wine = st.selectbox("Alege vinul pentru scanare:", wines)

if st.button(f"🚀 Scanează toată piața pentru {selected_wine}"):
    scraper = cloudscraper.create_scraper()
    results, errors = [], []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, site in enumerate(SITES):
        status_text.text(f"Se verifică {site['store']}...")
        price, url, err = search_wine(site, selected_wine, scraper)
        
        if price:
            results.append({"Magazin": site['store'], "Preț (RON)": price, "Link": url})
        else:
            errors.append({"Magazin": site['store'], "Motiv": err})
        
        # Pauză random între 1 și 3 secunde pentru a evita banarea IP-ului
        time.sleep(random.uniform(1, 3))
        progress_bar.progress((i + 1) / len(SITES))
    
    status_text.empty()
    
    if results:
        df = pd.DataFrame(results).sort_values("Preț (RON)")
        st.success(f"Găsit pe {len(results)} site-uri!")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        # Butoane directe de cumpărare
        cols = st.columns(3)
        for idx, row in df.iterrows():
            cols[idx % 3].link_button(f"🛒 {row['Magazin']}: {row['Preț (RON)']} RON", row['Link'], use_container_width=True)
    else:
        st.error("Nu am găsit oferte valide. Site-urile pot fi protejate sau vinul nu e pe stoc.")

    if errors:
        with st.expander("Vezi site-urile care nu au răspuns"):
            for e in errors: st.write(f"❌ {e['Magazin']}: {e['Motiv']}")
