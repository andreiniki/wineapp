import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Wine Watcher: Scrutin Total", page_icon="🍷")

# 1. MOTOR DE EXTRAGERE ULTRA-REZISTENT
def get_wine_price(url, min_p, max_p):
    # Folosim un set de headers mai "uman" pentru a păcăli protecțiile
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Eliminăm scripturile și stilurile care pot induce în eroare regex-ul
        for script in soup(["script", "style"]):
            script.decompose()

        # Strategia A: Căutăm în meta-tag-urile de produs (cele mai sigure)
        meta_p = soup.find("meta", property="product:price:amount") or \
                 soup.find("meta", attrs={"name": "twitter:data1"})
        if meta_p:
            p = clean_text_to_float(meta_p.get("content", ""))
            if p and min_p < p < max_p: return p

        # Strategia B: Căutare brutală (Regex) în tot textul paginii
        # Căutăm numere de forma 123,45 urmate de lei/ron
        full_text = soup.get_text(separator=' ')
        # Această formulă caută grupuri de cifre care arată a preț
        matches = re.findall(r'(\d+[\.,]\d{2})\s?(?:lei|RON)', full_text, re.IGNORECASE)
        
        valid_prices = []
        for m in matches:
            val = clean_text_to_float(m)
            if val and min_p < val < max_p:
                valid_prices.append(val)
        
        if valid_prices:
            # Returnăm cel mai mic preț valid găsit (de obicei e cel actual, nu cel vechi)
            return min(valid_prices)

        return None
    except:
        return None

def clean_text_to_float(text):
    if not text: return None
    # Curățăm textul de orice nu e cifră, punct sau virgulă
    clean = re.sub(r'[^\d.,]', '', str(text)).replace(',', '.')
    try:
        # Dacă avem mai multe puncte (ex 125.00.00), luăm doar prima parte
        if clean.count('.') > 1:
            clean = clean.split('.')[0] + '.' + clean.split('.')[1]
        val = float(clean)
        if val > 1000: val /= 100 # Corecție 12500 -> 125.00
        return round(val, 2)
    except:
        return None

# 2. BAZA DE DATE ACTUALIZATĂ (Sursă cu sursă)
VINURI = {
    "Le Volte dell'Ornellaia (Roșu)": {
        "min": 95, "max": 250,
        "surse": [
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
            {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rosu-sec-le-volte-dell-ornellaia-0-75l"},
            {"Magazin": "Alcool Scont", "URL": "https://www.alcoolscont.ro/vinuri/vin-rosu-le-volte-dell-ornellaia-0-75l.html"},
            {"Magazin": "E-Bauturi", "URL": "https://www.e-bauturi.ro/cumpara/vin-rosu-ornellaia-le-volte-dell-ornellaia-0-75l-8447"},
            {"Magazin": "Wine360", "URL": "https://wine360.ro/le-volte-dell-ornellaia-toscana-igt-rosso"},
            {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-rosii/ornellaia-le-volte-dellornellaia/"},
            {"Magazin": "ProduseItaliene", "URL": "https://www.produseitaliene.ro/vinuri-italiene/vinuri-rosii/le-volte-dell-ornellaia-igt-toscana-750-ml-2022"},
            {"Magazin": "Winesday", "URL": "https://shop.winesday.ro/vinuri-rosii/1149-le-volte-dell-ornellaia-toscana-igt-2021-ornellaia.html"}
        ]
    },
    "Rosa dei Frati (Rosé)": {
        "min": 65, "max": 140,
        "surse": [
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ca-dei-frati-rosa-dei-frati-075l"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ca-dei-frati-rosa-dei-frati-0.750-l.html"},
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/ca-dei-frati-rosa-dei-frati-riviera-del-garda-classico-doc-ca-dei-frati-ro"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/ca-dei-frati-rosa-dei-frati-0-75l"},
            {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rose-sec-ca-dei-frati-rosa-dei-frati-0-75l"},
            {"Magazin": "Alcool Scont", "URL": "https://www.alcoolscont.ro/vinuri/vin-rose-ca-dei-frati-rosa-dei-frati-0-75l.html"},
            {"Magazin": "E-Bauturi", "URL": "https://www.e-bauturi.ro/cumpara/vin-rose-ca-dei-frati-rosa-dei-frati-0-75l-4416"},
            {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-roze/ca-dei-frati-rosa-dei-frati-roze/"},
            {"Magazin": "World of Wines", "URL": "https://worldofwines.ro/ca-dei-frati-rosa-dei-frati-075l"},
            {"Magazin": "Gourmet Gift", "URL": "https://gourmetgift.ro/vin-rose/4342-vin-rose-ca-dei-frati-rosa-dei-frati-075l.html"}
        ]
    }
}

# 3. INTERFAȚĂ
st.title("🍷 Scrutin Național: Le Volte & Rosa dei Frati")
st.write("Verificăm peste 15 magazine de profil din România.")

produs_selectat = st.selectbox("Ce vin verificăm acum?", list(VINURI.keys()))

if st.button(f"🚀 Scanează toată piața pentru {produs_selectat}"):
    config = VINURI[produs_selectat]
    results = []
    
    prog_bar = st.progress(0)
    msg = st.empty()
    
    for i, s in enumerate(config["surse"]):
        msg.text(f"🔎 Căutăm la {s['Magazin']}...")
        pret = get_wine_price(s["URL"], config["min"], config["max"])
        
        if pret:
            results.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
        
        prog_bar.progress((i + 1) / len(config["surse"]))
        time.sleep(1.5) # Pauză vitală pentru a nu fi blocați

    msg.empty()

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.balloons()
        st.subheader(f"📊 Rezultate pentru {produs_selectat}:")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        for r in results:
            st.link_button(f"🛒 {r['Magazin']} - {r['Preț (RON)']} RON", r['Link'])
    else:
        st.error("Nicio ofertă găsită. Site-urile pot fi protejate sau stocurile epuizate.")
