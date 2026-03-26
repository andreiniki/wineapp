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

# 2. MOTORUL DE SCRAPING - DETECȚIE FLEXIBILĂ
def get_price_v3(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, f"Eroare Server ({res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        text_pret = ""

        # Strategie pe site-uri
        if "vinimondo.ro" in url:
            # Căutăm în meta tag-uri (cele mai sigure)
            meta = soup.find("meta", property="product:price:amount")
            text_pret = meta["content"] if meta else ""
        
        elif "king.ro" in url:
            # King folosește atribute de date
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            text_pret = tag.text if tag else ""

        elif "crushwineshop.ro" in url:
            # Crush are prețul într-un tag bdi sau span
            tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
            text_pret = tag.text if tag else ""

        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            text_pret = tag.text if tag else ""

        # Dacă nu am găsit prin metodele de mai sus, căutăm orice număr mare urmat de "lei"
        if not text_pret:
            page_text = soup.get_text()
            match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', page_text, re.IGNORECASE)
            if match:
                text_pret = match.group(1)

        if text_pret:
            # Curățare: păstrăm doar cifrele și transformăm virgula în punct
            clean_digits = text_pret.replace(',', '.').replace(' ', '')
            numere = re.findall(r"[-+]?\d*\.\d+|\d+", clean_digits)
            if numere:
                valoare = float(numere[0])
                # Corecție pentru formatări ciudate (ex: 12500 în loc de 125)
                if valoare > 2000: valoare = valoare / 100
                return valoare, "Succes"
                
        return None, "Nu am putut citi prețul din pagină"
    except Exception as e:
        return None, f"Eroare tehnică: {str(e)[:50]}"

# 3. INTERFAȚA
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
                pret, msg = get_price_v3(s["URL"])
                if pret:
                    rezultate.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
                else:
                    erori.append(f"{s['Magazin']}: {msg}")
                time.sleep(2) # Pauză mai lungă pentru a fi "invizibili"
            bara.progress((i + 1) / len(surse))
        
        if rezultate:
            df = pd.DataFrame(rezultate).sort_values(by="Preț (RON)")
            st.balloons()
            
            # Metrică principală
            st.metric("Cea mai bună ofertă", f"{df.iloc[0]['Preț (RON)']} RON", f"la {df.iloc[0]['Magazin']}")
            
            # Afișare tabel curat
            st.write("### Clasament prețuri:")
            st.table(df[["Magazin", "Preț (RON)"]])
            
            # Butoane de cumpărare
            for _, row in df.iterrows():
                st.link_button(f"🛒 Cumpără de la {row['Magazin']} ({row['Preț (RON)']} RON)", row['Link'])
        
        if erori:
            with st.expander("⚠️ Detalii despre magazinele care nu au răspuns"):
                for e in erori:
                    st.write(e)
                    
    st.divider()
    st.caption("Notă: Dacă un preț nu apare, reîncearcă peste 1 minut. Site-urile protejate pot bloca cereri repetate.")
