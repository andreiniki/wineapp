import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Wine Watcher Pro", page_icon="🍷")

def clean_price(text):
    if not text: return None
    # Eliminăm tot ce nu e cifră, punct sau virgulă
    text = text.lower().replace('lei', '').replace('ron', '').strip()
    text = text.replace(',', '.')
    # Extragem primul grup de cifre care seamănă a preț (ex: 85.00)
    match = re.search(r"(\d+\.\d+|\d+)", text)
    if match:
        val = float(match.group(1))
        if val > 1000: val /= 100 # Corecție format 8500 -> 85.00
        return round(val, 2)
    return None

def get_wine_price(url, min_p, max_p):
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, "html.parser")
        
        # --- STRATEGIA 1: Meta Tags (Standard) ---
        meta = soup.find("meta", property="product:price:amount")
        if meta:
            p = clean_price(meta["content"])
            if p and min_p < p < max_p: return p

        # --- STRATEGIA 2: Selectori Specifici (Vinimondo & King) ---
        # Vinimondo folosește deseori clasa 'price' în interiorul 'price-box'
        if "vinimondo.ro" in url:
            tags = soup.select(".price-wrapper .price, .price-box .price, .special-price .price")
            for t in tags:
                p = clean_price(t.text)
                if p and min_p < p < max_p: return p

        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return clean_price(tag.text)

        # --- STRATEGIA 3: Scanare Globală (Metoda "Detectiv") ---
        # Căutăm orice element care conține textul "lei" sau "ron"
        text_elements = soup.find_all(text=re.compile(r'lei|ron', re.I))
        for el in text_elements:
            # Ne uităm la părintele elementului pentru a lua tot prețul (ex: 85,00 lei)
            p = clean_price(el.parent.get_text())
            if p and min_p < p < max_p:
                return p
                
        return None
    except:
        return None

# --- BAZA DE DATE ACTUALIZATĂ ---
BAZA_DATE_VINURI = {
    "Rosa dei Frati (Ca' dei Frati)": {
        "min_price": 65,
        "max_price": 130,
        "surse": [
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/ca-dei-frati-rosa-dei-frati-riviera-del-garda-classico-doc-ca-dei-frati-ro"},
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ca-dei-frati-rosa-dei-frati-075l"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ca-dei-frati-rosa-dei-frati-0.750-l.html"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/ca-dei-frati-rosa-dei-frati-0-75l"},
            {"Magazin": "Alcool Scont", "URL": "https://www.alcoolscont.ro/vinuri/vin-rose-ca-dei-frati-rosa-dei-frati-0-75l.html"},
            {"Magazin": "Wine360", "URL": "https://wine360.ro/ca-dei-frati-rosa-dei-frati-riviera-del-garda-classico"},
            {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-roze/ca-dei-frati-rosa-dei-frati-roze/"}
        ]
    },
    "Le Volte dell'Ornellaia": {
        "min_price": 90,
        "max_price": 300,
        "surse": [
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"},
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
        ]
    }
}

# --- INTERFAȚĂ ---
st.title("🍷 Scrutin Vinuri Premium")
vin_ales = st.selectbox("Alege vinul:", list(BAZA_DATE_VINURI.keys()))

if st.button(f"🔍 Scanează prețuri pentru {vin_ales}"):
    config = BAZA_DATE_VINURI[vin_ales]
    results = []
    
    progress_bar = st.progress(0)
    status_msg = st.empty()
    
    for i, s in enumerate(config["surse"]):
        status_msg.text(f"Se analizează {s['Magazin']}...")
        pret = get_wine_price(s["URL"], config["min_price"], config["max_price"])
        
        if pret:
            results.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
        
        progress_bar.progress((i + 1) / len(config["surse"]))
        time.sleep(1.5)

    status_msg.empty()

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.success(f"Am găsit {len(results)} magazine active!")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        for r in results:
            st.link_button(f"🛒 {r['Magazin']}: {r['Preț (RON)']} RON", r['Link'])
    else:
        st.error("Nicio ofertă găsită. Site-urile ar putea fi temporar inaccesibile.")
