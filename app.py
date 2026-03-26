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
    # Simulăm un browser real pentru a evita blocarea
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return None
            
        soup = BeautifulSoup(res.content, "html.parser")
        price_text = ""

        if "vinimondo" in url:
            tag = soup.find("meta", property="product:price:amount")
            price_text = tag["content"] if tag else ""
        elif "king.ro" in url:
            tag = soup.find("span", class_="price")
            price_text = tag.text if tag else ""
        elif "crushwineshop" in url:
            tag = soup.find("span", class_="woocommerce-Price-amount")
            price_text = tag.text if tag else ""
        elif "winemag" in url:
            tag = soup.find("span", class_="price-new")
            price_text = tag.text if tag else ""

        if price_text:
            # Curățăm textul de "lei", ",", simboluri și păstrăm doar cifrele și punctul
            clean_price = "".join(c for c in price_text.replace(',', '.') if c.isdigit() or c == '.')
            return float(clean_price)
        return None
    except Exception:
        return None

# 3. INTERFAȚA UTILIZATOR
if check_password():
    st.title("🍷 Wine Watcher: Le Volte dell'Ornellaia")
    st.info("Apasă butonul de mai jos pentru a verifica prețurile actuale.")

    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🔄 Actualizează Prețurile"):
        data = []
        progress_bar = st.progress(0)
        
        for i, s in enumerate(surse):
            with st.spinner(f'Verificăm {s["Magazin"]}...'):
                pret = get_price(s["URL"], s["Magazin"])
                if pret:
                    data.append({"Magazin": s["Magazin"], "Preț (RON)": pret, "Link": s["URL"]})
            progress_bar.progress((i + 1) / len(surse))
        
        if data:
            df = pd.DataFrame(data)
            df = df.sort_values(by="Preț (RON)", ascending=True)

            # Highlight pentru cea mai bună ofertă
            min_price = df["Preț (RON)"].min()
            best_shop = df[df["Preț (RON)"] == min_price]["Magazin"].values[0]
            
            st.balloons()
            st.metric(label="Cea mai bună ofertă", value=f"{min_price} RON", delta=f"la {best_shop}")

            st.write("### Lista completă:")
            st.table(df[["Magazin", "Preț (RON)"]])
            
            for index, row in df.iterrows():
                st.link_button(f"👉 Mergi la {row['Magazin']} ({row['Preț (RON)']} RON)", row['Link'])
        else:
            st.error("⚠️ Nu am putut prelua prețurile. Site-urile pot fi temporar indisponibile pentru vizite automate.")

    st.divider()
    st.caption("Notă: Prețurile sunt preluate în timp real. Unele site-uri pot bloca accesul temporar.")
