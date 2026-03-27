import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import json
import os
import random

# --- 1. CONFIGURARE ---
st.set_page_config(page_title="Wine Watcher V6", page_icon="🍷", layout="wide")
PASSWORD = "CodulEsteVinul"

SITES = [
    {"store": "King.ro", "search_url": "https://king.ro/catalogsearch/result/?q={q}"},
    {"store": "FineStore", "search_url": "https://www.finestore.ro/?s={q}&post_type=product"},
    {"store": "Vinimondo", "search_url": "https://vinimondo.ro/?s={q}&post_type=product"},
    {"store": "WineMag", "search_url": "https://www.winemag.ro/?s={q}&post_type=product"},
    {"store": "Drinkz", "search_url": "https://drinkz.ro/catalogsearch/result/?q={q}"},
    {"store": "eMAG", "search_url": "https://www.emag.ro/search/{q}"}
]

# --- 2. MOTOR DE CĂUTARE AGRESIV (HUMAN LIKE) ---
def find_prices_in_raw_text(soup, query):
    """Căutăm prețuri oriunde în pagină, ignorând structura HTML fixă"""
    results = []
    # Curățăm query-ul pentru a căuta bucăți din el
    keywords = query.lower().split()
    
    # Căutăm toate elementele care ar putea conține un produs
    containers = soup.find_all(['div', 'li', 'article', 'tr'])
    
    for container in containers:
        text = container.get_text(separator=' ', strip=True)
        # Verificăm dacă măcar 2 cuvinte din vin sunt în acest bloc de text
        matches = sum(1 for word in keywords if word in text.lower())
        
        if matches >= 1:
            # Căutăm tiparul de preț: cifre urmate de lei/ron sau invers
            price_match = re.search(r'(\d{2,4}(?:[.,]\d{2})?)\s?(?:lei|RON)', text, re.IGNORECASE)
            if price_match:
                try:
                    raw_p = price_match.group(1).replace(',', '.')
                    val = float(re.sub(r'[^\d.]', '', raw_p))
                    
                    # Identificăm un titlu plauzibil în acel container (primul link sau text lung)
                    link_tag = container.find('a', href=True)
                    name = link_tag.get_text().strip() if link_tag else "Produs identificat"
                    if len(name) < 5: name = text[:50] + "..."
                    
                    if 30 < val < 15000: # Filtru de siguranță
                        results.append({
                            "Vin": name,
                            "Preț": round(val, 2),
                            "Link": link_tag['href'] if link_tag else "#"
                        })
                except: continue
    
    # Sortăm după preț și luăm cel mai ieftin (unic)
    if results:
        unique = sorted(results, key=lambda x: x['Preț'])
        return unique[0]
    return None

# --- 3. LOGICA PRINCIPALĂ ---
if "auth" not in st.session_state:
    st.title("🔐 Acces Crama")
    pwd = st.text_input("Parola:", type="password")
    if st.button("Intră"):
        if pwd == PASSWORD: st.session_state["auth"] = True; st.rerun()
else:
    st.title("🍷 Scrutin V6: Detectare prin Amprentă Textuală")
    
    q = st.text_input("Ce vin cauți exact (ex: Rosa dei Frati):", "Rosa dei Frati")

    if st.button(f"🚀 Scanează toată piața pentru {q}"):
        # Folosim un browser mai nou în configurarea scraper-ului
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        
        final_list = []
        bar = st.progress(0)
        
        for i, site in enumerate(SITES):
            st.write(f"🔎 Verificăm {site['store']}...")
            try:
                # Simulăm un user real care așteaptă puțin
                time.sleep(random.uniform(1, 3))
                url = site["search_url"].format(q=q.replace(" ", "+"))
                res = scraper.get(url, timeout=15)
                
                if res.status_code == 200:
                    soup = BeautifulSoup(res.content, "html.parser")
                    found = find_prices_in_raw_text(soup, q)
                    if found:
                        final_list.append({
                            "Magazin": site["store"],
                            "Denumire": found["Vin"],
                            "Preț (RON)": found["Preț"],
                            "Link": found["Link"] if found["Link"].startswith("http") else url
                        })
                else:
                    st.warning(f"⚠️ {site['store']} a returnat eroarea {res.status_code}")
            except Exception as e:
                st.error(f"❌ {site['store']} blocat.")
            
            bar.progress((i + 1) / len(SITES))

        if final_list:
            df = pd.DataFrame(final_list).sort_values("Preț (RON)")
            st.success("Am găsit următoarele oferte!")
            st.table(df[["Magazin", "Preț (RON)", "Denumire"]])
            
            for _, row in df.iterrows():
                st.link_button(f"🛒 Cumpără de la {row['Magazin']} - {row['Preț (RON)']} RON", row['Link'])
        else:
            st.error("Niciun rezultat. Site-urile au blocat cererea automată.")
