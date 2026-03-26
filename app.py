import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# 1. CONFIGURARE & SECURITATE
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

# 2. MOTORUL DE DETECȚIE TVA
def get_wine_data(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, None, f"Eroare Server ({res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        p_cu_tva = None
        p_fara_tva = None

        if "vinimondo.ro" in url:
            meta = soup.find("meta", property="product:price:amount")
            if meta: p_cu_tva = float(meta["content"])
        
        elif "king.ro" in url:
            # King afișează ambele în span-uri cu clase specifice
            tva_tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            no_tva_tag = soup.select_one('span[data-price-type="basePrice"] .price')
            if tva_tag: p_cu_tva = float(re.sub(r'[^\d.]', '', tva_tag.text.replace(',', '.')))
            if no_tva_tag: p_fara_tva = float(re.sub(r'[^\d.]', '', no_tva_tag.text.replace(',', '.')))

        elif "crushwineshop.ro" in url:
            # Crush de obicei are prețul final vizibil
            tag = soup.select_one(".woocommerce-Price-amount bdi, .price .amount")
            if tag: p_cu_tva = float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.')))

        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            if tag: p_cu_tva = float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.')))

        # Curățare valori (dacă au fost citite greșit ca 12500 în loc de 125.0)
        if p_cu_tva and p_cu_tva > 2000: p_cu_tva /= 100
        if p_fara_tva and p_fara_tva > 2000: p_fara_tva /= 100

        if p_cu_tva or p_fara_tva:
            return p_cu_tva, p_fara_tva, "Succes"
                
        return None, None, "Prețuri negăsite"
    except Exception as e:
        return None, None, f"Eroare: {str(e)[:20]}"

# 3. INTERFAȚA
if check_password():
    st.title("🍷 Wine Watcher: Comparativ TVA")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🔄 Verifică Prețurile (Cu/Fără TVA)"):
        rezultate = []
        erori = []
        bara = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Analizăm {s["Magazin"]}...'):
                tva_da, tva_nu, msg = get_wine_data(s["URL"])
                if tva_da or tva_nu:
                    rezultate.append({
                        "Magazin": s["Magazin"], 
                        "Preț cu TVA (RON)": tva_da if tva_da else "N/A",
                        "Preț fără TVA (RON)": tva_nu if tva_nu else "N/A",
                        "Link": s["URL"]
                    })
                else:
                    erori.append(f"{s['Magazin']}: {msg}")
                time.sleep(2)
            bara.progress((i + 1) / len(surse))
        
        if rezultate:
            df = pd.DataFrame(rezultate)
            # Sortăm după prețul cu TVA (dacă există)
            df_display = df.copy()
            st.balloons()
            
            st.write("### Clasament Detaliat:")
            st.dataframe(df_display, use_container_width=True)
            
            for _, row in df.iterrows():
                label = f"🛒 {row['Magazin']} - {row['Preț cu TVA (RON)']} RON"
                st.link_button(label, row['Link'])
        
        if erori:
            with st.expander("⚠️ Detalii erori"):
                for e in erori: st.write(e)
