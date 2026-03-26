import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random
from duckduckgo_search import DDGS  # Trebuie adăugat în requirements.txt

st.set_page_config(page_title="Le Volte: Deep Search", page_icon="🍷")

# 1. LOGICA DE EXTRAGERE ULTRA-FLEXIBILĂ
def get_price_any_site(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=10)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Căutăm meta-tag-ul de preț (standardul de aur)
        meta = soup.find("meta", property="product:price:amount")
        if meta: return float(meta["content"].replace(',', '.'))

        # Dacă nu există meta, căutăm textul care conține "lei" sau "ron"
        page_text = soup.get_text()
        # Regex care caută un număr urmat de lei/ron (ex: 119,00 lei)
        match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', page_text, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', '.'))
            return val if val < 500 else val / 100 # Corecție pt format 12500
        return None
    except:
        return None

# 2. INTERFAȚĂ
st.title("🔍 Deep Search: LE VOLTE")
st.write("Căutăm pe tot internetul românesc site-uri care conțin cuvintele cheie.")

# Căutare după cuvinte cheie
keywords = "LE VOLTE pret ron site:.ro"

if st.button("🚀 Începe Căutarea Globală"):
    rezultate = []
    
    with st.status("Răscolim internetul...", expanded=True) as status:
        try:
            # Folosim DuckDuckGo pentru a evita blocajele Google
            with DDGS() as ddgs:
                search_results = [r for r in ddgs.text(keywords, max_results=20)]
            
            for r in search_results:
                link = r['href']
                # Filtrăm site-urile care nu sunt magazine (forumuri, știri, etc.)
                if any(x in link for x in ["facebook", "emag", "olx", "vivino", "stiri", "prahova"]): continue
                
                nume_site = link.split('/')[2].replace('www.', '')
                status.write(f"🔎 Verificăm prețul pe: **{nume_site}**")
                
                pret = get_price_any_site(link)
                # Filtru: Prețul trebuie să fie realist pentru Le Volte (ex: 95 - 250 RON)
                if pret and 95 < pret < 250:
                    rezultate.append({"Magazin": nume_site, "Preț (RON)": pret, "Link": link})
                
                time.sleep(random.uniform(1, 2)) # Pauză anti-blocaj
                
        except Exception as e:
            st.error(f"Eroare la căutare: {e}")

    if rezultate:
        df = pd.DataFrame(rezultate).drop_duplicates(subset=['Magazin']).sort_values('Preț (RON)')
        st.balloons()
        st.table(df[["Magazin", "Preț (RON)"]])
        for _, row in df.iterrows():
            st.link_button(f"🛒 Mergi la {row['Magazin']}", row['Link'])
    else:
        st.warning("Nu am găsit oferte noi prin căutare automată. Site-urile pot fi protejate.")

# 3. LISTA TA DE AUR (Site-uri găsite de mine separat)
st.write("---")
st.subheader("📍 Magazine confirmate (Link Direct)")
surse_extra = [
    {"Magazin": "Wine360", "URL": "https://wine360.ro/le-volte-dell-ornellaia-toscana-igt-rosso"},
    {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rosu-sec-le-volte-dell-ornellaia-0-75l"},
    {"Magazin": "On-Vins", "URL": "https://on-vins.ro/produs/le-volte-dellornellaia-toscana-igt/"},
    {"Magazin": "Despre Vin", "URL": "https://desprevin.ro/vinuri/le-volte-dell-ornellaia-2021-igp-toscana-rosso/"}
]

if st.button("📊 Verifică Magazinele Confirmate"):
    for s in surse_extra:
        p = get_price_any_site(s["URL"])
        if p:
            st.write(f"✅ **{s['Magazin']}**: {p} RON")
            st.link_button(f"Mergi la {s['Magazin']}", s['URL'])
