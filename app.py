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

# --- CONFIGURARE ȘI PERSISTENȚĂ ---
st.set_page_config(page_title="Wine Watcher Pro", page_icon="🍷", layout="wide")

WINES_FILE = "wines_list.json"
HISTORY_FILE = "price_history.json"

def load_data(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: 
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- SITE-URI ACTUALIZATE (Selectori și URL-uri noi) ---
SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/index/?q={q}", "platform": "magento"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "Drinkz", "search_url": "https://drinkz.ro/catalogsearch/result/?q={q}", "platform": "magento"},
    {"store": "WinePoint", "search_url": "https://www.winepoint.ro/?s={q}&post_type=product", "platform": "woo"},
    {"store": "E-Bauturi", "search_url": "https://www.e-bauturi.ro/cauta?q={q}", "platform": "custom"}
]

# --- LOGICĂ EXTRACȚIE ---
def clean_price(text):
    if not text: return None
    s = re.sub(r'[^\d.,]', '', str(text)).strip().replace(',', '.')
    try:
        if s.count('.') > 1:
            parts = s.split('.')
            s = "".join(parts[:-1]) + "." + parts[-1]
        val = float(s)
        if 25 < val < 20000: return round(val, 2)
    except: return None
    return None

def get_price_from_page(soup, platform):
    # Fix pentru prețul cu TVA pe King.ro/Magento
    if platform == "magento":
        tag = soup.select_one('span[data-price-type="finalPrice"] .price')
        if tag:
            p = clean_price(tag.get_text())
            if p: return p
    # WooCommerce & Altele
    for sel in [".woocommerce-Price-amount bdi", ".price-new", ".current-price", ".product-price"]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.get_text())
            if p: return p
    return None

def search_wine(site, wine_name, scraper):
    # Eliminăm caractere care pot "strica" căutarea internă a site-urilor
    clean_query = re.sub(r'[^\w\s]', '', wine_name).replace("075L", "").replace("075", "").strip()
    url = site["search_url"].format(q=clean_query.replace(" ", "+"))
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        res = scraper.get(url, headers=headers, timeout=20)
        if res.status_code != 200: return None, None, f"HTTP {res.status_code}"
        
        soup = BeautifulSoup(res.content, "html.parser")
        domain = "/".join(url.split("/")[:3])
        
        # Dacă site-ul ne-a trimis direct pe pagina produsului
        if get_price_from_page(soup, site["platform"]):
            return get_price_from_page(soup, site["platform"]), res.url, None

        # Altfel, căutăm link-uri relevante în rezultate
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"): href = domain + href
            if any(x in href.lower() for x in ["cart", "wishlist", "account", "checkout"]): continue
            
            score = sum(1 for word in clean_query.lower().split() if word in a.get_text().lower())
            if score >= 1: links.append((score, href))
        
        if not links: return None, None, "Negăsit"
        
        links.sort(key=lambda x: x[0], reverse=True)
        prod_url = links[0][1]
        
        res_p = scraper.get(prod_url, headers=headers, timeout=20)
        soup_p = BeautifulSoup(res_p.content, "html.parser")
        return get_price_from_page(soup_p, site["platform"]), prod_url, None
    except Exception as e:
        return None, None, str(e)[:30]

# --- UI STREAMLIT ---
st.title("🍷 Scrutin Național: Monitorizare Vinuri")

wines = load_data(WINES_FILE, ["Le Volte dell'Ornellaia", "Rosa dei Frati"])
history = load_data(HISTORY_FILE, {})

with st.sidebar:
    st.header("⚙️ Administrare")
    new_wine = st.text_input("Adaugă vin (ex: Tignanello):")
    if st.button("➕ Adaugă"):
        if new_wine and new_wine not in wines:
            wines.append(new_wine)
            save_data(WINES_FILE, wines)
            st.rerun()
    
    st.divider()
    selected_wine = st.selectbox("Vinul de monitorizat:", wines)
    if st.button("🗑️ Șterge vin"):
        wines.remove(selected_wine)
        save_data(WINES_FILE, wines)
        st.rerun()

col1, col2 = st.columns([2, 1])

with col1:
    if st.button(f"🚀 Scanează România pentru {selected_wine}"):
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        results = []
        
        progress = st.progress(0)
        status = st.empty()
        
        for idx, site in enumerate(SITES):
            status.info(f"Se caută pe {site['store']}...")
            price, url, err = search_wine(site, selected_wine, scraper)
            
            if price:
                results.append({"Magazin": site['store'], "Preț (RON)": price, "Link": url})
            
            time.sleep(random.uniform(2, 4)) # Pauză umană necesară
            progress.progress((idx + 1) / len(SITES))
        
        status.empty()
        
        if results:
            df = pd.DataFrame(results).sort_values("Preț (RON)")
            st.success(f"Analiză completă!")
            st.dataframe(df[["Magazin", "Preț (RON)"]], use_container_width=True, hide_index=True)
            
            # Actualizare Istoric
            today = datetime.now().strftime("%Y-%m-%d")
            if selected_wine not in history: history[selected_wine] = []
            history[selected_wine].append({"data": today, "pret": df["Preț (RON)"].min()})
            save_data(HISTORY_FILE, history)
            
            st.subheader("🛒 Link-uri directe:")
            cols = st.columns(3)
            for i, res in enumerate(results):
                cols[i % 3].link_button(f"{res['Magazin']}: {res['Preț (RON)']} RON", res['Link'], use_container_width=True)
        else:
            st.error("Nicio ofertă găsită. Site-urile te pot bloca temporar (403).")

with col2:
    st.subheader("📈 Evoluție Preț")
    # FIX PENTRU VALUEERROR: Verificăm dacă există date valide înainte de plot
    if selected_wine in history and len(history[selected_wine]) > 0:
        h_df = pd.DataFrame(history[selected_wine])
        if not h_df.empty and "data" in h_df.columns and "pret" in h_df.columns:
            fig = px.line(h_df, x="data", y="pret", markers=True, 
                         title=f"Trend: {selected_wine}",
                         labels={"data": "Data", "pret": "Preț Minim (RON)"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Datele din istoric sunt incomplete.")
    else:
        st.info("Scanările viitoare vor apărea aici.")
    
    if st.button("🧹 Șterge Istoric"):
        history[selected_wine] = []
        save_data(HISTORY_FILE, history)
        st.rerun()
