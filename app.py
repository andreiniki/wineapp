import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random
from datetime import datetime

# 1. CONFIGURARE & SECURITATE
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

# 2. MOTORUL DE CĂUTARE "NINJA"
def get_final_price_v11(url):
    # Schimbăm identitatea la fiecare cerere
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) Chrome/122.0.0.0 Safari/537.36'
    ]
    
    scraper = cloudscraper.create_scraper()
    headers = {
        'User-Agent': random.choice(agents),
        'Accept': 'text/html,application/xhtml+xml,xml;q=0.9,image/avif,webp,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        res = scraper.get(url, headers=headers, timeout=25)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, "html.parser")
        
        if "vinimondo.ro" in url:
            tag = soup.find("meta", property="product:price:amount")
            return clean_price(tag["content"]) if tag else None
        
        elif "king.ro" in url:
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            return clean_price(tag.text) if tag else None

        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".woocommerce-Price-amount bdi, .amount")
            return clean_price(tag.text) if tag else None

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            return clean_price(tag.text) if tag else None

        return None
    except:
        return None

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Monitorizare Prețuri")
    st.warning("⚠️ Notă: Verificarea durează aproximativ 30 de secunde pentru a evita blocarea de către magazine.")

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
            with st.status(f"Se caută la {s['Magazin']}...", expanded=False) as status:
                price = get_final_price_v11(s["URL"])
                if price:
                    results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Verificat la": now, "Link": s["URL"]})
                    status.update(label=f"✅ {s['Magazin']}: {price} RON", state="complete")
                else:
                    status.update(label=f"❌ {s['Magazin']}: Indisponibil acum", state="error")
                
                # Pauză random pentru a părea uman
                time.sleep(random.uniform(4.5, 7.5))
                progress_bar.progress((i + 1) / len(surse))

        if results:
            st.balloons()
            df = pd.DataFrame(results).sort_values(by="Preț (RON)")
            st.subheader("📊 Tabel Prețuri Finale (TVA inclus)")
            st.dataframe(df[["Magazin", "Preț (RON)", "Verificat la"]], use_container_
