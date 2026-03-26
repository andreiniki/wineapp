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
    # Păstrăm doar cifrele, virgula și punctul
    clean = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    # Căutăm prima secvență de cifre care poate avea un punct în ea
    match = re.search(r"(\d+\.\d+|\d+)", clean)
    if match:
        val = float(match.group(1))
        # Dacă numărul e prea mare (ex: 12500 în loc de 125.00), îl corectăm
        if val > 5000: val /= 100
        return round(val, 2)
    return None

# 2. MOTORUL DE CĂUTARE
def get_wine_data_v7(url):
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
            # Selectori multipli pentru King.ro (sunt foarte dinamici)
            final = soup.select_one('span[data-price-type="finalPrice"] .price, .price-final_price .price')
            base = soup.select_one('span[data-price-type="basePrice"] .price, .price-excluding-tax .price')
            if final: p_cu_tva = extract_clean_price(final.text)
            if base: p_fara_tva = extract_clean_price(base.text)

        elif "crushwineshop.ro" in url:
            tag = soup.select_one(".summary .price .woocommerce-Price-amount, .price bdi, .amount")
            if tag: p_cu_tva = extract_clean_price(tag.text)

        elif "winemag.ro" in url:
            tag = soup.select_one(".price-new, .price")
            if tag: p_cu_tva = extract_clean_price(tag.text)

        # CALCULE TVA (Cota 21%)
        if p_cu_tva and not p_fara_tva:
            p_fara_tva = round(p_cu_tva / 1.21, 2)
        elif p_fara_tva and not p_cu_tva:
            p_cu_tva = round(p_fara_tva * 1.21, 2)

        if p_cu_tva:
            return p_cu_tva, p_fara_tva, "Succes"
        return None, None, "Preț negăsit în structura paginii"
    except Exception as e:
        return None, None, f"Eroare: {str(e)[:30]}"

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Ornellaia (TVA 21%)")
    
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
            with st.spinner(f'Analizăm {s["Magazin"]}...'):
                tva_da, tva_nu, msg = get_wine_data_v7(s["URL"])
                if tva_da:
                    results.append({
                        "Magazin": s["Magazin"],
                        "Preț cu TVA (21%)": f"{tva_da:.2f} RON",
                        "Preț fără TVA": f"{tva_nu:.2f} RON" if tva_nu else "N/A",
                        "URL": s["URL"]
                    })
                else:
                    errors.append(f"{s['Magazin']}: {msg}")
                time.sleep(2.5) # O pauză puțin mai mare pentru siguranță
            bar.progress((i + 1) / len(surse))

        if results:
            st.balloons()
            df = pd.DataFrame(results)
            st.table(df[["Magazin", "Preț cu TVA (21%)", "Preț fără TVA"]])
            
            for r in results:
                st.link_button(f"Mergi la {r['Magazin']}", r['URL'])
        
        if errors:
            with st.expander("🔍 Detalii erori / Debug"):
                for e in errors: st.write(e)
