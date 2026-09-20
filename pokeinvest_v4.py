import os
from datetime import datetime
import requests
import pandas as pd
import streamlit as st

# ============================================================
# PokéInvest V4 — Free/TCGplayer edition
# Designed for the PkmnPrices Free plan.
# Free plan: English cards + current TCGplayer USD prices.
# Cardmarket EUR, price history and marketplace listings are paid features.
# ============================================================

st.set_page_config(
    page_title="PokéInvest V4",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE = "https://api.pkmnprices.com/v1"


def api_get(path, params=None, api_key=""):
    if not api_key:
        return None, "Kein PkmnPrices API-Key."
    try:
        r = requests.get(
            BASE + path,
            params=params or {},
            headers={"X-Api-Key": api_key},
            timeout=25,
        )
        if r.status_code == 401:
            return None, "API-Key ungültig oder abgelaufen."
        if r.status_code == 403:
            return None, "Dieser Datenbereich ist in deinem aktuellen PkmnPrices-Tarif nicht freigeschaltet."
        if r.status_code == 429:
            return None, "API-Limit erreicht. Der kostenlose Tarif hat 500 Credits pro Tag."
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, f"Netzwerk/API-Fehler: {e}"


def card_search(q, api_key, page=1, per_page=25, sort=None):
    params = {
        "name": q,
        "language": "English",
        "page": page,
        "per_page": per_page,
        "currency": "usd",
    }
    if sort:
        params["sort"] = sort
    return api_get("/cards", params, api_key)


def card_get(card_id, api_key):
    # IMPORTANT: Free plan supports TCGplayer USD, not Cardmarket EUR.
    return api_get(f"/cards/{card_id}", {"currency": "usd"}, api_key)


def pct(x):
    if x is None or pd.isna(x):
        return "–"
    return f"{x:+.1f}%"


with st.sidebar:
    st.header("⚙️ Einstellungen")
    api_key = st.text_input(
        "PkmnPrices API-Key",
        value=os.getenv("PKMNPRICES_API_KEY", ""),
        type="password",
        help="Den Key nicht öffentlich in GitHub speichern.",
    )
    st.divider()
    st.markdown("**Kostenloser Datenmodus**")
    st.caption("TCGplayer • USD • English")
    st.caption("500 API-Credits pro Tag")
    st.caption("Cardmarket EUR und Historie benötigen einen bezahlten Tarif.")

st.title("🃏 PokéInvest V4")
st.caption("Pokémon-Karten Marktanalyse • kostenlose TCGplayer-USD-Version")

if api_key:
    st.success("🟢 Live-Datenmodus aktiv — TCGplayer USD")
else:
    st.info("Demo-/Startmodus. Links einen PkmnPrices API-Key eintragen, um echte Daten abzurufen.")

tab_dash, tab_search, tab_card, tab_watch, tab_portfolio = st.tabs(
    ["🏠 Dashboard", "🔎 Karten suchen", "📈 Kartenanalyse", "💎 Kandidaten", "📦 Sammlung"]
)

# ---------------- Dashboard ----------------
with tab_dash:
    st.subheader("🔥 Marktübersicht")
    if not api_key:
        st.write("Die App ist für den kostenlosen PkmnPrices-Tarif vorbereitet.")
        st.markdown("### Was kostenlos möglich ist")
        st.write("• Kartensuche  • aktuelle TCGplayer-Preise  • Kartenvergleich  • Sammlung  • eigene Watchlist")
        st.warning("Historische Preisentwicklung, Cardmarket EUR und Cardmarket-Angebote sind im Free-Tarif nicht verfügbar.")
    else:
        st.markdown("### Schnellstart")
        st.write("Suche z. B. **Charizard**, **Umbreon**, **Pikachu** oder eine Kartennummer.")
        st.write("V4 verwendet bewusst nur Daten, die dein kostenloser Tarif abrufen darf.")

# ---------------- Search ----------------
with tab_search:
    st.subheader("🔎 Pokémon-Karten suchen")
    q = st.text_input("Kartennamen eingeben", placeholder="z. B. Charizard, Umbreon VMAX, Pikachu")
    if q:
        if not api_key:
            st.warning("Bitte zuerst links den API-Key eintragen.")
        else:
            data, err = card_search(q, api_key, per_page=25)
            if err:
                st.error(err)
            else:
                rows = data.get("data", [])
                if not rows:
                    st.warning("Keine Karten gefunden.")
                else:
                    results = pd.DataFrame([
                        {
                            "ID": x.get("id"),
                            "Karte": x.get("name"),
                            "Set": (x.get("set") or {}).get("name"),
                            "Nr.": x.get("number"),
                            "Seltenheit": x.get("rarity"),
                        }
                        for x in rows
                    ])
                    st.dataframe(results, use_container_width=True, hide_index=True)
                    selected = st.selectbox(
                        "Karte für Analyse auswählen",
                        results.index,
                        format_func=lambda i: f"{results.loc[i,'Karte']} — {results.loc[i,'Set']} #{results.loc[i,'Nr.']}",
                    )
                    st.session_state["selected_card_id"] = int(results.loc[selected, "ID"])
                    st.session_state["selected_card_name"] = results.loc[selected, "Karte"]
                    st.success("Karte ausgewählt. Öffne „📈 Kartenanalyse“.")

# ---------------- Card analysis ----------------
with tab_card:
    st.subheader("📈 Kartenanalyse")
    if not api_key:
        st.info("Für die Live-Analyse zuerst links einen API-Key eintragen.")
    elif "selected_card_id" not in st.session_state:
        st.info("Erst unter „🔎 Karten suchen“ eine Karte auswählen.")
    else:
        cid = st.session_state["selected_card_id"]
        detail, err = card_get(cid, api_key)
        if err:
            st.error(err)
        else:
            name = detail.get("name", "Unbekannte Karte")
            set_name = (detail.get("set") or {}).get("name", "")
            prices = [
                p for p in detail.get("prices", [])
                if str(p.get("currency", "")).upper() == "USD"
                and str(p.get("condition", "")).lower() == "near mint"
            ]

            st.markdown(f"## {name}")
            st.caption(f"{set_name} • #{detail.get('number','–')} • {detail.get('rarity','–')}")

            if prices:
                p0 = prices[0]
                price = float(p0.get("market_price", 0) or 0)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("TCGplayer Marktpreis", f"${price:,.2f}")
                c2.metric("Variante", p0.get("variant", "–"))
                c3.metric("Zustand", p0.get("condition", "–"))
                c4.metric("Stand", str(p0.get("created_at", ""))[:10] or "–")

                # Simple, transparent price bucket — not an investment rating.
                if price >= 250:
                    bucket = "Sehr hoher aktueller Marktpreis"
                elif price >= 100:
                    bucket = "Hoher aktueller Marktpreis"
                elif price >= 25:
                    bucket = "Mittlerer aktueller Marktpreis"
                else:
                    bucket = "Niedriger aktueller Marktpreis"
                st.info(f"Preis-Kategorie: **{bucket}**. Das ist nur eine Einordnung des aktuellen Preises, keine Renditeprognose.")
            else:
                st.warning("Für Near Mint wurde kein aktueller USD-Preis zurückgegeben.")

            if detail.get("image_url"):
                with st.expander("🖼️ Kartenbild"):
                    st.image(detail["image_url"], width=280)

            st.markdown("### 📌 Was wir im Free-Tarif noch nicht messen können")
            st.write("Historische 30/90/180/365-Tage-Entwicklung, Cardmarket EUR und Cardmarket-Angebote sind mit dem kostenlosen PkmnPrices-Tarif nicht freigeschaltet.")

# ---------------- Candidates ----------------
with tab_watch:
    st.subheader("💎 Kandidaten / Watchlist")
    st.caption("V4 nutzt im Free-Tarif keine erfundene Renditeprognose. Kandidaten werden anhand aktueller TCGplayer-Preise angezeigt.")

    if not api_key:
        st.info("API-Key eintragen, dann kannst du Kandidaten suchen.")
    else:
        query = st.text_input("Kandidatengruppe suchen", value="Charizard", key="candidate_query")
        if query:
            data, err = card_search(query, api_key, per_page=20, sort="price_desc")
            if err:
                st.error(err)
            else:
                rows = data.get("data", [])
                if not rows:
                    st.warning("Keine Treffer.")
                else:
                    # The list endpoint itself does not return prices, so fetch only the first 10 details.
                    rows = rows[:10]
                    out = []
                    progress = st.progress(0)
                    for i, card in enumerate(rows, start=1):
                        detail, derr = card_get(card.get("id"), api_key)
                        price = None
                        variant = None
                        if not derr:
                            p = [
                                x for x in detail.get("prices", [])
                                if str(x.get("currency", "")).upper() == "USD"
                                and str(x.get("condition", "")).lower() == "near mint"
                            ]
                            if p:
                                price = p[0].get("market_price")
                                variant = p[0].get("variant")
                        out.append({
                            "ID": card.get("id"),
                            "Karte": card.get("name"),
                            "Set": (card.get("set") or {}).get("name"),
                            "Seltenheit": card.get("rarity"),
                            "Preis USD": price,
                            "Variante": variant,
                        })
                        progress.progress(i / len(rows))
                    progress.empty()
                    cdf = pd.DataFrame(out).dropna(subset=["Preis USD"]).sort_values("Preis USD", ascending=False)
                    st.dataframe(cdf, use_container_width=True, hide_index=True)
                    st.caption("Die Tabelle zeigt aktuelle Preise, nicht die erwartete zukünftige Wertentwicklung.")

# ---------------- Collection ----------------
with tab_portfolio:
    st.subheader("📦 Meine Sammlung")
    st.caption("Die Sammlung wird zunächst in deiner Browser-Session gespeichert und kann als CSV exportiert werden.")

    if "collection" not in st.session_state:
        st.session_state["collection"] = []

    with st.form("add_collection"):
        c1, c2, c3, c4 = st.columns(4)
        card_name = c1.text_input("Karte")
        purchase_price = c2.number_input("Kaufpreis €", min_value=0.0, value=0.0, step=1.0)
        quantity = c3.number_input("Anzahl", min_value=1, value=1, step=1)
        condition = c4.selectbox("Zustand", ["Near Mint", "Excellent", "Good", "Light Played", "Played", "Poor"])
        add = st.form_submit_button("➕ Hinzufügen")

    if add and card_name:
        st.session_state["collection"].append({
            "Karte": card_name,
            "Kaufpreis €": purchase_price,
            "Anzahl": quantity,
            "Zustand": condition,
        })
        st.success("Zur Sammlung hinzugefügt.")

    if st.session_state["collection"]:
        cdf = pd.DataFrame(st.session_state["collection"])
        total_cost = (cdf["Kaufpreis €"] * cdf["Anzahl"]).sum()
        a, b = st.columns(2)
        a.metric("Investierte Summe", f"{total_cost:.2f} €")
        b.metric("Positionen", len(cdf))
        st.dataframe(cdf, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Sammlung als CSV speichern",
            cdf.to_csv(index=False).encode("utf-8"),
            "pokeinvest_sammlung.csv",
            "text/csv",
        )
    else:
        st.info("Noch keine Karten in der Sammlung.")

st.divider()
st.caption("PokéInvest V4 • Datenquelle: PkmnPrices / TCGplayer. Aktuelle Preise sind keine Garantie für zukünftige Wertentwicklung.")
