import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Le Volte Price Tracker", page_icon="🍷")

def clean_price(text):
    if not text: return None
    # Curățare agresivă pentru a extrage doar cifrele
    text = text.lower().replace('lei', '').replace('ron', '').strip()
    text = text.replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", text)
    if match:
        val = float(match.group(1))
        # Corecție pentru formatele de tip 12500 (fără separator)
        if val > 1000: val /= 100
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
        
        # 1. Verificăm Meta Tags (metoda cea mai stabilă)
        meta = soup.find("meta", property="product:price:amount")
        if meta: return clean_price(meta["content"])

        # 2. Selectori specifici pentru site-uri cu structură aparte
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return clean_price(tag.text)
        
        # 3. Căutare generală (pentru site-urile noi adăugate)
        price_tags = soup.find_all(class_=re.compile("price", re.I))
        for tag in price_tags:
            val = clean_price(tag.text)
            if val and 90 < val < 400: # Filtru de siguranță pentru 0.75L
                return val
        return None
    except:
        return None

# INTERFAȚĂ
st.title("🍷 Monitorizare: LE VOLTE")
st.markdown("Am inclus toate variantele de denumire găsite (*Le Volte*, *Ornellaia Le Volte*, *Le Volte dell Ornellaia*).")

if st.button("🚀 Scanează Ofertele"):
    # LISTA EXTINSĂ BAZATĂ PE CĂUTAREA DUPĂ "LE VOLTE"
    surse = [
        {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"},
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
        {"Magazin": "E-Bauturi", "URL": "https://www.e-bauturi.ro/cumpara/vin-rosu-ornellaia-le-volte-dell-ornellaia-0-75l-8447"},
        {"Magazin": "Alcool Scont", "URL": "https://www.alcoolscont.ro/vinuri/vin-rosu-le-volte-dell-ornellaia-0-75l.html"},
        {"Magazin": "Winesday", "URL": "https://shop.winesday.ro/vinuri-rosii/1149-le-volte-dell-ornellaia-toscana-igt-2021-ornellaia.html"},
        {"Magazin": "Drinkz", "URL": "https://drinkz.ro/vin-rosu-sec-le-volte-dell-ornellaia-0-75l"},
        {"Magazin": "Wine360", "URL": "https://wine360.ro/le-volte-dell-ornellaia-toscana-igt-rosso"},
        {"Magazin": "Nobil Wine", "URL": "https://nobilwine.ro/magazin/vinuri/vinuri-rosii/ornellaia-le-volte-dellornellaia/"},
        {"Magazin": "Despre Vin", "URL": "https://desprevin.ro/vinuri/le-volte-dell-ornellaia-2021-igp-toscana-rosso/"}
    ]

    results = []
    progress_bar = st.progress(0)
    
    for i, s in enumerate(surse):
        with st.spinner(f"Căutăm la {s['Magazin']}..."):
            price = get_wine_price(s["URL"])
            if price:
                results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Link": s["URL"]})
            # O mică pauză pentru a nu declanșa sistemele anti-bot
            time.sleep(1.2)
        progress_bar.progress((i + 1) / len(surse))

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.balloons()
        st.subheader("📊 Cele mai bune prețuri pentru LE VOLTE:")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        for r in results:
            st.link_button(f"🛒 Cumpără de la {r['Magazin']} - {r['Preț (RON)']} RON", r['Link'])
    else:
        st.error("Nu am putut găsi prețuri în acest moment. Verifică link-urile.")
