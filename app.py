import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random
from googlesearch import search

# 1. CONFIGURARE
st.set_page_config(page_title="Wine Watcher Pro", page_icon="🍷")

# Listă de User-Agents pentru a evita detectarea ca robot
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
]

def get_price_stealth(url):
    # Folosim un User-Agent random la fiecare cerere
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    
    try:
        res = scraper.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, "html.parser")
        
        # 1. Încercăm Meta Tags (cele mai rezistente la schimbări de design)
        meta = soup.find("meta", property="product:price:amount")
        if meta: return float(meta["content"].replace(',', '.'))
        
        # 2. Logica pentru King.ro (Selectorul tău calibrat)
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.')))

        # 3. Căutare brută în text (Regex) - ultima șansă
        text = soup.get_text()
        match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', text, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', '.'))
            return val if val < 1000 else val / 100
            
        return None
    except:
        return None

# 2. INTERFAȚĂ
st.title("🍷 Wine Watcher: Scrutin Național")
produs = st.text_input("Denumire Vin:", "Le Volte dell'Ornellaia 0.75L")

if st.button("🚀 Scanează România"):
    rezultate = []
    
    with st.status("Căutăm oferte active...", expanded=True) as status:
        # Căutare Google cu interval de siguranță mărit
        query = f'"{produs}" pret site:.ro -inurl:forum'
        
        try:
            # sleep_interval mare pentru a nu fi blocați de Google
            search_results = search(query, sleep_interval=5, num_results=10)
            
            for link in search_results:
                if any(x in link for x in ["facebook", "emag", "okazii", "olx"]): continue
                
                magazin = link.split('/')[2].replace('www.', '')
                status.write(f"Verificăm magazinul: **{magazin}**...")
                
                pret = get_price_stealth(link)
                if pret and 90 < pret < 300:
                    rezultate.append({"Magazin": magazin, "Preț (RON)": pret, "Link": link})
                
                # Pauză random între magazine pentru a părea comportament uman
                time.sleep(random.uniform(2, 4))
                
        except Exception as e:
            st.error("Google a detectat prea multe cereri. Așteaptă 10 minute.")

    if rezultate:
        df = pd.DataFrame(rezultate).drop_duplicates(subset=['Magazin']).sort_values('Preț (RON)')
        st.balloons()
        st.table(df[["Magazin", "Preț (RON)"]])
        for _, row in df.iterrows():
            st.link_button(f"🛒 Cumpără de la {row['Magazin']}", row['Link'])
    else:
        st.warning("Nu am găsit prețuri. Încearcă să fii mai specific în căutare.")
