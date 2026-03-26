import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time

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

# 2. MOTORUL DE SCRAPING AVANSAT
def get_price_v2(url):
    # Folosim cloudscraper pentru a trece de protectiile tip Cloudflare
    scraper = cloudscraper.create_scraper()
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200:
            return None, f"Eroare HTTP {res.status_code}"
            
        soup = BeautifulSoup(res.content, "html.parser")
        price_text = ""

        # Logica specifica pentru fiecare site
        if "vinimondo.ro" in url:
            tag = soup.find("meta", property="product:price:amount")
            price_text = tag["content"] if tag else ""
        elif "king.ro" in url:
            tag = soup.find("span", class_="price-wrapper")
            if not tag: tag = soup.select_one(".price")
            price_text = tag.text if tag else ""
        elif "crushwineshop.ro" in url:
            tag = soup.find("p", class_="price")
            price_text = tag.text if tag else ""
        elif "winemag.ro" in url:
            tag = soup.find("span", class_="price-new")
            price_text = tag.text if tag else ""

        if price_text:
            # Extragem doar cifrele
            digits = "".join(c for c in price_text if c.isdigit())
            if digits:
                # Daca pretul e de forma 12500 (pentru 125,00 lei)
                val = float(digits)
                return (val / 100 if val > 1000 else val), "Succes"
        return None, "Preț negăsit în pagină"
    except Exception as e:
        return None, str(e)

# 3. INTERFAȚA
if check_password():
    st.title("🍷 Wine Watcher: Le Volte dell'Ornellaia")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🔄 Verifică Prețurile Acum"):
        data = []
        status_info = []
        progress = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Căutăm pe {s["Magazin"]}...'):
                pret, msg = get_price_v2(s["URL"])
                status_info.append(f"{s['Magazin']}: {msg}")
                if pret:
                    data.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
                time.sleep(1) # Pauza mica sa nu parem roboti agresivi
            progress.progress((i + 1) / len(surse))
        
        if data:
            df = pd.DataFrame(data).sort_values(by="Preț (RON)")
            st.balloons()
            st.metric("Cel mai bun preț", f"{df.iloc[0]['Preț (RON)']} RON", f"la {df.iloc[0]['Magazin']}")
            st.table(df[["Magazin", "Preț (RON)"]])
        else:
            st.error("⚠️ Niciun preț nu a putut fi preluat.")
            with st.expander("Vezi detalii erori (Debug)"):
                for info in status_info:
                    st.write(info)

    st.divider()
    st.caption("Creat cu ❤️ pentru iubitorii de vin.")
