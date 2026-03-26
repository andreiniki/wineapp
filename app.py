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

# 2. MOTORUL DE PRECIZIE
def get_price_v4(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, f"Eroare Server ({res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        text_pret = ""

        if "vinimondo.ro" in url:
            meta = soup.find("meta", property="product:price:amount")
            text_pret = meta["content"] if meta else ""
        
        elif "king.ro" in url:
            # Căutăm specific prețul final cu TVA
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            if not tag:
                tag = soup.find("span", class_="price")
            text_pret = tag.text if tag else ""

        elif "crushwineshop.ro" in url:
            # Crush folosește structura de WooCommerce cu <bdi>
            tag = soup.select_one(".summary .price .woocommerce-Price-amount bdi")
            if not tag:
                tag = soup.select_one(".price .woocommerce-Price-amount")
            text_pret = tag.text if tag else ""

        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            text_pret = tag.text if tag else ""

        if text_pret:
            # Curățare avansată: eliminăm spațiile non-breaking și tot ce nu e cifră/punct/virgulă
            clean_text = text_pret.replace('\xa0', '').replace(' ', '').replace(',', '.')
            # Extragem primul grup de cifre care arată a preț (ex: 125.00)
            match = re.search(r"(\d+[\.]?\d*)", clean_text)
            if match:
                valoare = float(match.group(1))
                # Dacă prețul e absurd de mic (sub 50 lei) sau mare, ignorăm
                if 50 < valoare < 1000:
                    return round(valoare, 2), "Succes"
                
        return None, "Preț invalid sau negăsit"
    except Exception as e:
        return None, f"Eroare: {str(e)[:30]}"

# 3. INTERFAȚA (Rămâne la fel, dar cu funcția nouă)
if check_password():
    st.title("🍷 Wine Watcher: Ornellaia")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🔄 Verifică Toate Prețurile"):
        rezultate = []
        erori = []
        bara = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Analizăm {s["Magazin"]}...'):
                pret, msg = get_price_v4(s["URL"])
                if pret:
                    rezultate.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
                else:
                    erori.append(f"{s['Magazin']}: {msg}")
                time.sleep(2)
            bara.progress((i + 1) / len(surse))
        
        if rezultate:
            df = pd.DataFrame(rezultate).sort_values(by="Preț (RON)")
            st.balloons()
            st.metric("Cea mai bună ofertă", f"{df.iloc[0]['Preț (RON)']} RON", f"la {df.iloc[0]['Magazin']}")
            st.table(df[["Magazin", "Preț (RON)"]])
            for _, row in df.iterrows():
                st.link_button(f"🛒 Cumpără de la {row['Magazin']} ({row['Preț (RON)']} RON)", row['Link'])
        
        if erori:
            with st.expander("⚠️ Detalii erori"):
                for e in erori: st.write(e)
