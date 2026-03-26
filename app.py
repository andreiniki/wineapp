import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Wine Watcher Premium", page_icon="🍷")

def clean_price(text):
    if not text: return None
    text = text.lower().replace('lei', '').replace('ron', '').strip()
    text = text.replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", text)
    if match:
        val = float(match.group(1))
        if val > 1000: val /= 100
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
        
        # Metoda 1: Meta Tags
        meta = soup.find("meta", property="product:price:amount")
        if meta: 
            p = clean_price(meta["content"])
            if p and min_p < p < max_p: return p

        # Metoda 2: Selectori King.ro
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return clean_price(tag.text)
        
        # Metoda 3: Căutare generală
        price_tags = soup.find_all(class_=re.compile("price", re.I))
        for tag in price_tags:
            val = clean_price(tag.text)
            if val and min_p < val < max_p:
                return val
        return None
    except:
        return None

# --- CONFIGURARE SURSE ---
BAZA_DATE_VINURI = {
    "Le Volte dell'Ornellaia": {
        "min_price": 90,
        "max_price": 300,
        "surse": [
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"},
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
            {"Magazin": "Alcool Scont", "URL": "https://www.alcoolscont.ro/vinuri/vin-rosu-le-volte-dell-ornellaia-0-75l.html"},
            {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rosu-sec-le-volte-dell-ornellaia-0-75l"}
        ]
    },
    "Rosa dei Frati (Ca' dei Frati)": {
        "min_price": 60,
        "max_price": 150,
        "surse": [
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ca-dei-frati-rosa-dei-frati-075l"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ca-dei-frati-rosa-dei-frati-0.750-l.html"},
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/ca-dei-frati-rosa-dei-frati-riviera-del-garda-classico-doc-ca-dei-frati-ro"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/ca-dei-frati-rosa-dei-frati-0-75l"},
            {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rose-sec-ca-dei-frati-rosa-dei-frati-0-75l"},
            {"Magazin": "Alcool Scont", "URL": "https://www.alcoolscont.ro/vinuri/vin-rose-ca-dei-frati-rosa-dei-frati-0-75l.html"},
            {"Magazin": "Wine360", "URL": "https://wine360.ro/ca-dei-frati-rosa-dei-frati-riviera-del-garda-classico"},
            {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-roze/ca-dei-frati-rosa-dei-frati-roze/"}
        ]
    }
}

# --- INTERFAȚĂ ---
st.title("🍷 Wine Watcher: Monitorizare Prețuri")
vin_ales = st.selectbox("Alege vinul pe care vrei să-l verifici:", list(BAZA_DATE_VINURI.keys()))

if st.button(f"🔍 Verifică prețuri pentru {vin_ales}"):
    config = BAZA_DATE_VINURI[vin_ales]
    results = []
    
    progress_bar = st.progress(0)
    status_msg = st.empty()
    
    for i, s in enumerate(config["surse"]):
        status_msg.text(f"Se verifică {s['Magazin']}...")
        pret = get_wine_price(s["URL"], config["min_price"], config["max_price"])
        
        if pret:
            results.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
        
        progress_bar.progress((i + 1) / len(config["surse"]))
        time.sleep(1.2)

    status_msg.empty()

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.success(f"Am găsit {len(results)} oferte pentru {vin_ales}!")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        for r in results:
            st.link_button(f"🛒 {r['Magazin']}: {r['Preț (RON)']} RON", r['Link'])
    else:
        st.error("Nu am găsit nicio ofertă validă. Verifică link-urile manual.")
