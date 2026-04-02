"""
Wine Price Watcher România
Caută și compară prețuri de vinuri din magazine online românești.
Toate prețurile includ TVA. Doar sticle 0.75L.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

from scraper import WineSearchEngine

st.set_page_config(
    page_title="Wine Price Watcher România",
    page_icon="🍷",
    layout="wide",
    initial_sidebar_state="expanded",
)

GROUPS_FILE = Path("groups.json")

st.markdown("""
<style>
  .stApp { background-color: #0f0805; color: #f0e6d3; }
  .stSidebar { background-color: #1a0e0a !important; border-right: 1px solid #5c1f28; }
  h1, h2, h3, h4 { color: #d4a84b !important; font-family: Georgia, serif !important; }
  .stButton > button {
      background: linear-gradient(135deg, #7c1f2e, #5c1520);
      color: #f5e6c8; border: 1px solid #a0384a;
      border-radius: 8px; font-weight: 600;
  }
  .stButton > button:hover {
      background: linear-gradient(135deg, #9e2840, #7c1f2e);
      border-color: #c94b5f; transform: translateY(-1px);
  }
  .stButton > button:disabled { background: #2a1a1a; color: #555; border-color: #333; }
  [data-testid="stMetric"] {
      background: linear-gradient(135deg, #1f0f0c, #2d1615);
      border: 1px solid #4a1520; border-radius: 10px; padding: 12px;
  }
  [data-testid="stMetricValue"] { color: #d4a84b !important; }
  [data-testid="stMetricLabel"] { color: #a0785a !important; }
  .streamlit-expanderHeader {
      background: linear-gradient(135deg, #1f1010, #2d1a1a) !important;
      border: 1px solid #5c2030 !important; border-radius: 8px !important;
  }
  .stDataFrame { border: 1px solid #4a2030; border-radius: 8px; overflow: hidden; }
  hr { border-color: #5c1f28 !important; }
  .stCaption { color: #8a6a4a !important; }
  .stTextInput input, .stTextArea textarea {
      background-color: #1f0f0c !important; color: #f5e6c8 !important;
      border-color: #5c2030 !important;
  }
  div[data-testid="stSelectbox"] > div {
      background-color: #1f0f0c !important; border-color: #5c2030 !important;
  }
  .stTabs [data-baseweb="tab"] { color: #a0785a; }
  .stTabs [data-baseweb="tab"][aria-selected="true"] { color: #d4a84b; border-bottom-color: #d4a84b; }
  .stInfo { background-color: #0a1a2e !important; border-color: #1a3a5e !important; }
  .stSuccess { background-color: #0a2e0a !important; border-color: #1a5e1a !important; }
  .stWarning { background-color: #2e1e0a !important; border-color: #5e3e1a !important; }
  .stError { background-color: #2e0a0a !important; border-color: #5e1a1a !important; }
</style>
""", unsafe_allow_html=True)


def load_groups() -> Dict[str, List[str]]:
    if GROUPS_FILE.exists():
        try:
            data = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_groups(groups: Dict[str, List[str]]) -> None:
    try:
        GROUPS_FILE.write_text(
            json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        st.error(f"Eroare salvare grupuri: {e}")


def init_state() -> None:
    if "groups" not in st.session_state:
        st.session_state.groups = load_groups()
    if "results" not in st.session_state:
        st.session_state.results: Dict[str, list] = {}
    if "engine" not in st.session_state:
        st.session_state.engine = None
    if "pending_wines" not in st.session_state:
        st.session_state.pending_wines: List[str] = []
    if "editing_group" not in st.session_state:
        st.session_state.editing_group = None


def get_engine() -> WineSearchEngine:
    if st.session_state.engine is None:
        st.session_state.engine = WineSearchEngine()
    return st.session_state.engine


def results_to_df(results: Dict[str, list]) -> pd.DataFrame:
    rows = []
    for wine, items in results.items():
        for r in items:
            rows.append({
                "Vin": wine,
                "Magazin": r["shop"],
                "Denumire Produs": r.get("name", wine),
                "Format": r.get("volume", "—"),
                "Preț (RON, TVA inc.)": r["price"],
                "Link": r["url"],
            })
    if not rows:
        return pd.DataFrame(columns=["Vin","Magazin","Denumire Produs","Format","Preț (RON, TVA inc.)","Link"])
    return pd.DataFrame(rows).sort_values(["Vin","Preț (RON, TVA inc.)"]).reset_index(drop=True)



def render_sidebar() -> None:
    groups = st.session_state.groups

    with st.sidebar:
        st.markdown("<h2 style='text-align:center;font-size:2rem;'>🍷</h2>", unsafe_allow_html=True)
        st.title("Grupuri de Vinuri")

        with st.expander("➕ Grup Nou", expanded=len(groups) == 0):
            g_name = st.text_input("Nume grup:", placeholder="ex: Barolo Preferate", key="new_g_name")
            g_wines = st.text_area(
                "Vinuri (unul per linie):",
                placeholder="Barolo Borgogno\nChianti Classico\nAmarone\nBrunello di Montalcino",
                height=130,
                key="new_g_wines",
            )
            if st.button("✅ Creează Grup", use_container_width=True, key="btn_create_group"):
                name = (g_name or "").strip()
                wines = [w.strip() for w in (g_wines or "").splitlines() if w.strip()]
                if not name:
                    st.error("Introdu un nume pentru grup.")
                elif not wines:
                    st.error("Adaugă cel puțin un vin.")
                else:
                    if name in groups:
                        groups[name] = list(dict.fromkeys(groups[name] + wines))
                        st.success(f"Adăugate {len(wines)} vinuri în '{name}'.")
                    else:
                        groups[name] = wines
                        st.success(f"Grup '{name}' creat cu {len(wines)} vinuri!")
                    save_groups(groups)
                    time.sleep(0.6)
                    st.rerun()

        st.divider()

        if groups:
            st.subheader(f"Grupuri ({len(groups)})")
            for gname, gwines in list(groups.items()):
                with st.expander(f"📦 {gname}  ·  {len(gwines)} vinuri"):
                    if st.session_state.editing_group == gname:
                        new_text = st.text_area(
                            "Editează vinuri:",
                            value="\n".join(gwines),
                            height=120,
                            key=f"edit_ta_{gname}",
                        )
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("💾 Salvează", key=f"save_{gname}", use_container_width=True):
                                groups[gname] = [w.strip() for w in new_text.splitlines() if w.strip()]
                                save_groups(groups)
                                st.session_state.editing_group = None
                                st.rerun()
                        with c2:
                            if st.button("✖ Anulează", key=f"cancel_{gname}", use_container_width=True):
                                st.session_state.editing_group = None
                                st.rerun()
                    else:
                        for w in gwines:
                            st.markdown(f"&nbsp;&nbsp;• {w}")
                        ca, cb, cc = st.columns(3)
                        with ca:
                            if st.button("🔍", key=f"srch_{gname}", help="Caută grupul"):
                                st.session_state.pending_wines = list(gwines)
                                st.rerun()
                        with cb:
                            if st.button("✏️", key=f"edit_{gname}", help="Editează"):
                                st.session_state.editing_group = gname
                                st.rerun()
                        with cc:
                            if st.button("🗑", key=f"del_{gname}", help="Șterge grupul"):
                                del groups[gname]
                                save_groups(groups)
                                st.rerun()
        else:
            st.info("Niciun grup încă.\nCreează primul grup de vinuri!")

        st.divider()
        st.caption(
            "ℹ️ Surse: 12+ magazine România\n"
            "💶 Prețuri cu TVA inclus (21%)\n"
            "🍾 Doar sticle 0.75L"
        )


def run_search(wines: List[str]) -> None:
    engine = get_engine()
    results: Dict[str, list] = {}

    st.subheader(f"🔍 Caut {len(wines)} {'vin' if len(wines) == 1 else 'vinuri'}…")
    overall = st.progress(0.0, text="Progres general")
    wine_label = st.empty()
    shop_bar = st.progress(0.0)
    shop_label = st.empty()

    for i, wine in enumerate(wines):
        wine_label.markdown(f"**Vin {i+1}/{len(wines)}:** _{wine}_")
        shop_bar.progress(0.0)

        def shop_cb(done: int, total: int) -> None:
            shop_bar.progress(done / max(total, 1))
            shop_label.text(f"  Magazine verificate: {done}/{total}")

        try:
            results[wine] = engine.search_wine(wine, progress_cb=shop_cb)
        except Exception as exc:
            st.warning(f"⚠️ Eroare la '{wine}': {str(exc)[:100]}")
            results[wine] = []

        overall.progress((i + 1) / len(wines), text=f"Progres: {i+1}/{len(wines)} vinuri")

    overall.empty()
    wine_label.empty()
    shop_bar.empty()
    shop_label.empty()

    n_found = sum(1 for v in results.values() if v)
    n_prices = sum(len(v) for v in results.values())
    st.success(f"✅ Gata! {n_found}/{len(wines)} vinuri găsite, {n_prices} prețuri total.")
    st.session_state.results = results


def render_wine_card(wine_name: str, items: list) -> None:
    if not items:
        st.warning(f"🍾 **{wine_name}** — Niciun rezultat 0.75L găsit.")
        return

    prices = [r["price"] for r in items]
    p_min, p_max = min(prices), max(prices)

    header = (
        f"🍷 **{wine_name}**  ·  "
        f"{len(items)} {'magazin' if len(items) == 1 else 'magazine'}  ·  "
        f"**{p_min:.2f}** – {p_max:.2f} RON"
    )

    with st.expander(header, expanded=True):
        col_tbl, col_stats = st.columns([3, 1])

        with col_tbl:
            df = pd.DataFrame(items)[["shop", "name", "price"]].rename(
                columns={"shop": "Magazin", "name": "Denumire Produs", "price": "Preț (RON)"}
            )

            def _color_price(v: float) -> str:
                if v == p_min:
                    return "color: #4caf50; font-weight: bold"
                if v == p_max:
                    return "color: #e57373"
                return ""

            styled = (
                df.style
                .applymap(_color_price, subset=["Preț (RON)"])
                .format({"Preț (RON)": "{:.2f} RON"})
                .hide(axis="index")
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)

        with col_stats:
            st.metric("🏆 Cel mai mic", f"{p_min:.2f} RON")
            st.metric("📊 Medie", f"{sum(prices)/len(prices):.2f} RON")
            st.metric("📈 Diferență", f"{p_max - p_min:.2f} RON")

        st.write("**Cumpără direct:**")
        cols = st.columns(min(4, len(items)))
        for j, r in enumerate(items):
            badge = "🏆 " if r["price"] == p_min else ""
            with cols[j % min(4, len(items))]:
                st.link_button(
                    f"{badge}{r['shop']}\n{r['price']:.2f} RON",
                    r["url"],
                    use_container_width=True,
                )


def tab_search() -> None:
    st.subheader("Caută Vinuri")
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.write("**Vinuri individuale** (unul per linie):")
        individual = st.text_area(
            label="vinuri individuale",
            label_visibility="collapsed",
            height=160,
            placeholder="Barolo Borgogno 2019\nChianti Classico Riserva\nAmarone della Valpolicella",
            key="ta_individual",
        )

    with col_r:
        st.write("**Sau caută un grup salvat:**")
        groups = st.session_state.groups
        group_opts = ["— Niciun grup —"] + list(groups.keys())
        chosen = st.selectbox(label="grup", label_visibility="collapsed", options=group_opts, key="sel_group")
        if chosen != "— Niciun grup —":
            gwines = groups[chosen]
            preview = "\n".join(f"• {w}" for w in gwines[:6])
            extra = f"\n… și încă {len(gwines)-6}" if len(gwines) > 6 else ""
            st.info(f"**{len(gwines)} vinuri** în '{chosen}':\n{preview}{extra}")

    wines_list: List[str] = []

    if st.session_state.pending_wines:
        wines_list = st.session_state.pending_wines
        st.session_state.pending_wines = []

    if chosen != "— Niciun grup —":
        for w in groups.get(chosen, []):
            if w not in wines_list:
                wines_list.append(w)

    if individual:
        for w in individual.splitlines():
            w = w.strip()
            if w and w not in wines_list:
                wines_list.append(w)

    cb1, cb2, cb3 = st.columns([3, 1.5, 1.5])
    with cb1:
        label_btn = f"🔍 Caută Prețuri ({len(wines_list)} vinuri)" if wines_list else "🔍 Caută Prețuri"
        search_clicked = st.button(label_btn, type="primary", disabled=not wines_list,
                                   use_container_width=True, key="btn_search_main")
    with cb2:
        clear_clicked = st.button("🗑 Șterge Rezultate", disabled=not st.session_state.results,
                                  use_container_width=True, key="btn_clear")
    with cb3:
        if st.session_state.results:
            total_p = sum(len(v) for v in st.session_state.results.values())
            st.caption(f"✅ {total_p} prețuri în memorie")

    if clear_clicked:
        st.session_state.results = {}
        st.rerun()

    if search_clicked and wines_list:
        st.divider()
        run_search(wines_list)
        st.rerun()

    if st.session_state.results:
        st.divider()
        results = st.session_state.results
        found = sum(1 for v in results.values() if v)
        total = len(results)
        total_p = sum(len(v) for v in results.values())

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Vinuri căutate", total)
        mc2.metric("Vinuri găsite", found)
        mc3.metric("Prețuri găsite", total_p)
        mc4.metric("Negăsite", total - found)

        st.divider()
        for wine_name, items in results.items():
            render_wine_card(wine_name, items)


def tab_table() -> None:
    results = st.session_state.results
    if not results:
        st.info("Nicio căutare efectuată. Mergi la **Caută Vinuri** pentru a începe.")
        return

    df = results_to_df(results)
    if df.empty:
        st.warning("Niciun rezultat disponibil.")
        return

    st.subheader("Tabel Complet de Prețuri")
    st.caption(f"Toate sticlele sunt **0.75L** | Prețuri **cu TVA inclus** (21%) | **{len(df)}** rezultate")

    with st.expander("🔧 Filtre & Sortare", expanded=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            sel_wines = st.multiselect("Filtrează vinuri:", options=df["Vin"].unique().tolist(),
                                       default=df["Vin"].unique().tolist(), key="f_wines")
        with f2:
            sel_shops = st.multiselect("Filtrează magazine:", options=df["Magazin"].unique().tolist(),
                                       default=df["Magazin"].unique().tolist(), key="f_shops")
        with f3:
            p_min = float(df["Preț (RON, TVA inc.)"].min())
            p_max = float(df["Preț (RON, TVA inc.)"].max())
            if p_min < p_max:
                price_range = st.slider("Interval preț (RON):", min_value=p_min, max_value=p_max,
                                        value=(p_min, p_max), step=0.5, key="f_price")
            else:
                price_range = (p_min, p_max)
                st.caption(f"Preț fix: {p_min:.2f} RON")

        s1, s2 = st.columns(2)
        with s1:
            sort_col = st.selectbox("Sortează după:", ["Preț (RON, TVA inc.)", "Vin", "Magazin"], key="f_sort_col")
        with s2:
            sort_asc = st.radio("Ordine:", ["Crescător ↑", "Descrescător ↓"], horizontal=True, key="f_sort_dir")

    mask = (
        df["Vin"].isin(sel_wines)
        & df["Magazin"].isin(sel_shops)
        & df["Preț (RON, TVA inc.)"].between(price_range[0], price_range[1])
    )
    filtered = df[mask].sort_values(sort_col, ascending=(sort_asc == "Crescător ↑")).reset_index(drop=True)

    min_per_wine = filtered.groupby("Vin")["Preț (RON, TVA inc.)"].transform("min")

    def _row_style(row: pd.Series):
        if row["Preț (RON, TVA inc.)"] == min_per_wine[row.name]:
            return ["background-color: #0a2e0a"] * len(row)
        return [""] * len(row)

    display = filtered[["Vin", "Magazin", "Denumire Produs", "Preț (RON, TVA inc.)"]].copy()
    styled = (
        display.style
        .apply(_row_style, axis=1)
        .format({"Preț (RON, TVA inc.)": "{:.2f} RON"})
        .hide(axis="index")
    )

    st.dataframe(styled, use_container_width=True,
                 height=min(600, max(300, len(filtered) * 36 + 60)), hide_index=True)
    st.caption(f"Afișând **{len(filtered)}/{len(df)}** rezultate  |  **Verde** = cel mai mic preț per vin")


def tab_export() -> None:
    results = st.session_state.results
    if not results:
        st.info("Nicio căutare efectuată încă.")
        return

    df = results_to_df(results)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.subheader("Export Date")
    ec1, ec2, ec3 = st.columns(3)

    with ec1:
        st.write("**CSV (compatibil Excel)**")
        csv = df.to_csv(index=False, encoding="utf-8-sig", sep=";", decimal=",")
        st.download_button("⬇️ Descarcă .csv", data=csv,
                           file_name=f"wine_prices_{ts}.csv", mime="text/csv", use_container_width=True)

    with ec2:
        st.write("**JSON**")
        json_str = json.dumps(results, ensure_ascii=False, indent=2, default=str)
        st.download_button("⬇️ Descarcă .json", data=json_str,
                           file_name=f"wine_prices_{ts}.json", mime="application/json", use_container_width=True)

    with ec3:
        st.write("**Grupuri salvate**")
        grp_str = json.dumps(st.session_state.groups, ensure_ascii=False, indent=2)
        st.download_button("⬇️ Descarcă grupuri.json", data=grp_str,
                           file_name="wine_groups.json", mime="application/json", use_container_width=True)

    st.divider()

    if not df.empty:
        st.subheader("Statistici per Vin")
        stats = (
            df.groupby("Vin")["Preț (RON, TVA inc.)"]
            .agg(["min", "max", "mean", "count"])
            .reset_index()
        )
        stats.columns = ["Vin", "Preț Min (RON)", "Preț Max (RON)", "Preț Mediu (RON)", "Nr. Magazine"]
        stats = stats.round(2)
        st.dataframe(
            stats.style
            .format({"Preț Min (RON)": "{:.2f}", "Preț Max (RON)": "{:.2f}", "Preț Mediu (RON)": "{:.2f}"})
            .background_gradient(subset=["Preț Min (RON)"], cmap="RdYlGn_r")
            .hide(axis="index"),
            use_container_width=True, hide_index=True,
        )

    st.divider()
    st.subheader("Previzualizare Completă")
    st.dataframe(
        df.style.format({"Preț (RON, TVA inc.)": "{:.2f} RON"}).hide(axis="index"),
        use_container_width=True, hide_index=True,
    )


def main() -> None:
    init_state()
    render_sidebar()

    st.title("🍷 Wine Price Watcher România")
    st.caption(
        "Caută și compară prețuri de vinuri din magazine online românești  |  "
        "Toate prețurile **includ TVA**  |  Doar sticle **0.75L**"
    )

    tab1, tab2, tab3 = st.tabs(["🔍 Caută Vinuri", "📊 Tabel Detaliat", "📋 Export & Statistici"])

    with tab1:
        tab_search()
    with tab2:
        tab_table()
    with tab3:
        tab_export()


if __name__ == "__main__":
    main()
