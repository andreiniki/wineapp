import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
from googlesearch import search

# 1. CONFIGURARE
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

# 2. MOTORUL DE EXTRARE (Logica ta îmbunătățită)
def get_price_flexible(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Încercăm întâi meta-tag-urile standard (comune la magazinele mari)
        meta = soup.find("meta", property="product:price:amount")
        if meta:
            return float(meta["content"].replace(',', '.'))

        # Strategia de urgență: Căutăm tiparul de preț în textul paginii
        page_text = soup.get_text()
        # Regex pentru prețuri tip 120,74 sau 125.00 urmate de lei/ron
        match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', page_text, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', '.'))
            if val > 2000: val /= 100
            return val
            
        return None
    except:
        return None

# 3. INTERFAȚA
if check_password():
    st.title("🍷 Wine Watcher: Căutare Națională")
    produs_cautat = st.text_input("Produs de căutat:", value="Le Volte dell'Ornellaia 0.75L")
    
    if st.button("🚀 Scanează tot internetul (RO)"):
        rezultate = []
        # Căutăm pe Google primele 10-15 rezultate din magazine românești
        query = f'"{produs_cautat}" site:.ro store OR pret OR cumpara'
        
        with st.status("Google indexează magazinele...", expanded=True) as status:
            # Preluăm link-urile de la Google
            links = [j for j in search(query, num=15, stop=15, pause=2)]
            
            for i, link in enumerate(links):
                # Filtrăm site-urile care nu sunt magazine (ex: bloguri, stiri)
                if any(x in link for x in ["stiri", "forum", "facebook", "youtube", "emag"]): # eMag e greu de scanat direct
                    continue
                
                status.write(f"Analizăm magazinul: {link.split('/')[2]}...")
                pret = get_price_flexible(link)
                
                if pret and 80 < pret < 300: # Filtru de siguranță pentru 0.75L
                    nume_magazin = link.split('/')[2].replace('www.', '')
                    rezultate.append({"Magazin": nume_magazin, "Preț (RON)": pret, "Link": link})
                
                time.sleep(1) # Evităm blocajele
            
            status.update(label="Căutare finalizată!", state="complete")

        if rezultate:
            df = pd.DataFrame(rezultate).sort_values(by="Preț (RON)")
            st.balloons()
            st.metric("Cea mai bună ofertă găsită", f"{df.iloc[0]['Preț (RON)']} RON")
            st.table(df[["Magazin", "Preț (RON)"]])
            
            for _, row in df.iterrows():
                st.link_button(f"🛒 Mergi la {row['Magazin']}", row['Link'])
        else:
            st.warning("Nu am găsit prețuri valide. Reîncearcă sau verifică termenii de căutare.")

    st.divider()
    st.caption("Acest mod folosește Google pentru a descoperi noi magazine automat.")
