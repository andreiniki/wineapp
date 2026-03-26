import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Wine Watcher: Le Volte", page_icon="🍷")

def clean_price(text):
    if not text: return None
    # Curățăm caracterele inutile și forțăm formatul numeric
    text = text.lower().replace('lei', '').replace('ron', '').strip()
    text = text.replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", text)
    if match:
        val = float(match.group(1))
        # Corecție pentru site-urile care trimit prețul în format "12500" (fără punct)
        if val > 1000: val /= 100
        return round(val, 2)
    return None

def get_wine_price(url):
    # Folosim cloudscraper pentru a ocoli protecțiile magazinelor
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, "html.parser")
        
        # 1. Metoda Standard (Meta Tags)
        meta = soup.find("meta", property="product:price:amount")
        if meta: return clean_price(meta["content"])

        # 2. Selectori dedicați pentru King și Vinimondo
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return clean_price(tag.text)
        
        # 3. Metoda Generală (Căutare după orice clasă de preț)
        price_tags = soup.find_all(class_=re.compile("price", re.I))
        for tag in price_tags:
            val = clean_price(tag.text)
            if val and 90 < val < 400: # Siguranță pentru volumul de 0.75L
                return val
        return None
    except:
        return None

# INTERFAȚĂ
st.title("🍷 Monitorizare: Le Volte dell'Ornellaia")
st.write("Verificăm prețurile în magazinele selectate de tine.")

if st.button("🔄 Actualizează Prețurile Acum"):
    # LISTA TA COMPLETĂ DE MAGAZINE (Actualizată manual)
    surse = [
        {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"},
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
        {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rosu-sec-le-volte-dell-ornellaia-0-75l"},
        {"Magazin": "Wine360", "URL": "https://wine360.ro/le-volte-dell-ornellaia-toscana-igt-rosso"},
        {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-rosii/ornellaia-le-volte-dellornellaia/"},
        {"Magazin": "Crush Wine", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "ProduseItaliene", "URL": "https://www.produseitaliene.ro/vinuri-italiene/vinuri-rosii/le-volte-dell-ornellaia-igt-toscana-750-ml-2022"}
    ]

    results = []
    progress_bar = st.progress(0)
    
    for i, s in enumerate(surse):
        with st.spinner(f"Verificăm {s['Magazin']}..."):
            price = get_wine_price(s["URL"])
            if price:
                results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Link": s["URL"]})
            time.sleep(1.5) # Esențial pentru a evita blocajele
        progress_bar.progress((i + 1) / len(surse))

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.balloons()
        st.subheader("📊 Top Oferte Astăzi:")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        # Generăm butoane pentru fiecare magazin găsit
        for r in results:
            st.link_button(f"🛒 Mergi la {r['Magazin']} ({r['Preț (RON)']} RON)", r['Link'])
    else:
        st.error("Nu am putut prelua prețurile. S-ar putea ca site-urile să fie temporar inaccesibile.")
