import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# 1. CONFIGURARE ȘI SECURITATE
st.set_page_config(page_title="Wine Watcher RO", page_icon="🍷")
PASSWORD = "CodulEsteVinul"

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acces Privat Crama")
        parola = st.text_input("Introdu parola pentru a vedea prețurile:", type="password")
        if st.button("Intră"):
            if parola == PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Parolă incorectă!")
        return False
    return True

# 2. MOTORUL DE SCRAPING (ADAPTIV)
def get_price(url, magazin):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")
        
        if "vinimondo" in url:
            price_raw = soup.find("meta", property="product:price:amount")["content"]
        elif "king.ro" in url:
            price_raw = soup.find("span", class_="price").text
        elif "crushwineshop" in url:
            price_raw = soup.find("span", class_="woocommerce-Price-amount").text
        elif "winemag" in url:
            price_raw = soup.find("span", class_="price-new").text
        else:
            price_raw = "0"

        # Curățare preț: eliminăm "lei", ",", și spațiile
        clean_price = "".join(filter(str.isdigit, price_raw.replace(',', '')))
        return int(clean_price) / 100 if len(clean_price) > 3 else int(clean_price)
    except:
        return None

# 3. INTERFAȚA UTILIZATOR
if check_password():
    st.title("🍷 Wine Watcher: Le Volte dell'Ornellaia")
    st.info("Aplicația verifică prețurile în timp real pe site-urile selectate.")

    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🔄 Actualizează Prețurile"):
        data = []
        with st.spinner('Se verifică ofertele...'):
            for s in surse:
                pret = get_price(s["URL"], s["Magazin"])
                data.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
        
        df = pd.DataFrame(data)
        df = df.sort_values(by="Preț (RON)", ascending=True)

        # Afișare Best Deal
        min_price = df["Preț (RON)"].min()
        best_shop = df[df["Preț (RON)"] == min_price]["Magazin"].values[0]
        
        st.metric(label="Cel mai bun preț azi", value=f"{min_price} RON", delta=f"la {best_shop}")

        # Tabel formatat
        st.write("### Comparație prețuri:")
        st.dataframe(df, use_container_width=True)
        
        for index, row in df.iterrows():
            st.link_button(f"Cumpără de la {row['Magazin']} - {row['Preț (RON)']} RON", row['Link'])