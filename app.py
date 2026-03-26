import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# 1. CONFIGURARE
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

def extract_price(text):
    if not text: return None
    # Curățăm textul de simboluri și păstrăm doar cifrele/punctul
    clean = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", clean)
    if match:
        val = float(match.group(1))
        if val > 5000: val /= 100
        return round(val, 2)
    return None

# 2. MOTORUL HIBRID
def get_wine_data_v9(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        soup = BeautifulSoup(res.content, "html.parser")
        p_cu_tva = None
        p_fara_tva = None

        if "vinimondo.ro" in url:
            # Revenim la metoda V3 care a mers: meta tag-ul de pret
            tag = soup.find("meta", property="product:price:amount")
            if tag: p_cu_tva = extract_price(tag["content"])
        
        elif "king.ro" in url:
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            if tag: p_cu_tva = extract_price(tag.text)
            
        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".summary .price .woocommerce-Price-amount bdi")
            if tag: p_cu_tva = extract_price(tag.text)

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            if tag: p_cu_tva = extract_price(tag.text)

        # Calcul TVA 21%
        if p_cu_tva:
            p_fara_tva = round(p_cu_tva / 1.21, 2)
            return p_cu_tva, p_fara_tva, "Succes"
            
        return None, None, "Preț negăsit"
    except Exception as e:
        return None, None, str(e)

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Monitorizare Prețuri")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🔄 Scanează acum"):
        results = []
        for s in surse:
            with st.status(f"Analizăm {s['Magazin']}...") as status:
                p_tva, p_fara, msg = get_wine_data_v9(s["URL"])
                if p_tva:
                    results.append({
                        "Magazin": s["Magazin"],
                        "Preț cu TVA (21%)": f"{p_tva:.2f} RON",
                        "Preț fără TVA": f"{p_fara:.2f} RON",
                        "URL": s["URL"]
                    })
                    status.update(label=f"✅ {s['Magazin']}: {p_tva} RON", state="complete")
                else:
                    status.update(label=f"❌ {s['Magazin']}: Eșuat", state="error")
                time.sleep(2)

        if results:
            st.balloons()
            df = pd.DataFrame(results)
            st.subheader("📊 Tabel Comparativ")
            st.table(df[["Magazin", "Preț cu TVA (21%)", "Preț fără TVA"]])
            
            # Butoane rapide de acces
            cols = st.columns(len(results))
            for i, r in enumerate(results):
                cols[i].link_button(f"🛒 {r['Magazin']}", r['URL'])
