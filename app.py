import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Wine Watcher", page_icon="🍷")

def clean_price(text):
    if not text: return None
    # Eliminăm "lei", "ron", spațiile și alte caractere, păstrăm doar cifre, punct și virgulă
    text = text.lower().replace('lei', '').replace('ron', '').strip()
    # Înlocuim virgula cu punct pentru formatul zecimal
    text = text.replace(',', '.')
    # Extragem doar grupul de cifre (ex: din "125.00 lei" extragem "125.00")
    match = re.search(r"(\d+\.\d+|\d+)", text)
    if match:
        val = float(match.group(1))
        # Dacă prețul e uriaș (ex: 12500 în loc de 125.00), îl corectăm
        if val > 1000: val /= 100
        return round(val, 2)
    return None

def get_wine_price(url):
    # Creăm un scraper care imită un browser real de Windows
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    try:
        # Adăugăm un timeout mai mare și headers de browser
        res = scraper.get(url, timeout=20)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Încercăm mai multe metode de a găsi prețul, de la cea mai sigură la cea mai generală
        
        # 1. Metoda Meta (Standard pentru majoritatea magazinelor)
        meta_price = soup.find("meta", property="product:price:amount")
        if meta_price: 
            return clean_price(meta_price["content"])

        # 2. Specific pentru King.ro
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return clean_price(tag.text)

        # 3. Specific pentru Vinimondo
        if "vinimondo.ro" in url:
            tag = soup.select_one(".price-wrapper .price")
            if tag: return clean_price(tag.text)

        # 4. Metoda Disperată: Căutăm orice clasă care conține cuvântul "price"
        price_tags = soup.find_all(class_=re.compile("price", re.I))
        for tag in price_tags:
            val = clean_price(tag.text)
            if val and 80 < val < 500: # Filtru de siguranță pentru preț real
                return val

        return None
    except Exception as e:
        return None

# INTERFAȚĂ
st.title("🍷 Monitorizare Prețuri: Le Volte")

if st.button("🔄 Actualizează Prețurile Acum"):
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
        {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"}
    ]

    results = []
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    for i, s in enumerate(surse):
        status_text.text(f"Se verifică {s['Magazin']}...")
        price = get_wine_price(s["URL"])
        if price:
            results.append({"Magazin": s["Magazin"], "Preț": f"{price} RON", "val": price, "Link": s["URL"]})
        
        progress_bar.progress((i + 1) / len(surse))
        time.sleep(1) # O mică pauză să nu fim agresivi

    status_text.empty()

    if results:
        # Sortăm după valoarea numerică a prețului
        df = pd.DataFrame(results).sort_values(by="val")
        st.success("Prețuri actualizate cu succes!")
        st.table(df[["Magazin", "Preț"]])
        
        for r in results:
            st.link_button(f"🛒 Mergi la {r['Magazin']}", r['Link'])
    else:
        st.error("Niciun preț nu a putut fi extras. Verifică dacă link-urile mai sunt valabile.")
