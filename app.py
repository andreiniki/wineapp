import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# 1. CONFIGURARE & SECURITATE
st.set_page_config(page_title="Wine Watcher RO", page_icon="🍷")
PASSWORD = "CodulEsteVinul"

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acces Privat Crama")
        parola = st.text_input("Introdu parola:", type="password")
        if st.button("Intră"):
            if parola == PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Parolă incorectă!")
        return False
    return True

# 2. MOTORUL DE SCRAPING - CALIBRAT PENTRU 0.75L
def get_price_v3(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, f"Eroare Server ({res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        page_text = soup.get_text().lower()
        
        # Validare 0.75L: Dacă pagina menționează Magnum sau 1.5L dominant, dăm avertisment
        is_magnum = "1.5l" in page_text or "magnum" in page_text
        is_standard = "0.75" in page_text or "750ml" in page_text or "75cl" in page_text

        text_pret = ""

        # Strategie specifică pe site-uri
        if "vinimondo.ro" in url:
            meta = soup.find("meta", property="product:price:amount")
            text_pret = meta["content"] if meta else ""
        
        elif "king.ro" in url:
            # Calibrare pentru 120.74 RON
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag:
                text_pret = tag.text

        elif "crushwineshop.ro" in url:
            tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
            text_pret = tag.text if tag else ""

        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            text_pret = tag.text if tag else ""

        # Fallback dacă nu a găsit prin selectori
        if not text_pret:
            match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', soup.get_text(), re.IGNORECASE)
            if match:
                text_pret = match.group(1)

        if text_pret:
            clean_digits = text_pret.replace(',', '.').replace(' ', '')
            numere = re.findall(r"[-+]?\d*\.\d+|\d+", clean_digits)
            if numere:
                valoare = float(numere[0])
                if valoare > 2000: valoare = valoare / 100
                
                # Filtru de siguranță: Un 0.75L rar costă peste 250 RON sau sub 80 RON
                if is_magnum and not is_standard and valoare > 220:
                    return None, "Detectată variantă Magnum (1.5L)"
                
                return valoare, "Succes"
                
        return None, "Nu am putut citi prețul"
    except Exception as e:
        return None, f"Eroare tehnică: {str(e)[:30]}"

# 3. INTERFAȚA
if check_password():
    st.title("🍷 Wine Watcher: Ornellaia 0.75L")
    st.caption("Căutare filtrată exclusiv pentru varianta standard de 750ml.")

    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🚀 Verifică Oferte 0.75L"):
        rezultate = []
        erori = []
        bara = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Căutăm {s["Magazin"]} (sticla 0.75L)...'):
                pret, msg = get_price_v3(s["URL"])
