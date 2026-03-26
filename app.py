import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re

# 1. CONFIGURARE
st.set_page_config(page_title="Wine Watcher RO", page_icon="🍷")
PASSWORD = "CodulEsteVinul"

if "password_correct" not in st.session_state:
    st.title("🔐 Acces Privat Crama")
    parola = st.text_input("Introdu parola:", type="password")
    if st.button("Intră"):
        if parola == PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Parolă incorectă!")
    st.stop()

# 2. MOTORUL DE CĂUTARE (Calibrat 0.75L)
def get_price_v3(url):
    # Folosim un browser mai "uman" pentru a evita eroarea 403/Indisponibil
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            return None, f"Serverul a refuzat conexiunea (Cod {res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        text_pret = ""

        if "vinimondo.ro" in url:
            meta = soup.find("meta", property="product:price:amount")
            text_pret = meta["content"] if meta else ""
        
        elif "king.ro" in url:
            # Selectorul pentru 120.74 RON
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            text_pret = tag.text if tag else ""

        elif "crushwineshop.ro" in url:
            tag = soup.select_one("p.price ins span.woocommerce-Price-amount, p.price span.woocommerce-Price-amount")
            text_pret = tag.text if tag else ""

        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            text_pret = tag.text if tag else ""

        if text_pret:
            clean_digits = text_pret.replace(',', '.').replace(' ', '')
            numere = re.findall(r"\d+\.\d+|\d+", clean_digits)
            if numere:
                valoare = float(numere[0])
                if valoare > 2000: valoare /= 100
                return valoare, "Succes"
                
        return None, "Preț negăsit în pagină"
    except Exception as e:
        return None, "Timeout sau blocaj IP"

# 3. INTERFAȚĂ
st.title("🍷 Wine Watcher: Ornellaia 0.75L")

surse = [
    {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
    {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
    {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
    {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
]

if st.button("🚀 Verifică Prețurile Acum"):
    rezultate = []
    
    # Folosim containere pentru a vedea progresul în timp real
    status_container = st.container()
    
    for s in surse:
        with status_container:
            with st.status(f"Se verifică {s['Magazin']}...", expanded=True) as status:
                pret, msg = get_price_v3(s["URL"])
                if pret:
                    rezultate.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
                    status.update(label=f"✅ {s['Magazin']}: {pret} RON", state="complete")
                else:
                    status.update(label=f"❌ {s['Magazin']}: {msg}", state="error")
                time.sleep(3) # Pauză anti-blocaj

    if rezultate:
        st.divider()
        df = pd.DataFrame(rezultate).sort_values(by="Preț (RON)")
        st.subheader("📊 Rezultate Găsite")
        st.table(df[["Magazin", "Preț (RON)"]])
        
        for r in rezultate:
            st.link_button(f"🛒 {r['Magazin']} - {r['Preț (RON)']} RON", r['Link'])
    else:
        st.error("⚠️ Nu am putut prelua niciun preț. Cel mai probabil, adresa IP a fost blocată temporar de magazine.")
