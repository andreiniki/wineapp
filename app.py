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

# --- 1. CONFIGURARE & PERSISTENȚĂ ---
st.set_page_config(page_title="Wine Watcher Pro", page_icon="🍷", layout="wide")

WINES_FILE = "wines_list.json"
HISTORY_FILE = "price_history.json"
PASSWORD = "CodulEsteVinul"

def load_data(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: 
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- 2. MOTORUL DE EXTRACȚIE DIN V3 (ULTRA ROBUST) ---
def extract_price_v3(soup, url):
    text_pret = ""
    
    # Strategie specifică pe domenii (preluată din V3)
    if "vinimondo.ro" in url:
        meta = soup.find("meta", property="product:price:amount")
        text_pret = meta["content"] if meta else ""
    
    elif "king.ro" in url:
        tag = soup.find("span", {"data-price-type": "finalPrice"})
        text_pret = tag.text if tag else ""

    elif "crushwineshop.ro" in url:
        tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
        text_pret = tag.text if tag else ""

    elif "winemag.ro" in url:
        tag = soup.find("span", class_="price-new")
        text_pret = tag.text if tag else ""

    # Fallback: Căutare Regex (din V3)
    if not text_pret:
        page_text = soup.get_text()
        match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', page_text, re.IGNORECASE)
        if match:
            text_pret = match.group(1)

    if text_pret:
        # Curățare (din V3)
        clean_digits = text_pret.replace(',', '.').replace(' ', '')
        numere = re.findall(r"[-+]?\d*\.\d+|\d+", clean_digits)
        if numere:
            valoare = float(numere[0])
            if valoare > 3000: valoare = valoare / 100 # Corecție formatări
            if 25 < valoare < 20000: return round(valoare, 2)
    
    return None

# --- 3. LOGICĂ DE CĂUTARE PE INTERNET ---
SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/index/?q={q}"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product"},
    {"store": "CrushWine", "search_url": "https://www.crushwineshop.ro/catalogsearch/result/?q={q}"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product"},
    {"store": "WinePoint", "search_url": "https://www.winepoint.ro/?s={q}&post_type=product"}
]

def search_and_extract(site, wine_name, scraper):
    clean_query = re.sub(r'[^\w\s]', '', wine_name).replace("075L", "").replace("075", "").strip()
    url = site["search_url"].format(q=clean_query.replace(" ", "+"))
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
        res = scraper.get(url, headers=headers, timeout=20)
        if res.status_code != 200: return None, None, f"HTTP {res.status_code}"
        
        soup = BeautifulSoup(res.content, "html.parser")
        domain = "/".join(url.split("/")[:3])
        
        # Verificăm dacă suntem deja pe pagina produsului
        direct_price = extract_price_v3(soup, url)
        if direct_price: return direct_price, url, None

        # Căutăm link-uri de produse
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"): href = domain + href
            if any(x in href.lower() for x in ["cart", "account", "checkout", "contact"]): continue
            
            score = sum(1 for word in clean_query.lower().split() if word in a.get_text().lower())
            if score >= 1: links.append((score, href))
        
        if not links: return None, None, "Negăsit"
        
        links.sort(key=lambda x: x[0], reverse=True)
        prod_url = links[0][1]
        
        res_p = scraper.get(prod_url, headers=headers, timeout=20)
        soup_p = BeautifulSoup(res_p.content, "html.parser")
        price = extract_price_v3(soup_p, prod_url)
        
        return price, prod_url, None
    except Exception as e:
        return None, None, str(e)[:30]

# --- 4. INTERFAȚĂ ---
if "auth" not in st.session_state:
    st.title("🔐 Acces Privat")
    pwd = st.text_input("Introdu parola:", type="password")
    if st.button("Intră"):
        if pwd == PASSWORD:
            st.session_state["auth"] = True
            st.rerun()
        else: st.error("Incorect!")
else:
    st.title("🍷 Wine Watcher: Monitorizare Națională")
    
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
        if st.button(f"🚀 Scanează România pentru: {selected_wine}"):
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
            results = []
            
            progress = st.progress(0)
            status = st.empty()
            
            for idx, site in enumerate(SITES):
                status.info(f"Se verifică {site['store']}...")
                price, url, err = search_and_extract(site, selected_wine, scraper)
                
                if price:
                    results.append({"Magazin": site['store'], "Preț (RON)": price, "Link": url})
                
                time.sleep(random.uniform(2, 3)) 
                progress.progress((idx + 1) / len(SITES))
            
            status.empty()
            
            if results:
                df = pd.DataFrame(results).sort_values("Preț (RON)")
                st.success(f"Analiză completă!")
                st.dataframe(df[["Magazin", "Preț (RON)"]], use_container_width=True, hide_index=True)
                
                # Update Istoric
                today = datetime.now().strftime("%Y-%m-%d")
                if selected_wine not in history: history[selected_wine] = []
                history[selected_wine].append({"data": today, "pret": df["Preț (RON)"].min()})
                save_data(HISTORY_FILE, history)
                
                for res in results:
                    st.link_button(f"🛒 {res['Magazin']}: {res['Preț (RON)']} RON", res['Link'])
            else:
                st.error("Nicio ofertă găsită. Site-urile pot fi protejate.")

    with col2:
        st.subheader("📈 Evoluție Preț")
        if selected_wine in history and len(history[selected_wine]) > 0:
            h_df = pd.DataFrame(history[selected_wine])
            fig = px.line(h_df, x="data", y="pret", markers=True, title=f"Trend: {selected_wine}")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Efectuează o scanare pentru istoric.")
