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

def extract_clean_price(text):
    if not text: return None
    # Eliminăm tot ce nu e cifră sau punct/virgulă
    clean = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    match = re.search(r"(\d+\.\d+|\d+)", clean)
    if match:
        val = float(match.group(1))
        if val > 1000: val /= 100 # Corecție pentru formatări gen 12500
        return round(val, 2)
    return None

# 2. MOTORUL DE CĂUTARE
def get_wine_data_v6(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        soup = BeautifulSoup(res.content, "html.parser")
        p_cu_tva = None
        p_fara_tva = None

        if "vinimondo.ro" in url:
            tag = soup.find("meta", property="product:price:amount")
            if tag: p_cu_tva = extract_clean_price(tag["content"])
        
        elif "king.ro" in url:
            # King.ro afișează prețurile în span-uri cu clase de preț
            final = soup.select_one(".price-final_price .price, span[data-price-type='finalPrice'] .price")
            base = soup.select_one(".price-including-tax .price, span[data-price-type='basePrice'] .price")
            if final: p_cu_tva = extract_clean_price(final.text)
            if base: p_fara_tva = extract_clean_price(base.text)
            # Dacă ambele sunt la fel, înseamnă că am citit greșit, King le separă clar
            if p_cu_tva == p_fara_tva: p_fara_tva = round(p_cu_tva / 1.19, 2) if p_cu_tva else None

        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".summary .price .woocommerce-Price-amount, .price bdi")
            if tag: p_cu_tva = extract_clean_price(tag.text)

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            if tag: p_cu_tva = extract_clean_price(tag.text)

        # Fallback: dacă nu am găsit nimic, calculăm automat TVA pentru afișare
        if p_cu_tva and not p_fara_tva:
            p_fara_tva = round(p_cu_tva / 1.19, 2)

        return p_cu_tva, p_fara_tva, "Succes"
    except Exception as e:
        return None, None, str(e)

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Analiză TVA")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🚀 Scanează Magazinele"):
        results = []
        errors = []
        bar = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Verificăm {s["Magazin"]}...'):
                tva_da, tva_nu, msg = get_wine_data_v6(s["URL"])
                if tva_da:
                    results.append({
                        "Magazin": s["Magazin"],
                        "Preț cu TVA": f"{tva_da} RON",
                        "Preț fără TVA": f"{tva_nu} RON" if tva_nu else "N/A",
                        "URL": s["URL"]
                    })
                else:
                    errors.append(f"{s['Magazin']}: {msg}")
                time.sleep(2)
            bar.progress((i + 1) / len(surse))

        if results:
            st.balloons()
            df = pd.DataFrame(results)
            st.table(df[["Magazin", "Preț cu TVA", "Preț fără TVA"]])
            
            for r in results:
                st.link_button(f"Mergi la {r['Magazin']}", r['URL'])
        else:
            st.error("Nu am găsit prețuri. Verifică log-urile de erori.")
            with st.expander("Erori tehnice"):
                for e in errors: st.write(e)
