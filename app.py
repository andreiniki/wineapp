import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import urllib.parse

# 1. CONFIGURARE & SECURITATE
st.set_page_config(page_title="Wine Watcher Universal", page_icon="🍷")
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

# 2. MOTORUL DE EXTRARE UNIVERSAL
def get_price_flexible(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Căutăm meta-tag-ul standard de preț
        meta = soup.find("meta", property="product:price:amount")
        if meta: return float(meta["content"].replace(',', '.'))

        # Backup: Căutăm tiparul de preț în textul paginii (ex: 125,00 lei)
        match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', soup.get_text(), re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', '.'))
            return val if val < 2000 else val / 100
        return None
    except:
        return None

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Căutare Națională")
    produs = "Le Volte dell'Ornellaia 0.75"
    
    if st.button("🚀 Scanează Magazine Noi"):
        rezultate = []
        # Căutăm magazine românești prin DuckDuckGo (nu cere librării noi)
        search_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(produs + ' pret ron')}"
        
        with st.status("Căutăm magazine disponibile...", expanded=True) as status:
            scraper = cloudscraper.create_scraper()
            search_res = scraper.get(search_url)
            search_soup = BeautifulSoup(search_res.content, "html.parser")
            
            # Extragem link-urile din rezultatele căutării
            links = []
            for a in search_soup.find_all('a', class_='result__a', href=True):
                url = a['href']
                if ".ro" in url and not any(x in url for x in ["emag", "vivino", "olx", "facebook"]):
                    links.append(url)

            # Scanăm fiecare link găsit
            for link in list(set(links))[:10]: # Primele 10 magazine unice
                nume = link.split('/')[2].replace('www.', '')
                status.write(f"Verificăm {nume}...")
                pret = get_price_flexible(link)
                
                if pret and 90 < pret < 250:
                    rezultate.append({"Magazin": nume, "Preț (RON)": pret, "Link": link})
                time.sleep(1)
            
            status.update(label="Căutare finalizată!", state="complete")

        if rezultate:
            df = pd.DataFrame(rezultate).sort_values(by="Preț (RON)")
            st.balloons()
            st.table(df[["Magazin", "Preț (RON)"]])
            for _, row in df.iterrows():
                st.link_button(f"🛒 Mergi la {row['Magazin']}", row['Link'])
        else:
            st.warning("Nu am găsit prețuri noi. Reîncearcă în câteva minute.")
