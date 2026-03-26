import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Wine Watcher: Le Volte", page_icon="🍷")

def clean_price(text):
    if not text: return None
    # Curățăm textul de simboluri și litere
    text = text.lower().replace('lei', '').replace('ron', '').strip()
    text = text.replace(',', '.')
    # Extragem prima secvență de cifre care arată a preț
    match = re.search(r"(\d+\.\d+|\d+)", text)
    if match:
        val = float(match.group(1))
        if val > 1000: val /= 100  # Corecție pentru formatul 12500 în loc de 125.00
        return round(val, 2)
    return None

def get_wine_price(url):
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Metoda 1: Meta Tags (Cele mai sigure)
        meta = soup.find("meta", property="product:price:amount")
        if meta: return clean_price(meta["content"])

        # Metoda 2: Selectori specifici pentru magazine populare
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return clean_price(tag.text)
        
        if "finestore.ro" in url:
            tag = soup.select_one(".price-new") or soup.select_one(".price")
            if tag: return clean_price(tag.text)

        # Metoda 3: Căutare generală după clasa "price"
        price_tags = soup.find_all(class_=re.compile("price", re.I))
        for tag in price_tags:
            val = clean_price(tag.text)
            if val and 90 < val < 400: # Filtru de siguranță pentru 0.75L
                return val
        return None
    except:
        return None

# INTERFAȚĂ
st.title("🍷 Scrutin: Le Volte dell'Ornellaia")
st.info("Monitorizăm prețurile în timp real din cele mai importante magazine din RO.")

if st.button("🚀 Scanează Toate Magazinele"):
    # LISTA TA DE SURSE ACTUALIZATĂ
    surse = [
        {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
        {"Magazin": "E-Bauturi", "URL": "https://www.e-bauturi.ro/cumpara/vin-rosu-ornellaia-le-volte-dell-ornellaia-0-75l-8447"},
        {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-rosii/ornellaia-le-volte-dellornellaia/"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "ProduseItaliene", "URL": "https://www.produseitaliene.ro/vinuri-italiene/vinuri-rosii/le-volte-dell-ornellaia-igt-toscana-750-ml-2022"}
    ]

    results = []
    status = st.empty()
    progress = st.progress(0)
    
    for i, s in enumerate(surse):
        status.text(f"🔎 Analizăm oferta de la {s['Magazin']}...")
        price = get_wine_price(s["URL"])
        if price:
            results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Link": s["URL"]})
        
        progress.progress((i + 1) / len(surse))
        time.sleep(1.2) # Pauză scurtă pentru a evita blocajele de tip "429 Too Many Requests"

    status.empty()

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.balloons()
        st.subheader("📊 Rezultate Găsite:")
        
        # Tabel curat
        st.dataframe(df[["Magazin", "Preț (RON)"]], use_container_width=True, hide_index=True)
        
        # Butoane de acces rapid
        st.write("---")
        cols = st.columns(2)
        for idx, row in df.iterrows():
            with cols[idx % 2]:
                st.link_button(f"🛒 {row['Magazin']}: {row['Preț (RON)']} RON", row['Link'])
    else:
        st.error("Nu am putut prelua prețurile. Verificați conexiunea la internet sau link-urile.")
