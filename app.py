import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random
from datetime import datetime

# 1. CONFIGURARE PAGINĂ
st.set_page_config(page_title="Wine Watcher", page_icon="🍷")
PASSWORD = "CodulEsteVinul"

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acces Privat")
        parola = st.text_input("Introdu parola:", type="password")
        if st.button("Intră"):
            if parola == PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Parolă incorectă!")
        return False
    return True

def clean_price(text):
    if not text: return None
    digits = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", digits)
    if match:
        val = float(match.group(1))
        if val > 5000: val /= 100
        return round(val, 2)
    return None

# 2. MOTORUL DE CĂUTARE (Focalizat pe preț final)
def get_final_price(url):
    # Folosim cloudscraper pentru a trece de protecții
    scraper = cloudscraper.create_scraper()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    try:
        res = scraper.get(url, headers=headers, timeout=20)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, "html.parser")
        
        if "vinimondo.ro" in url:
            # Selector specific pentru prețul corect de 125 RON
            tag = soup.find("meta", property="product:price:amount")
            return clean_price(tag["content"]) if tag else None
        
        elif "king.ro" in url:
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            return clean_price(tag.text) if tag else None

        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".summary .price .woocommerce-Price-amount bdi, .amount")
            return clean_price(tag.text) if tag else None

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            return clean_price(tag.text) if tag else None

        return None
    except:
        return None

# 3. INTERFAȚĂ UTILIZATOR
if check_password():
    st.title("🍷 Wine Watcher: Monitorizare Prețuri")
    st.write("Verifică prețul final (TVA inclus) pentru Le Volte dell'Ornellaia.")

    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🚀 Scanează Magazinele"):
        results = []
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        progress_bar = st.progress(0)
        for i, s in enumerate(surse):
            price = get_final_price(s["URL"])
            if price:
                results.append({
                    "Magazin": s["Magazin"], 
                    "Preț (RON)": price, 
                    "Ultima Verificare": now,
                    "Link": s["URL"]
                })
            # Pauză esențială pentru a evita blocarea
            time.sleep(random.uniform(2, 4))
            progress_bar.progress((i + 1) / len(surse))

        if results:
            st.balloons()
            df = pd.DataFrame(results).sort_values(by="Preț (RON)")
            st.subheader("📊 Rezultate Actualizate")
            st.dataframe(df[["Magazin", "Preț (RON
