import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

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
        
        # 1. VINIMONDO
        if "vinimondo.ro" in url:
            tag = soup.find("meta", property="product:price:amount")
            return clean_price(tag["content"]) if tag else None
        
        # 2. KING.RO (Reparat)
        elif "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if not tag: tag = soup.select_one(".price-final_price .price")
            return clean_price(tag.text) if tag else None

        # 3. CRUSH
        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".woocommerce-Price-amount bdi")
            if not tag: tag = soup.select_one("p.price ins span.woocommerce-Price-amount")
            return clean_price(tag.text) if tag else None

        # 4. WINEMAG
        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            return clean_price(tag.text) if tag else None
            
        # 5. MOTOR GENERIC (Pentru orice alt site pe care îl adaugi tu în listă)
        else:
            meta = soup.find("meta", property="product:price:amount")
            if meta: return clean_price(meta["content"])
            
            # Caută numere în format de preț prin tot textul paginii
            text = soup.get_text()
            match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', text, re.IGNORECASE)
            if match: return clean_price(match.group(1))
            
        return None
    except:
        return None

# INTERFAȚĂ
st.title("🍷 Wine Watcher: Monitorizare Stabilă")
st.write("Apasă butonul pentru a verifica prețurile actuale. Fără Google, fără blocaje.")

if st.button("🔄 Actualizează Prețurile"):
    # AICI POȚI ADĂUGA ORICÂTE MAGAZINE VREI, DOAR PUI LINK-UL CĂTRE VIN
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"}
    ]

    results = []
    bara = st.progress(0)
    
    for i, s in enumerate(surse):
        with st.spinner(f"Verificăm {s['Magazin']}..."):
            price = get_wine_price(s["URL"])
            if price:
                results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Link": s["URL"]})
            # Pauză esențială de 2 secunde între site-uri
            time.sleep(2)
        bara.progress((i + 1) / len(surse))

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.balloons()
        st.subheader("Clasament oferte:")
        st.dataframe(df[["Magazin", "Preț (RON)"]], use_container_width=True)
        
        for r in results:
            st.link_button(f"🛒 Cumpără de la {r['Magazin']} ({r['Preț (RON)']} RON)", r['Link'])
    else:
        st.error("Nu am putut prelua prețurile temporar.")
