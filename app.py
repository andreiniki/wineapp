import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# 1. CONFIGURARE & SECURITATE (Păstrăm ce a mers)
st.set_page_config(page_title="Wine Watcher: Corecții", page_icon="🍷", layout="wide")
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

# 2. MOTORUL DE EXTRACȚIE V3 CU LOGICĂ DE PREȚ BRUT
def get_wine_data_v3_beta(url, scraper, query):
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, None, f"Eroare Server ({res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        text_pret = ""
        full_name = ""

        # A. Extracție Nume Complet (din H1)
        h1_tag = soup.find("h1")
        full_name = h1_tag.get_text().strip() if h1_tag else query

        # B. EXTRACȚIE PREȚ - Strategia 1 (Selectori Specifici V3 Fix)
        if "vinimondo.ro" in url:
            meta = soup.find("meta", property="product:price:amount")
            text_pret = meta["content"] if meta else ""
        elif "king.ro" in url:
            # FIX PENTRU KING: Luăm exact tag-ul de finalPrice
            tag = soup.select_one('span[data-price-type="finalPrice"] .price')
            text_pret = tag.get_text() if tag else ""
        elif "crushwineshop.ro" in url:
            tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
            text_pret = tag.get_text() if tag else ""
        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            text_pret = tag.text if tag else ""

        # C. EXTRACȚIE PREȚ - Strategia 2 (Fallback Brut: Lei, ron, RON)
        if not text_pret:
            # Preluăm tot textul din pagină și curățăm scripturile
            for script in soup(["script", "style"]): script.decompose()
            page_text = soup.get_text(separator=' ')
            
            # Regex inteligent care caută cifre lângă valută sau invers
            price_match = re.search(r'(\d+[\.,]\d{2})\s?(?:lei|RON|ron)', page_text, re.IGNORECASE)
            if price_match:
                text_pret = price_match.group(1)

        # D. CURĂȚARE ȘI VALIDARE PREȚ
        if text_pret:
            # Păstrăm doar cifrele și punctul zecimal
            clean = re.sub(r'[^\d.]', '', text_pret.replace(',', '.'))
            nums = re.findall(r"\d+\.\d+|\d+", clean)
            if nums:
                valoare = float(nums[0])
                # Corecție pentru formatele tip 12500 (fără punct)
                if valoare > 1000: valoare = valoare / 100
                
                # --- PARSARE AN ȘI FORMAT (NOU ȘI INTELIGENT) ---
                name_low = full_name.lower()
                
                # Căutăm ANUL
                year_match = re.search(r'\b(19|20)\d{2}\b', full_name)
                year = year_match.group(0) if year_match else "N/A"
                
                # Căutăm FORMATUL
                fmt = "0.75L"
                if any(x in name_low for x in ["magnum", "1.5l", "1.5 l"]): fmt = "1.5L (Magnum)"
                elif any(x in name_low for x in ["3l", "3 l", "double"]): fmt = "3L"
                elif any(x in name_low for x in ["0.375", "375ml"]): fmt = "0.375L"
                # Dacă prețul e suspect de mic pentru Magnum, e probabil 0.75L (Fix Winemag)
                elif valoare < 150 and fmt == "1.5L (Magnum)" and "magnum" not in name_low:
                     fmt = "0.75L"
                
                return valoare, {"an": year, "format": fmt, "nume_complet": full_name}, "Succes"
                
        return None, None, "Nu am putut citi prețul"
    except Exception as e:
        return None, None, f"Eroare tehnică: {str(e)[:30]}"

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Monitorizare V3 (Corecție & Brut)")
    query = st.text_input("Ce vin verificăm? (ex: Rosa dei Frati):", "Rosa dei Frati")
    
    # LISTA TA DE LINK-URI DIRECTE (Asigurăm acuratețea)
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/ca-dei-frati-rosa-dei-frati-riviera-del-garda-classico-doc-ca-dei-frati-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/ca-dei-frati-rosa-dei-frati-0-75l"},
        {"Magazin": "FineStore", "URL": "https://www.finestore.ro/ornellaia-le-volte-dellornellaia-075l"}
    ]

    if st.button("🔄 Verifică Toate Prețurile"):
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
        rezultate = []
        bara = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Analizăm {s["Magazin"]}...'):
                pret, meta, msg = get_wine_data_v3_beta(s["URL"], scraper, query)
                if pret:
                    rezultate.append({
                        "Magazin": s["Magazin"], 
                        "Denumire Completă": meta["nume_complet"],
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
                # Filtrăm și sortăm pe ani
                fmt_df = df[df["Format"] == format_grup].sort_values("Preț (RON)")
                st.table(fmt_df[["An", "Magazin", "Preț (RON)", "Denumire Completă"]])
                
                # Butoane directe de cumpărare
                cols = st.columns(3)
                for j, row in fmt_df.reset_index().iterrows():
                    cols[j % 3].link_button(f"🛒 Cumpără de la {row['Magazin']} - {row['Preț (RON)']} RON", row['Link'], use_container_width=True)
        else:
            st.error("Nu am găsit prețuri valide. Site-urile pot fi protejate.")

    st.divider()
    st.caption("Notă: Dacă un preț nu apare, reîncearcă peste 1 minut. Această versiune include căutarea brută pentru RON/lei.")
