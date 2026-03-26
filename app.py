import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import random
from datetime import datetime

# 1. CONFIGURARE
st.set_page_config(page_title="Wine Watcher", page_icon="🍷", layout="wide")
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

# 2. MOTORUL DE CĂUTARE AVANSAT
def get_final_price_v12(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    # Încercăm de 2 ori pentru fiecare site dacă dă eroare
    for _ in range(2):
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                
                if "vinimondo.ro" in url:
                    tag = soup.find("meta", property="product:price:amount")
                    if tag: return clean_price(tag["content"])
                
                elif "king.ro" in url:
                    tag = soup.select_one('span[data-price-type="finalPrice"] .price')
                    if tag: return clean_price(tag.text)

                elif "crushwineshop.ro" in url:
                    tag = soup.select_one(".woocommerce-Price-amount bdi, .price .amount")
                    if tag: return clean_price(tag.text)

                elif "winemag.ro" in url:
                    tag = soup.select_one(".price-new, .price")
                    if tag: return clean_price(tag.text)
            
            time.sleep(2) # Pauză scurtă între reîncercări
        except:
            continue
    return None

# 3. INTERFAȚĂ (CEA DIN IMAGINEA TA)
if check_password():
    st.title("🍷 Wine Watcher: Monitorizare Prețuri")
    st.info("ℹ️ Notă: Verificarea durează aproximativ 30 de secunde pentru a evita blocarea de către magazine.")

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
            with st.status(f"Se verifică {s['Magazin']}...", expanded=False) as status:
                price = get_final_price_v12(s["URL"])
                if price:
                    results.append({"Magazin": s["Magazin"], "Preț (RON)": price, "Verificat la": now, "Link": s["URL"]})
                    status.update(label=f"✅ {s['Magazin']}: {price} RON", state="complete")
                else:
                    status.update(label=f"❌ {s['Magazin']}: Indisponibil acum", state="error")
                
                # Pauză între site-uri
                time.sleep(random.uniform(3, 5))
                progress_bar.progress((i + 1) / len(surse))

        if results:
            st.balloons()
            df = pd.DataFrame(results).sort_values(by="Preț (RON)")
            st.subheader("📊 Rezultate Actualizate (TVA Inclus)")
            st.dataframe(df[["Magazin", "Preț (RON)", "Verificat la"]], use_container_width=True, hide_index=True)
            
            # Butoane de cumpărare
            for row in results:
                st.link_button(f"🛒 Cumpără de la {row['Magazin']} ({row['Preț (RON)']} RON)", row['Link'])
        else:
            st.error("❌ Toate încercările au eșuat. Așteaptă 10 minute pentru resetarea IP-ului.")
