import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import json
import time
import re

# 1. CONFIGURARE
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

# 2. MOTORUL DE EXTRACȚIE JSON (MULT MAI STABIL)
def get_wine_data_v8(url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    try:
        res = scraper.get(url, timeout=25)
        if res.status_code != 200:
            return None, None, f"Blocat de site (Cod {res.status_code})"
            
        soup = BeautifulSoup(res.content, "html.parser")
        p_cu_tva = None
        
        # Strategie: Căutăm scripturi de tip ld+json (date structurate)
        json_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                # Unele site-uri pun datele într-o listă, altele direct în obiect
                items = data if isinstance(data, list) else [data]
                for item in items:
                    # Căutăm entitatea de tip "Product" sau "Offer"
                    if "@type" in item and item["@type"] == "Product":
                        if "offers" in item:
                            offers = item["offers"]
                            if isinstance(offers, list):
                                p_cu_tva = float(offers[0].get("price", 0))
                            else:
                                p_cu_tva = float(offers.get("price", 0))
                            break
            except:
                continue

        # Dacă JSON-ul a eșuat, fallback pe selectori simpli
        if not p_cu_tva or p_cu_tva == 0:
            tag = soup.select_one('[property="product:price:amount"], .price, .price-new')
            if tag:
                text = tag.get("content") if tag.has_attr("content") else tag.text
                digits = re.sub(r'[^\d.,]', '', text).replace(',', '.')
                match = re.search(r"(\d+\.\d+|\d+)", digits)
                if match: p_cu_tva = float(match.group(1))

        if p_cu_tva and p_cu_tva > 0:
            if p_cu_tva > 5000: p_cu_tva /= 100
            p_fara_tva = round(p_cu_tva / 1.21, 2)
            return round(p_cu_tva, 2), p_fara_tva, "Succes"
            
        return None, None, "Preț invizibil pentru robot"
    except Exception as e:
        return None, None, f"Eroare: {str(e)[:25]}"

# 3. INTERFAȚĂ
if check_password():
    st.title("🍷 Wine Watcher: Ornellaia")
    st.markdown("---")
    
    surse = [
        {"Magazin": "Vinimondo", "URL": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
        {"Magazin": "King.ro", "URL": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
        {"Magazin": "Crush Wine Shop", "URL": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
        {"Magazin": "WineMag", "URL": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"}
    ]

    if st.button("🔍 Verifică prețurile acum"):
        results = []
        errors = []
        
        for s in surse:
            with st.status(f"Se analizează {s['Magazin']}...", expanded=False) as status:
                p_tva, p_fara, msg = get_wine_data_v8(s["URL"])
                if p_tva:
                    results.append({
                        "Magazin": s["Magazin"],
                        "Preț cu TVA (21%)": f"{p_tva:.2f} RON",
                        "Preț fără TVA": f"{p_fara:.2f} RON",
                        "URL": s["URL"]
                    })
                    status.update(label=f"✅ {s['Magazin']}: Găsit!", state="complete")
                else:
                    errors.append(f"{s['Magazin']}: {msg}")
                    status.update(label=f"❌ {s['Magazin']}: Eșuat", state="error")
                time.sleep(3) # Pauză strategică

        if results:
            st.balloons()
            df = pd.DataFrame(results)
            st.subheader("📊 Rezultate Găsite")
            st.table(df[["Magazin", "Preț cu TVA (21%)", "Preț fără TVA"]])
            
            cols = st.columns(len(results))
            for idx, r in enumerate(results):
                cols[idx].link_button(f"🛒 {r['Magazin']}", r['URL'])
        
        if errors:
            with st.expander("📝 Jurnal de scanare (Erori)"):
                for e in errors: st.write(e)

    st.info("💡 Sfat: Dacă toate site-urile dau 'Eșuat', înseamnă că serverul a fost blocat temporar. Încearcă din nou peste 10 minute.")
