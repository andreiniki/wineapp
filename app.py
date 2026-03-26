import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Wine Watcher Pro", page_icon="🍷")

def clean_price(text, min_p, max_p):
    if not text: return None
    # Curățăm tot ce nu e cifră, punct sau virgulă
    clean = re.sub(r'[^\d.,]', '', str(text)).replace(',', '.')
    try:
        # Rezolvăm problema numerelor cu mai multe puncte (ex: 108.70.00)
        if clean.count('.') > 1:
            parts = clean.split('.')
            clean = f"{parts[0]}.{parts[1]}"
        
        val = float(clean)
        # Dacă prețul e prea mic (ex: 10.87 în loc de 108.7), corectăm
        if val < 20: val *= 10
        # Dacă prețul e uriaș (ex: 10870), corectăm
        if val > 1000: val /= 100
        
        # Validăm dacă prețul se încadrează în plaja logică pentru acest vin
        if min_p <= val <= max_p:
            return round(val, 2)
    except:
        return None
    return None

def get_wine_price(url, min_p, max_p):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, "html.parser")

        # Prioritate 1: Selectoare specifice pentru King.ro (pentru a evita prețul greșit)
        if "king.ro" in url:
            # Căutăm exact tag-ul de preț final
            price_tag = soup.select_one('span[data-price-type="finalPrice"] .price') or \
                        soup.select_one('.product-info-main .price')
            if price_tag:
                return clean_price(price_tag.text, min_p, max_p)

        # Prioritate 2: Meta Tags (Standarde e-commerce)
        meta = soup.find("meta", property="product:price:amount") or \
               soup.find("meta", attrs={"name": "twitter:data1"})
        if meta:
            p = clean_price(meta.get("content", ""), min_p, max_p)
            if p: return p

        # Prioritate 3: Căutare în elemente cu clasa 'price'
        for tag in soup.find_all(class_=re.compile("price", re.I)):
            p = clean_price(tag.get_text(), min_p, max_p)
            if p: return p
            
        return None
    except:
        return None

# --- SURSE REVERIFICATE ---
VINURI = {
    "Le Volte dell'Ornellaia": {
        "min": 100, "max": 180,
        "surse": [
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
            {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rosu-sec-le-volte-dell-ornellaia-0-75l"},
            {"Magazin": "Alcool Scont", "URL": "https://www.alcoolscont.ro/vinuri/vin-rosu-le-volte-dell-ornellaia-0-75l.html"},
            {"Magazin": "E-Bauturi", "URL": "https://www.e-bauturi.ro/cumpara/vin-rosu-ornellaia-le-volte-dell-ornellaia-0-75l-8447"},
            {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-rosii/ornellaia-le-volte-dellornellaia/"}
        ]
    },
    "Rosa dei Frati": {
        "min": 70, "max": 120,
        "surse": [
            {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ca-dei-frati-rosa-dei-frati-075l"},
            {"Magazin": "King.ro", "URL": "https://king.ro/ca-dei-frati-rosa-dei-frati-0.750-l.html"},
            {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/ca-dei-frati-rosa-dei-frati-riviera-del-garda-classico-doc-ca-dei-frati-ro"},
            {"Magazin": "WineMag", "URL": "https://www.winemag.ro/ca-dei-frati-rosa-dei-frati-0-75l"},
            {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rose-sec-ca-dei-frati-rosa-dei-frati-0-75l"},
            {"Magazin": "World of Wines", "URL": "https://worldofwines.ro/ca-dei-frati-rosa-dei-frati-075l"}
        ]
    }
}

st.title("🍷 Scrutin Național: Le Volte & Rosa dei Frati")
selectie = st.selectbox("Selectează vinul:", list(VINURI.keys()))

if st.button(f"🔍 Verifică Oferte Active"):
    config = VINURI[selectie]
    results = []
    bar = st.progress(0)
    
    for i, s in enumerate(config["surse"]):
        with st.spinner(f"Scanăm {s['Magazin']}..."):
            p = get_wine_price(s["URL"], config["min"], config["max"])
            if p:
                results.append({"Magazin": s["Magazin"], "Preț": p, "Link": s["URL"]})
        bar.progress((i + 1) / len(config["surse"]))
        time.sleep(1.5)

    if results:
        df = pd.DataFrame(results).sort_values("Preț")
        st.success(f"Găsit {len(results)} magazine!")
        st.dataframe(df[["Magazin", "Preț"]], hide_index=True, use_container_width=True)
        for r in results:
            st.link_button(f"🛒 {r['Magazin']} - {r['Preț']} RON", r['Link'])
    else:
        st.error("Nicio ofertă validă găsită. Site-urile pot fi protejate.")
