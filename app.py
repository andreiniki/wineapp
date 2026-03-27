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

# --- CONFIGURARE ---
st.set_page_config(page_title="Wine Watcher Pro", page_icon="🍷", layout="wide")

WINES_FILE = "wines_list.json"
HISTORY_FILE = "price_history.json"

# Listă extinsă de magazine (fără Google, căutare directă)
SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/?q={q}", "platform": "magento"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "Drinkz", "search_url": "https://drinkz.ro/catalogsearch/result/?q={q}", "platform": "magento"},
    {"store": "AlcoolScont", "search_url": "https://www.alcoolscont.ro/catalogsearch/result/?q={q}", "platform": "magento"},
    {"store": "WinePoint", "search_url": "https://www.winepoint.ro/?s={q}&post_type=product", "platform": "woo"}
]

# --- FUNCȚII SUPORT ---

def load_data(file, default):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

def clean_price(text):
    if not text: return None
    # Extrage doar cifrele și virgula/punctul
    s = re.sub(r'[^\d.,]', '', str(text)).strip().replace(',', '.')
    try:
        if s.count('.') > 1:
            parts = s.split('.')
            s = "".join(parts[:-1]) + "." + parts[-1]
        val = float(s)
        if 20 < val < 15000: return round(val, 2)
    except: return None
    return None

def get_price_from_page(soup, platform):
    # Prioritate 1: Prețul Final (cu TVA) pentru Magento/King.ro
    if platform == "magento":
        tag = soup.select_one('span[data-price-type="finalPrice"] .price')
        if tag:
            p = clean_price(tag.get_text())
            if p: return p

    # Prioritate 2: WooCommerce standard
    for sel in [".woocommerce-Price-amount bdi", ".price-new", ".current-price"]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.get_text())
            if p: return p
    return None

def search_wine(site, wine_name, scraper):
    # Curățăm numele pentru căutare (scoatem 0.75L care poate încurca căutarea internă)
    clean_query = wine_name.replace("0.75L", "").replace("0.75", "").strip()
    url = site["search_url"].format(q=clean_query.replace(" ", "+"))
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
        res = scraper.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None, None, f"Eroare {res.status_code}"
        
        soup = BeautifulSoup(res.content, "html.parser")
        domain = "/".join(url.split("/")[:3])
        
        # Căutăm linkul de produs
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"): href = domain + href
            if any(x in href.lower() for x in ["cart", "wishlist", "account", "contact"]): continue
            
            # Scor de relevanță simplu
            score = sum(1 for word in clean_query.lower().split() if word in a.get_text().lower())
            if score >= 1: links.append((score, href))
        
        if not links: return None, None, "Produs negăsit"
        
        # Mergem pe cel mai relevant link
        links.sort(key=lambda x: x[0], reverse=True)
        prod_url = links[0][1]
        
        res_p = scraper.get(prod_url, headers=headers, timeout=15)
        soup_p = BeautifulSoup(res_p.content, "html.parser")
        price = get_price_from_page(soup_p, site["platform"])
        
        return price, prod_url, None
    except Exception as e:
        return None, None, str(e)[:30]

# --- UI STREAMLIT ---

st.title("🍷 Wine Watcher: Monitorizare Stabilă")
st.markdown("Fără Google, fără blocaje. Căutare directă în sursele magazinelor.")

wines = load_data(WINES_FILE, ["Le Volte dell'Ornellaia", "Rosa dei Frati"])
history = load_data(HISTORY_FILE, {})

with st.sidebar:
    st.header("⚙️ Administrare")
    new_wine = st.text_input("Nume vin nou:")
    if st.button("Adaugă în listă"):
        if new_wine and new_wine not in wines:
            wines.append(new_wine)
            save_data(WINES_FILE, wines)
            st.rerun()
    
    st.divider()
    selected_wine = st.selectbox("Alege vinul de verificat:", wines)

col1, col2 = st.columns([2, 1])

with col1:
    if st.button(f"🔍 Scanează prețuri pentru: {selected_wine}"):
        scraper = cloudscraper.create_scraper()
        results = []
        
        progress = st.progress(0)
        status = st.empty()
        
        for idx, site in enumerate(SITES):
            status.text(f"Se verifică {site['store']}...")
            price, url, err = search_wine(site, selected_wine, scraper)
            
            if price:
                results.append({"Magazin": site['store'], "Preț (RON)": price, "Link": url})
            
            time.sleep(random.uniform(1.5, 3.0)) # Pauză anti-bot
            progress.progress((idx + 1) / len(SITES))
        
        status.empty()
        
        if results:
            df = pd.DataFrame(results).sort_values("Preț (RON)")
            st.success(f"Analiză finalizată!")
            st.table(df[["Magazin", "Preț (RON)"]])
            
            # Salvare în istoric
            today = datetime.now().strftime("%Y-%m-%d")
            if selected_wine not in history: history[selected_wine] = []
            
            min_price = df["Preț (RON)"].min()
            history[selected_wine].append({"data": today, "pret": min_price})
            save_data(HISTORY_FILE, history)
            
            for res in results:
                st.link_button(f"🛒 {res['Magazin']}: {res['Preț (RON)']} RON", res['Link'])
        else:
            st.warning("Nu s-au găsit oferte. Încearcă să simplifici numele vinului.")

with col2:
    st.subheader("📈 Evoluție Preț")
    if selected_wine in history and len(history[selected_wine]) > 0:
        h_df = pd.DataFrame(history[selected_wine])
        fig = px.line(h_df, x="data", y="pret", title="Cel mai mic preț găsit")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Efectuează o scanare pentru a genera istoricul.")
