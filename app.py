import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime

# 1. CONFIGURARE FUNDAMENTALĂ (Fără brizbrizuri care pot genera erori)
st.set_page_config(page_title="Wine Watcher", page_icon="🍷", layout="wide")

if "password_correct" not in st.session_state:
    st.title("🔐 Acces Privat")
    parola = st.text_input("Introdu parola:", type="password")
    if st.button("Intră"):
        if parola == "CodulEsteVinul":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Parolă incorectă!")
    st.stop()

def clean_price(text):
    if not text: return None
    digits = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", digits)
    if match:
        val = float(match.group(1))
        if val > 5000: val /= 100  # Corecție pentru formate tip 12500
        return round(val, 2)
    return None

# 2. MOTORUL DE CĂUTARE (Versiunea Minimalistă)
def get_wine_price(url):
    scraper = cloudscraper.create_scraper()
    try:
        res = scraper.get(url, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        if "vinimondo.ro" in url:
            tag = soup.find("meta", property="product:price:amount")
            return clean_price(tag["content"]) if tag else None
        
        elif "king.ro" in url:
            # Selector mai precis pentru King.ro pentru a evita eroarea anterioară
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
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

# 3. INTERFAȚĂ (Păstrăm ce ți-a plăcut)
st.title("🍷 Wine Watcher: Monitorizare Prețuri")
st.info("ℹ️ Notă: Verificarea durează puțin pentru a evita blocarea de către magazine.")

surse = [
    {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
    {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
    {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
    {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
]

if st.button("🚀 Scanează Magazinele"):
    results = []
    now = datetime.now().strftime("%H:%M:%S")
    
    for s in surse:
        with st.status(f"Se verifică {s['Magazin']}...", expanded=False) as status:
            price = get_wine_price(s["URL"])
            if price:
                results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Ora": now, "Link": s["URL"]})
                status.update(label=f"✅ {s['Magazin']}: {price} RON", state="complete")
            else:
                status.update(label=f"❌ {s['Magazin']}: Indisponibil", state="error")
            time.sleep(3) # Pauză de siguranță

    if results:
        df = pd.DataFrame(results).sort_values(by="Preț (RON)")
        st.subheader("📊 Rezultate (TVA Inclus)")
        st.table(df[["Magazin", "Preț (RON)", "Ora"]])
        
        for r in results:
            st.link_button(f"🛒 {r['Magazin']} ({r['Preț (RON)']} RON)", r['Link'])
    else:
        st.error("⚠️ Toate magazinele au refuzat conexiunea. Așteaptă 10 minute și reîncearcă.")
