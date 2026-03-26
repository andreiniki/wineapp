import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# 1. CONFIGURARE
st.set_page_config(page_title="Wine Watcher RO", page_icon="🍷")
PASSWORD = "CodulEsteVinul"

if "password_correct" not in st.session_state:
    st.title("🔐 Acces Privat Crama")
    parola = st.text_input("Introdu parola:", type="password")
    if st.button("Intră"):
        if parola == PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Parolă incorectă!")
    st.stop()

# 2. MOTORUL DE CĂUTARE (Calibrat 0.75L)
def get_price_v3(url):
    # Folosim un browser mai "uman" pentru a evita eroarea 403/Indisponibil
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, f"Serverul a refuzat conexiunea (Cod {res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        text_pret = ""

        if "vinimondo.ro" in url:
            meta = soup.find("meta", property="product:price:amount")
            text_pret = meta["content"] if meta else ""
        
        elif "king.ro" in url:
            # Selectorul pentru 120.74 RON
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            text_pret = tag.text if tag else ""

        elif "crushwineshop.ro" in url:
            tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
            text_pret = tag.text if tag else ""

        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            text_pret = tag.text if tag else ""

        if text_pret:
            clean_digits = text_pret.replace(',', '.').replace(' ', '')
            numere = re.findall(r"\d+\.\d+|\d+", clean_digits)
            if numere:
                valoare = float(numere[0])
                if valoare > 2000: valoare /= 100
                return valoare, "Succes"
                
        return None, "Preț negăsit în pagină"
    except Exception as e:
        return None, "Timeout sau blocaj IP"

# 3. INTERFAȚĂ
st.title("🍷 Wine Watcher: Ornellaia 0.75L")

surse = [
    {"Magazin": "Vinimondo", "URL": "
