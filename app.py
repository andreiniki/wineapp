import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random
from datetime import datetime

# 1. SETUP INTERFAȚĂ (Interfața pe care ai ales-o)
st.set_page_config(page_title="Wine Watcher", page_icon="🍷", layout="wide")

# CSS pentru a face interfața să arate exact ca în screenshot-ul tău preferat
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stStatus { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Parolă simplă
if "auth" not in st.session_state:
    parola = st.sidebar.text_input("Parolă:", type="password")
    if parola == "CodulEsteVinul":
        st.session_state["auth"] = True
    else:
        st.info("Introdu parola în lateral pentru a activa scanerul.")
        st.stop()

def clean_price(text):
    if not text: return None
    # Elimină orice caracter care nu e cifră sau punct/virgulă
    digits = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", digits)
    if match:
        val = float(match.group(1))
        # Dacă prețul e uriaș (ex 12500), e clar formatare greșită de site
        if val > 5000: val /= 100 
        return round(val, 2)
    return None

# 2. MOTORUL DE CĂUTARE (Ultima încercare de forțare)
def get_wine_data(url):
    # Simulăm un browser de Windows foarte comun
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    
    try:
        # Adăugăm un delay random înainte de fiecare cerere (1-3 sec)
        time.sleep(random.uniform(1, 3))
        res = scraper.get(url, timeout=20)
        
        if res.status_code != 200:
            return None, f"Eroare Server ({res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        
        if "vinimondo.ro" in url:
            # Metoda de aur pentru 125 RON
            tag = soup.find("meta", property="product:price:amount")
            p = clean_price(tag["content"]) if tag else None
            return p, "Succes" if p else "Preț negăsit"
        
        elif "king.ro" in url:
            # Selectorul final care evită zecimalele infinite
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            if not tag: tag = soup.select_one(".price-final_price .price")
            p = clean_price(tag.text) if tag else None
            return p, "Succes" if p else "Preț negăsit"

        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".woocommerce-Price-amount bdi")
            p = clean_price(tag.text) if tag else None
            return p, "Succes" if p else "Preț negăsit"

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            p = clean_price(tag.text) if tag else None
            return p, "Succes" if p else "Preț negăsit"

        return None, "Site nerecunoscut"
    except Exception as e:
        return None, "Blocaj IP/Timeout"

# 3. LOGICA DE AFIȘARE
st.title("🍷 Wine Watcher: Monitorizare Prețuri")
st.info("ℹ️ Notă: Verificarea durează aproximativ 30 de secunde pentru a evita blocarea.")

surse = [
    {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
    {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
    {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
    {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
]

if st.button("🚀 Scanează Magazinele"):
    results = []
    now = datetime.now().strftime("%d/%m %H:%M")
    
    progress = st.progress(0)
    
    for i, s in enumerate(surse):
        with st.status(f"Căutăm la {s['Magazin']}...", expanded=False) as status:
            pret, msg = get_wine_data(s["URL"])
            
            if pret:
                results.append({"Magazin": s["Magazin"], "Preț": pret, "Ora": now, "Link": s["URL"]})
                status.update(label=f"✅ {s['Magazin']}: {pret} RON", state="complete")
            else:
                status.update(label=f"❌ {s['Magazin']}: {msg}", state="error")
            
            # Pauză între magazine (4-6 secunde) - CRUCIALĂ
            time.sleep(random.uniform(4, 6))
            progress.progress((i + 1) / len(surse))

    if results:
        st.balloons()
        df = pd.DataFrame(results).sort_values(by="Preț")
        st.subheader("📊 Clasament Prețuri Finale (TVA Inclus)")
        st.dataframe(df[["Magazin", "Preț", "Ora"]], use_container_width=True, hide_index=True)
        
        # Butoane de acțiune
        cols = st.columns(len(results))
        for idx, row in enumerate(results):
            with cols[idx]:
                st.link_button(f"🛒 {row['Magazin']}", row['Link'])
    else:
        st.error("❌ Blocaj total. Site-urile refuză conexiunea de pe acest server. Încearcă peste 15 minute.")
