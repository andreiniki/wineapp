import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
from googlesearch import search

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

# 2. MOTORUL DE EXTRARE (Logica ta stabilă din V3)
def get_price_flexible(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=15)
        if res.status_code != 200: return None
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Prioritate 1: Meta tag (Cel mai precis)
        meta = soup.find("meta", property="product:price:amount")
        if meta: return float(meta["content"].replace(',', '.'))

        # Prioritate 2: King.ro specific
        if "king.ro" in url:
            tag = soup.find("span", {"data-price-type": "finalPrice"})
            if tag: return float(re.sub(r'[^\d.]', '', tag.text.replace(',', '.')))

        # Prioritate 3: Căutare text (Universal)
        page_text = soup.get_text()
        match = re.search(r'(\d{2,3}[\.,]\d{2})\s?(?:lei|RON)', page_text, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', '.'))
            return val if val < 2000 else val / 100
        return None
    except:
        return None

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Scrutin Național")
    produs_cautat = st.text_input("Ce vin căutăm astăzi?", value="Le Volte dell'Ornellaia 0.75L")
    
    if st.button("🚀 Scanează Magazinele din România"):
        rezultate = []
        # Query specific pentru a forța rezultate din magazine RO
        query = f'"{produs_cautat}" pret lei site:.ro'
        
        with st.status("Google caută magazinele...", expanded=True) as status:
            # SINTAXĂ NOUĂ: search(query, sleep_interval=2)
            # Extragem link-urile unul câte unul pentru a evita TypeError
            try:
                search_results = search(query, sleep_interval=2)
                links_count = 0
                
                for link in search_results:
                    if links_count >= 12: break # Limităm la 12 magazine pentru viteză
                    
                    # Filtrăm site-urile care nu sunt magazine directe
                    if any(x in link for x in ["stiri", "forum", "facebook", "emag", "vivino"]):
                        continue
                    
                    nume_magazin = link.split('/')[2].replace('www.', '')
                    status.write(f"🔎 Verificăm prețul pe: **{nume_magazin}**")
                    
                    pret = get_price_flexible(link)
                    if pret and 90 < pret < 350: # Filtru de siguranță
                        rezultate.append({"Magazin": nume_magazin, "Preț (RON)": pret, "Link": link})
                        links_count += 1
                    
                    time.sleep(1) # Pauză anti-blocaj
            except Exception as e:
                st.error(f"Eroare la căutare: {e}")

        if rezultate:
            df = pd.DataFrame(rezultate).sort_values(by="Preț (RON)").drop_duplicates(subset=['Magazin'])
            st.balloons()
            st.subheader(f"Cele mai bune oferte pentru: {produs_cautat}")
            st.table(df[["Magazin", "Preț (RON)"]])
            
            for _, row in df.iterrows():
                st.link_button(f"🛒 Mergi la {row['Magazin']} ({row['Preț (RON)']} RON)", row['Link'])
        else:
            st.warning("Nu am găsit prețuri valide. Site-urile ar putea bloca accesul automatizat.")
