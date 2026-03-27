import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# 1. CONFIGURARE & SECURITATE (Păstrăm ce a mers în V3)
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

# 2. MOTORUL DE SCRAPING V3 (ORIGINALUL CARE MERGE)
def get_price_v3_core(url, site_name):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, None, f"Eroare Server ({res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        text_pret = ""
        full_name = ""

        # Identificăm numele produsului și prețul (Logica V3)
        if "vinimondo.ro" in url:
            meta = soup.find("meta", property="product:price:amount")
            text_pret = meta["content"] if meta else ""
        elif "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            text_pret = tag.text if tag else ""
        elif "crushwineshop.ro" in url:
            tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
            text_pret = tag.text if tag else ""
        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            text_pret = tag.text if tag else ""

        # Fallback Regex (Inima stabilității V3)
        if not text_pret:
            page_text = soup.get_text()
            match = re.search(r'(\d{2,4}[\.,]\d{2})\s?(?:lei|RON)', page_text, re.IGNORECASE)
            if match:
                text_pret = match.group(1)

        if text_pret:
            clean_digits = text_pret.replace(',', '.').replace(' ', '')
            numere = re.findall(r"[-+]?\d*\.\d+|\d+", clean_digits)
            if numere:
                valoare = float(numere[0])
                if valoare > 3000: valoare = valoare / 100 
                
                # Extragem ANUL și FORMATUL din titlu sau text
                year_match = re.search(r'\b(19|20)\d{2}\b', soup.get_text())
                year = year_match.group(0) if year_match else "N/A"
                
                fmt = "0.75L"
                txt_low = soup.get_text().lower()
                if "1.5" in txt_low or "magnum" in txt_low: fmt = "1.5L"
                elif "3l" in txt_low or "double" in txt_low: fmt = "3L"
                
                return valoare, {"an": year, "format": fmt}, "Succes"
                
        return None, None, "Nu am putut citi prețul"
    except Exception as e:
        return None, None, f"Eroare: {str(e)[:30]}"

# 3. INTERFAȚA
if check_password():
    st.title("🍷 Wine Watcher: Monitorizare V3 Robust")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
        {"Magazin": "AlcoolScont", "URL": "https://www.alcoolscont.ro/vin-rosu-le-volte-dell-ornellaia-0-75l.html"}
    ]

    if st.button("🔄 Verifică Toate Prețurile"):
        rezultate = []
        bara = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Analizăm {s["Magazin"]}...'):
                pret, meta, msg = get_price_v3_core(s["URL"], s["Magazin"])
                if pret:
                    rezultate.append({
                        "Magazin": s["Magazin"], 
                        "An": meta["an"],
                        "Format": meta["format"],
                        "Preț (RON)": pret, 
                        "Link": s["URL"]
                    })
                time.sleep(2)
            bara.progress((i + 1) / len(surse))
        
        if rezultate:
            df = pd.DataFrame(rezultate)
            
            # Afișare pe categorii de format, așa cum ai cerut
            for format_grup in df["Format"].unique():
                st.subheader(f"📦 Format: {format_grup}")
                sub_df = df[df["Format"] == format_grup].sort_values("Preț (RON)")
                st.table(sub_df[["An", "Magazin", "Preț (RON)"]])
                
                for _, row in sub_df.iterrows():
                    st.link_button(f"🛒 {row['Magazin']} ({row['An']})", row['Link'])
        else:
            st.error("Nu am găsit prețuri. Verifică manual dacă link-urile mai sunt valide.")

    st.divider()
    st.caption("Această versiune folosește exclusiv motorul V3 care a confirmat succesul.")
