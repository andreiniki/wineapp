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

# ── Site definitions ──────────────────────────────────────────────────────────
# search_url: {q} va fi inlocuit cu numele vinului
# result_sel: CSS selector pentru linkuri in pagina de rezultate
# platform: tip platforma pentru extractia pretului

SITES = [
    {"store": "King.ro",        "search_url": "https://king.ro/catalogsearch/result/?q={q}",              "result_sel": ".product-item-link, .product-item-name a", "platform": "magento"},
    {"store": "FineStore",      "search_url": "https://www.finestore.ro/?s={q}&post_type=product",        "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "Crush Wine Shop","search_url": "https://www.crushwineshop.ro/?s={q}&post_type=product",    "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "VinMagazin",     "search_url": "https://vinmagazin.ro/?s={q}&post_type=product",           "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "WineMag",        "search_url": "https://www.winemag.ro/?s={q}&post_type=product",          "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a, .product-name a", "platform": "woo"},
    {"store": "Vinimondo",      "search_url": "https://vinimondo.ro/?s={q}&post_type=product",            "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "Vinoteca",       "search_url": "https://vinoteca.ro/?s={q}&post_type=product",             "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "WinePoint",      "search_url": "https://www.winepoint.ro/?s={q}&post_type=product",        "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "Rewine",         "search_url": "https://www.rewine.ro/?s={q}&post_type=product",           "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "VinExpert",      "search_url": "https://www.vinexpert.ro/?s={q}&post_type=product",        "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "LoveWine",       "search_url": "https://www.lovewine.ro/?s={q}&post_type=product",         "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "VinRegal",       "search_url": "https://vinregal.ro/?s={q}&post_type=product",             "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a", "platform": "woo"},
    {"store": "VinMag",         "search_url": "https://www.vinmag.ro/?s={q}&post_type=product",           "result_sel": ".woocommerce-LoopProduct-link, h2.woocommerce-loop-product__title a, .product-name a", "platform": "woo"},
]

# ── Price extraction ──────────────────────────────────────────────────────────

def clean_price(text):
    if not text:
        return None
    s = re.sub(r'[^\d.,]', '', str(text)).strip().rstrip('.,')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '.')
    try:
        val = float(s)
        if val < 5 or val > 50000:
            return None
        if val > 5000:
            val /= 100
        return round(val, 2)
    except ValueError:
        return None


def extract_jsonld_price(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            for item in (data if isinstance(data, list) else [data]):
                if not isinstance(item, dict):
                    continue
                for key in ("price", "Price"):
                    if key in item:
                        p = clean_price(str(item[key]))
                        if p: return p
                offers = item.get("offers") or item.get("Offers")
                if isinstance(offers, list): offers = offers[0]
                if isinstance(offers, dict):
                    for key in ("price", "Price", "lowPrice"):
                        p = clean_price(str(offers.get(key, "")))
                        if p: return p
        except Exception:
            pass
    return None


def extract_meta_price(soup):
    for prop in ("product:price:amount", "og:price:amount"):
        tag = soup.find("meta", property=prop)
        if tag:
            p = clean_price(tag.get("content", ""))
            if p: return p
    return None


def extract_script_price(soup):
    patterns = [
        r'"finalPrice"\s*:\s*\{[^}]*?"amount"\s*:\s*([0-9]+(?:[.,][0-9]+)?)',
        r'"price"\s*:\s*"?([0-9]+(?:[.,][0-9]+))"?',
    ]
    for script in soup.find_all("script"):
        text = script.string or ""
        if "price" not in text.lower():
            continue
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                p = clean_price(m.group(1))
                if p: return p
    return None


def extract_css_price(soup):
    for sel in [
        ".woocommerce-Price-amount bdi",
        ".price ins .woocommerce-Price-amount bdi",
        ".woocommerce-Price-amount",
        ".price-new",
        'span[data-price-type="finalPrice"] .price',
        ".price-wrapper .price",
        "[itemprop='price']",
    ]:
        tag = soup.select_one(sel)
        if tag:
            p = clean_price(tag.get("content") or tag.get_text())
            if p: return p
    return None


def get_price_from_page(soup, platform):
    p = extract_jsonld_price(soup)
    if p: return p
    p = extract_meta_price(soup)
    if p: return p
    if platform == "magento":
        p = extract_script_price(soup)
        if p: return p
    return extract_css_price(soup)


# ── Search & scrape ───────────────────────────────────────────────────────────

def name_score(title, wine_name):
    """Simple relevance score: how many words from wine_name appear in title."""
    words = wine_name.lower().split()
    title_l = title.lower()
    return sum(1 for w in words if w in title_l)


def search_wine_on_site(site, wine_name, scraper_client, debug=False):
    query = wine_name.replace("'", "").replace("'", "")
    url = site["search_url"].replace("{q}", query.replace(" ", "+"))
    try:
        res = scraper_client.get(url, timeout=15)
        if res.status_code != 200:
            return None, None, f"Search HTTP {res.status_code}"
        soup = BeautifulSoup(res.content, "html.parser")

        # Find product links in search results
        links = []
        for tag in soup.select(site["result_sel"]):
            href = tag.get("href") or (tag.find_parent("a") or {}).get("href")
            text = tag.get_text(strip=True)
            if href and href.startswith("http"):
                links.append((href, text))
            elif href:
                from urllib.parse import urljoin
                links.append((urljoin(url, href), text))

        if not links:
            return None, None, "Niciun rezultat gasit"

        # Pick best matching link
        links.sort(key=lambda x: name_score(x[1], wine_name), reverse=True)
        best_url, best_title = links[0]

        if debug:
            st.caption(f"  Top result: {best_title[:60]} → {best_url}")

        # Fetch product page
        res2 = scraper_client.get(best_url, timeout=15)
        if res2.status_code != 200:
            return None, best_url, f"Product HTTP {res2.status_code}"
        soup2 = BeautifulSoup(res2.content, "html.parser")
        price = get_price_from_page(soup2, site["platform"])
        if price:
            return price, best_url, None
        return None, best_url, "Pret negasit in pagina"
    except Exception as e:
        return None, None, str(e)[:60]


# ── Persistence ───────────────────────────────────────────────────────────────

def load_wines():
    if os.path.exists("wines.json"):
        with open("wines.json") as f:
            data = json.load(f)
        # Support both old format (with sources) and new format (name only)
        return [w["name"] if isinstance(w, dict) else w for w in data]
    return ["Le Volte dell'Ornellaia"]


def save_wines(wines):
    with open("wines.json", "w") as f:
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
    history.setdefault(wine_name, [])
    for r in results:
        history[wine_name].append({"date": today, "store": r["Magazin"], "price": r["Pret (RON)"]})
    save_history(history)


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🍷 Wine Watcher RO")
st.caption("Cauta automat preturile pe toate site-urile romanesti de vinuri")

wines = load_wines()

with st.sidebar:
    st.header("🍾 Vinuri urmarite")
    selected = st.selectbox("Selecteaza vin", wines)

    st.divider()
    with st.form("add_wine"):
        st.subheader("Adauga vin nou")
        new_name = st.text_input("Nume vin (ex: Antinori Tignanello)")
        if st.form_submit_button("Adauga") and new_name:
            if new_name not in wines:
                wines.append(new_name)
                save_wines(wines)
                st.rerun()

    if len(wines) > 1:
        st.divider()
        with st.form("del_wine"):
            st.subheader("Sterge vin")
            to_del = st.selectbox("Vin de sters", wines)
            if st.form_submit_button("Sterge") and to_del:
                wines.remove(to_del)
                save_wines(wines)
                st.rerun()

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader(f"📍 {selected}")
with col2:
    fetch = st.button("🔄 Cauta preturi", use_container_width=True)

debug_mode = st.toggle("🔍 Mod debug", value=False)

if fetch:
    scraper_client = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    results, errors = [], []
    progress = st.progress(0)
    status = st.empty()

    for i, site in enumerate(SITES):
        status.info(f"Cautam pe {site['store']}... ({i+1}/{len(SITES)})")
        if debug_mode:
            st.caption(f"🔎 {site['store']}")
        price, url, err = search_wine_on_site(site, selected, scraper_client, debug=debug_mode)
        if price:
            results.append({"Magazin": site["store"], "Pret (RON)": price, "Link": url})
        else:
            errors.append({"Magazin": site["store"], "Eroare": err or "Negasit"})
        time.sleep(1)
        progress.progress((i + 1) / len(SITES))

    status.empty()
    progress.empty()

    if results:
        record_prices(selected, results)
        st.session_state[f"res_{selected}"] = results
        st.session_state[f"err_{selected}"] = errors
        st.success(f"Gasit pe {len(results)} site-uri la {datetime.now().strftime('%H:%M, %d %b %Y')}")
    else:
        st.error("Nu am gasit pretul pe niciun site.")
        with st.expander("Detalii erori", expanded=True):
            for e in errors:
                st.write(f"❌ **{e['Magazin']}**: {e['Eroare']}")

results = st.session_state.get(f"res_{selected}", [])
errors  = st.session_state.get(f"err_{selected}", [])

if results:
    df = pd.DataFrame(results).sort_values("Pret (RON)")
    best = df.iloc[0]
    st.success(f"🏆 Cel mai ieftin: **{best['Magazin']}** — **{best['Pret (RON)']} RON**")

    col_a, col_b = st.columns(2)
    with col_a:
        st.dataframe(df[["Magazin", "Pret (RON)"]].reset_index(drop=True), use_container_width=True, hide_index=True)
        if errors:
            with st.expander(f"⚠️ {len(errors)} site-uri fara rezultat"):
                for e in errors:
                    st.write(f"❌ **{e['Magazin']}**: {e['Eroare']}")
    with col_b:
        if HAS_PLOTLY:
            fig = px.bar(df, x="Magazin", y="Pret (RON)", color="Pret (RON)",
                         color_continuous_scale="reds_r", title="Comparatie preturi")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🛒 Cumpara direct")
    cols = st.columns(min(len(results), 4))
    for col, r in zip(cols, results):
        col.link_button(f"{r['Magazin']}\n{r['Pret (RON)']} RON", r["Link"], use_container_width=True)

st.divider()
st.subheader("📈 Istoric preturi")
history = load_history()
wine_hist = history.get(selected, [])
if wine_hist:
    hist_df = pd.DataFrame(wine_hist)
    hist_df["date"] = pd.to_datetime(hist_df["date"])
    if HAS_PLOTLY:
        fig2 = px.line(hist_df, x="date", y="price", color="store",
                       title=f"Evolutie preturi - {selected}",
                       labels={"date": "Data", "price": "Pret (RON)", "store": "Magazin"})
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.dataframe(hist_df, use_container_width=True)
    if st.button("🗑️ Sterge istoricul"):
        history.pop(selected, None)
        save_history(history)
        st.rerun()
else:
    st.info("Apasa 'Cauta preturi' pentru a incepe colectarea.")
