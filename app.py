import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random
from googlesearch import search

# 1. CONFIGURARE
st.set_page_config(page_title="Wine Watcher Universal", page_icon="🍷")

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
]

# MOTORUL DE EXTRAGERE
def get_price_stealth(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    
    try:
        res = scraper.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return None, f"Refuzat (Cod {res.status_code})"
        
        soup = BeautifulSoup(res.content, "html.parser")
        
        # 1. Meta tag (metoda principală)
        meta = soup.find("meta", property="product:price:amount")
        if meta: return float(meta["content"].replace(',', '.')), "Succes"
        
        # 2. King.ro
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.'))), "Succes"

        # 3. Universal (Regex)
        text = soup.get_text()
        match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', text, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', '.'))
            return (val if val < 1000 else val / 100), "Succes"
            
        return None, "Structură necunoscută"
    except Exception as e:
        return None, "Eroare de conexiune"

# 2. INTERFAȚĂ
st.title("🍷 Wine Watcher: Scrutin Național")
st.write("Acum poți urmări în timp real ce magazine sunt analizate.")

# Am scos "L"-ul din default pentru o căutare și mai flexibilă
produs = st.text_input("Denumire Vin:", "Le Volte dell'Ornellaia 0.75")

if st.button("🚀 Scanează România"):
    rezultate = []
    erori = []
    
    # CHEIA: Fără ghilimele exacte. Permitem Google să fie inteligent.
    query = f'{produs} pret romania site:.ro'
    
    with st.status("Inițializare scanare...", expanded=True) as status:
        status.write(f"🔍 Căutăm pe Google după: `{query}`")
        
        try:
            # Folosim un format compatibil cu orice versiune de googlesearch
            rezultate_google = search(query, lang="ro")
            linkuri = []
            for i, l in enumerate(rezultate_google):
                if i >= 12: break # Ne oprim la 12 rezultate pentru a evita blocajele
                linkuri.append(l)
        except Exception as e:
            status.update(label="Eroare: Google ne-a blocat temporar accesul.", state="error")
            st.stop()

        if not linkuri:
            status.update(label="Google nu a găsit nicio pagină relevantă.", state="error")
            st.stop()
            
        status.write(f"✅ Am extras **{len(linkuri)}** magazine potențiale. Începem analiza...")
        status.divider()
        
        for link in linkuri:
            if any(x in link for x in ["facebook", "emag", "okazii", "olx", "vivino", "compari", "stiri"]):
                continue
                
            magazin = link.split('/')[2].replace('www.', '')
            status.write(f"⏳ Analizăm: **{magazin}** ...")
            
            pret, msg = get_price_stealth(link)
            
            if pret:
                if 80 < pret < 350:
                    rezultate.append({"Magazin": magazin, "Preț (RON)": pret, "Link": link})
                    status.write(f"👉 **Găsit: {pret} RON**")
                else:
                    erori.append(f"{magazin}: Preț atipic ({pret} RON)")
                    status.write(f"👉 Ignorat: {pret} RON (probabil alt volum)")
            else:
                erori.append(f"{magazin}: {msg}")
                status.write(f"👉 Eșuat: {msg}")
            
            time.sleep(1.5) # Ritm susținut dar uman
            
        status.update(label="Scanare finalizată!", state="complete")

    if rezultate:
        df = pd.DataFrame(rezultate).drop_duplicates(subset=['Magazin']).sort_values('Preț (RON)')
        st.balloons()
        st.subheader("📊 Clasament oferte:")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        for _, row in df.iterrows():
            st.link_button(f"🛒 Cumpără de la {row['Magazin']} ({row['Preț (RON)']} RON)", row['Link'])
            
    if erori:
        with st.expander("🛠️ Vezi detaliile tehnice ale magazinelor ratate"):
            for e in erori:
                st.write(f"- {e}")
