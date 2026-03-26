import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# CONFIGURARE
st.set_page_config(page_title="Wine Watcher", page_icon="🍷")

def clean_price(text):
    if not text: return None
    # Păstrăm doar cifrele și punctul/virgula
    digits = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", digits)
    if match:
        val = float(match.group(1))
        # Corecție pentru formate de tipul 12500
        if val > 5000: val /= 100
        return round(val, 2)
    return None

def get_wine_price(url):
    scraper = cloudscraper.create_scraper()
    try:
        res = scraper.get(url, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        if "vinimondo.ro" in url:
            # Metoda care a dat 125 RON
            tag = soup.find("meta", property="product:price:amount")
            return clean_price(tag["content"]) if tag else None
        
        elif "king.ro" in url:
            # Calibrare pentru 120.74 RON
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if not tag: tag = soup.select_one(".price-final_price .price")
            return clean_price(tag.text) if tag else None

        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".woocommerce-Price-amount bdi")
            return clean_price(tag.text) if tag else None

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            return clean_price(tag.text) if tag else None
            
        return None
    except:
        return None

# INTERFAȚĂ ORIGINALĂ
st.title("🍷 Wine Watcher: Le Volte dell'Ornellaia")
st.write("Apasă butonul de mai jos pentru a verifica prețurile actuale (0.75L).")

if st.button("🔄 Actualizează Prețurile"):
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"}
    ]

    results = []
    for s in surse:
        with st.spinner(f"Verificăm {s['Magazin']}..."):
            price = get_wine_price(s["URL"])
            if price:
                results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Link": s["URL"]})
            # Pauză esențială pentru a evita blocajele detectate anterior
            time.sleep(2)

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.subheader("Clasament prețuri:")
        st.dataframe(df[["Magazin", "Preț (RON)"]], use_container_width=True)
        
        for r in results:
            st.link_button(f"🛒 Cumpără de la {r['Magazin']} ({r['Preț (RON)']} RON)", r['Link'])
    else:
        st.error("Nu am putut prelua prețurile. Site-urile pot fi temporar indisponibile.")
