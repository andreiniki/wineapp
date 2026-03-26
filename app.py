import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random

# 1. CONFIGURARE & PAROLĂ
st.set_page_config(page_title="Wine Watcher RO", page_icon="🍷", layout="wide")
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

# 2. LOGICA DE EXTRACȚIE ROBUSTĂ
def get_wine_data_v10(url):
    # Identități false pentru a păcăli protecția
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    ]
    
    scraper = cloudscraper.create_scraper()
    headers = {
        'User-Agent': random.choice(agents),
        'Referer': 'https://www.google.com/'
    }

    try:
        res = scraper.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return None, None, f"Blocat (Cod {res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        p_cu_tva = None

        # Strategie per site (bazată pe ce a funcționat anterior)
        if "vinimondo.ro" in url:
            tag = soup.find("meta", property="product:price:amount")
            if tag: p_cu_tva = float(tag["content"])
        
        elif "king.ro" in url:
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            if not tag: tag = soup.select_one(".price-final_price .price")
            if tag: p_cu_tva = float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.')))

        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".woocommerce-Price-amount bdi, .price .amount")
            if tag: p_cu_tva = float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.')))

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            if tag: p_cu_tva = float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.')))

        if p_cu_tva:
            # Corecție zecimale (ex: 12500 -> 125.0)
            if p_cu_tva > 2000: p_cu_tva /= 100
            p_fara_tva = round(p_cu_tva / 1.21, 2)
            return round(p_cu_tva, 2), p_fara_tva, "Succes"
            
        return None, None, "Preț negăsit în pagină"
    except Exception as e:
        return None, None, "Eroare conexiune"

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Ornellaia")
    st.info("Sfat: Dacă primești erori, așteaptă 2 minute înainte de a scana din nou pentru a evita blocarea IP-ului.")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🚀 Scanează Magazinele"):
        results = []
        for s in surse:
            with st.spinner(f"Se verifică {s['Magazin']}..."):
                p_tva, p_fara, msg = get_wine_data_v10(s["URL"])
                if p_tva:
                    results.append({
                        "Magazin": s["Magazin"],
                        "Preț cu TVA": f"{p_tva:.2f} RON",
                        "Preț fără TVA": f"{p_fara:.2f} RON",
                        "Status": "✅ OK"
                    })
                else:
                    results.append({
                        "Magazin": s["Magazin"],
                        "Preț cu TVA": "N/A",
                        "Preț fără TVA": "N/A",
                        "Status": f"❌ {msg}"
                    })
                time.sleep(random.uniform(2, 4)) # Pauză variabilă pentru a părea uman

        df = pd.DataFrame(results)
        st.subheader("📊 Rezultate Actualizate")
        st.dataframe(df, use_container_width=True, hide_index=True)
