import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import time
import re
import json
import os
from datetime import datetime

try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(page_title="Wine Watcher RO", page_icon="🍷", layout="wide")

HISTORY_FILE = "price_history.json"
WINES_FILE = "wines.json"

def clean_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d.,]', '', str(text)).replace(',', '.')
    match = re.search(r'(\d+\.\d+|\d+)', digits)
    if match:
        val = float(match.group(1))
        if val > 5000:
            val /= 100
        return round(val, 2)
    return None

SCRAPERS = {}

def scraper(domain):
    def decorator(fn):
        SCRAPERS[domain] = fn
        return fn
    return decorator

@scraper("vinimondo.ro")
def scrape_vinimondo(soup, url):
    tag = soup.find("meta", property="product:price:amount")
    if tag:
        return clean_price(tag["content"])
    tag = soup.select_one(".woocommerce-Price-amount bdi, .price bdi")
    return clean_price(tag.text) if tag else None

@scraper("king.ro")
def scrape_king(soup, url):
    for sel in [
        'span[data-price-type="finalPrice"] .price',
        ".price-final_price .price",
        ".price-wrapper .price",
        ".product-info-main .price",
    ]:
        tag = soup.select_one(sel)
        if tag:
            return clean_price(tag.text)
    return None

@scraper("crushwineshop.ro")
def scrape_crush(soup, url):
    for sel in [".woocommerce-Price-amount bdi", ".woocommerce-Price-amount", ".price ins bdi"]:
        tag = soup.select_one(sel)
        if tag:
            return clean_price(tag.text)
    return None

@scraper("winemag.ro")
def scrape_winemag(soup, url):
    for sel in [".price-new", ".price ins .amount", ".woocommerce-Price-amount bdi", ".price"]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.text)
            if p:
                return p
    return None

@scraper("vinoteca.ro")
def scrape_vinoteca(soup, url):
    for sel in [
        ".woocommerce-Price-amount bdi",
        ".price ins .woocommerce-Price-amount bdi",
        ".woocommerce-Price-amount",
    ]:
        tag = soup.select_one(sel)
        if tag:
            return clean_price(tag.text)
    return None

@scraper("winexpert.ro")
def scrape_winexpert(soup, url):
    for sel in [".woocommerce-Price-amount bdi", ".price", ".product-price"]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.text)
            if p:
                return p
    return None

@scraper("spiritshop.ro")
def scrape_spiritshop(soup, url):
    for sel in [".woocommerce-Price-amount bdi", ".price"]:
        tag = soup.select_one(sel)
        if tag:
            return clean_price(tag.text)
    return None

@scraper("wineshop.ro")
def scrape_wineshop(soup, url):
    for sel in [".price-new", "#product-price .price", ".price"]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.text)
            if p:
                return p
    return None

@scraper("cramelerecas.ro")
def scrape_recas(soup, url):
    for sel in [".woocommerce-Price-amount bdi", ".price", ".product-price"]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.text)
            if p:
                return p
    return None

def get_wine_price(url, debug=False):
    scraper_client = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    try:
        res = scraper_client.get(url, timeout=20)
        if debug:
            st.caption(f"HTTP {res.status_code} — {url}")
        if res.status_code != 200:
            return None, f"HTTP {res.status_code}"
        soup = BeautifulSoup(res.content, "html.parser")
        title = soup.title.string if soup.title else ""
        if any(x in title.lower() for x in ["404", "not found", "pagina negasita", "eroare"]):
            return None, f"Pagina inexistenta ({title[:40]})"
        for domain, fn in SCRAPERS.items():
            if domain in url:
                price = fn(soup, url)
                if debug and price is None:
                    st.caption(f"  Selector negasit pentru {domain}")
                return price, None
        for sel in [
            ".woocommerce-Price-amount bdi",
            ".price-new",
            ".price ins .amount",
            "[itemprop='price']",
            ".product-price",
        ]:
            tag = soup.select_one(sel)
            if tag:
                price = clean_price(tag.get("content") or tag.text)
                if price:
                    return price, None
        return None, "Selector pret negasit"
    except Exception as e:
        return None, str(e)[:60]

def load_wines():
    if os.path.exists(WINES_FILE):
        with open(WINES_FILE) as f:
            return json.load(f)
    default = [
        {
            "name": "Le Volte dell'Ornellaia",
            "sources": [
                {"store": "Vinimondo", "url": "https://vinimondo.ro/le-volte-dellornellaia-2023-toscana-igt-ornellaia-ro"},
                {"store": "King.ro", "url": "https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html"},
                {"store": "WineMag", "url": "https://www.winemag.ro/le-volte-dell-ornellaia-2021-0-75l"},
                {"store": "Crush Wine Shop", "url": "https://www.crushwineshop.ro/le-volte-dell-ornellaia-2023-igp-toscana-rosso-p1435"},
            ]
        }
    ]
    save_wines(default)
    return default

def save_wines(wines):
    with open(WINES_FILE, "w") as f:
        json.dump(wines, f, indent=2, ensure_ascii=False)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def record_prices(wine_name, results):
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    if wine_name not in history:
        history[wine_name] = []
    for r in results:
        history[wine_name].append({
            "date": today,
            "store": r["Magazin"],
            "price": r["Pret (RON)"]
        })
    save_history(history)

st.title("🍷 Wine Watcher RO")
st.caption("Urmareste preturile vinurilor pe site-urile romanesti")

wines = load_wines()
wine_names = [w["name"] for w in wines]

with st.sidebar:
    st.header("🍾 Vinuri urmarite")
    selected_wine_name = st.selectbox("Selecteaza vin", wine_names)

    st.divider()
    st.subheader("Adauga vin nou")
    with st.form("add_wine"):
        new_name = st.text_input("Nume vin")
        new_url = st.text_input("URL produs (primul magazin)")
        new_store = st.text_input("Nume magazin")
        submitted = st.form_submit_button("Adauga")
        if submitted and new_name and new_url and new_store:
            existing = next((w for w in wines if w["name"].lower() == new_name.lower()), None)
            if existing:
                existing["sources"].append({"store": new_store, "url": new_url})
            else:
                wines.append({"name": new_name, "sources": [{"store": new_store, "url": new_url}]})
            save_wines(wines)
            st.success(f"Adaugat: {new_name}")
            st.rerun()

    st.divider()
    st.subheader("Adauga magazin la vin existent")
    with st.form("add_source"):
        target_wine = st.selectbox("Vin", wine_names, key="target")
        extra_store = st.text_input("Magazin")
        extra_url = st.text_input("URL")
        sub2 = st.form_submit_button("Adauga magazin")
        if sub2 and extra_store and extra_url:
            wine_obj = next(w for w in wines if w["name"] == target_wine)
            wine_obj["sources"].append({"store": extra_store, "url": extra_url})
            save_wines(wines)
            st.success("Magazin adaugat!")
            st.rerun()

selected_wine = next(w for w in wines if w["name"] == selected_wine_name)

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader(f"📍 {selected_wine_name}")
with col2:
    fetch = st.button("🔄 Actualizeaza preturile", use_container_width=True)

debug_mode = st.toggle("🔍 Mod debug (arata erori per site)", value=False)

if fetch:
    results = []
    errors = []
    progress = st.progress(0)
    sources = selected_wine["sources"]
    status_box = st.empty()
    for i, s in enumerate(sources):
        status_box.info(f"Verificam {s['store']}... ({i+1}/{len(sources)})")
        price, err = get_wine_price(s["url"], debug=debug_mode)
        if price:
            results.append({"Magazin": s["store"], "Pret (RON)": price, "Link": s["url"]})
        else:
            errors.append({"Magazin": s["store"], "Eroare": err or "Pret negasit"})
        time.sleep(1.5)
        progress.progress((i + 1) / len(sources))
    status_box.empty()
    progress.empty()

    if results:
        record_prices(selected_wine_name, results)
        st.session_state[f"results_{selected_wine_name}"] = results
        st.session_state[f"errors_{selected_wine_name}"] = errors
        st.success(f"Preturi actualizate la {datetime.now().strftime('%H:%M, %d %b %Y')}")
    else:
        st.error("Nu am putut prelua preturile de la niciun magazin.")

    if errors and (debug_mode or not results):
        with st.expander("Detalii erori per magazin", expanded=not results):
            for e in errors:
                st.write(f"❌ **{e['Magazin']}**: {e['Eroare']}")

results = st.session_state.get(f"results_{selected_wine_name}", [])
errors = st.session_state.get(f"errors_{selected_wine_name}", [])
if results:
    df = pd.DataFrame(results).sort_values("Pret (RON)")
    best = df.iloc[0]
    st.success(f"🏆 Cel mai ieftin: **{best['Magazin']}** — **{best['Pret (RON)']} RON**")

    col_a, col_b = st.columns(2)
    with col_a:
        st.dataframe(
            df[["Magazin", "Pret (RON)"]].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
        if errors:
            with st.expander(f"⚠️ {len(errors)} magazin(e) fara pret"):
                for e in errors:
                    st.write(f"❌ **{e['Magazin']}**: {e['Eroare']}")
    with col_b:
        if HAS_PLOTLY:
            fig = px.bar(
                df, x="Magazin", y="Pret (RON)",
                color="Pret (RON)", color_continuous_scale="reds_r",
                title="Comparatie preturi"
            )
            fig.update_layout(coloraxis_showscale=False, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🛒 Cumpara direct")
    cols = st.columns(len(results))
    for col, r in zip(cols, results):
        col.link_button(f"{r['Magazin']}\n{r['Pret (RON)']} RON", r["Link"], use_container_width=True)

st.divider()
st.subheader("📈 Istoric preturi")
history = load_history()
wine_hist = history.get(selected_wine_name, [])
if wine_hist:
    hist_df = pd.DataFrame(wine_hist)
    hist_df["date"] = pd.to_datetime(hist_df["date"])
    if HAS_PLOTLY:
        fig2 = px.line(
            hist_df, x="date", y="price", color="store",
            title=f"Evolutie preturi - {selected_wine_name}",
            labels={"date": "Data", "price": "Pret (RON)", "store": "Magazin"}
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.dataframe(hist_df, use_container_width=True)
    if st.button("🗑️ Sterge istoricul pentru acest vin"):
        history.pop(selected_wine_name, None)
        save_history(history)
        st.rerun()
else:
    st.info("Niciun istoric disponibil. Apasa 'Actualizeaza preturile' pentru a incepe colectarea.")
