import os
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
import numpy as np
import streamlit as st

# ============================================================
# PokéInvest V3
# Live Pokémon card analysis using PkmnPrices API.
# API docs: https://www.pkmnprices.com/docs
# ============================================================

st.set_page_config(
    page_title="PokéInvest V3",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE = "https://api.pkmnprices.com/v1"

DEMO = pd.DataFrame([
    ["Umbreon VMAX", "Evolving Skies", 680.0, 51.0, 143.0, 390.0, "Hoch", "Hoch"],
    ["Charizard VMAX", "Darkness Ablaze", 310.0, 28.0, 84.0, 240.0, "Hoch", "Hoch"],
    ["Pikachu VMAX", "Vivid Voltage", 190.0, 17.0, 61.0, 180.0, "Mittel", "Hoch"],
    ["Lugia V Alt Art", "Silver Tempest", 245.0, 34.0, 92.0, 215.0, "Mittel", "Hoch"],
    ["Gengar VMAX Alt Art", "Fusion Strike", 410.0, 39.0, 111.0, 285.0, "Mittel", "Mittel"],
    ["Rayquaza VMAX Alt Art", "Evolving Skies", 520.0, 31.0, 125.0, 310.0, "Hoch", "Mittel"],
], columns=["Karte","Set","Preis €","1J %","3J %","5J %","Volatilität","Liquidität"])


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
        if r.status_code == 429:
            return None, "API-Limit erreicht. Bitte später erneut versuchen."
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return None, f"Netzwerk/API-Fehler: {e}"


def card_search(q, api_key, page=1, per_page=50):
    return api_get("/cards", {
        "name": q,
        "language": "English",
        "page": page,
        "per_page": per_page,
    }, api_key)


def card_get(card_id, api_key):
    return api_get(f"/cards/{card_id}", {"currency": "eur"}, api_key)


def price_history(card_id, api_key, period="365d", variant=None):
    params = {
        "currency": "eur",
        "period": period,
        "condition": "Near Mint",
        "limit": 365,
    }
    if variant:
        params["variant"] = variant
    return api_get(f"/cards/{card_id}/prices/history", params, api_key)


def listings(card_id, api_key, limit=20):
    return api_get(
        f"/cards/{card_id}/listings/cardmarket",
        {"condition": "Near Mint", "sort": "price_asc", "limit": limit},
        api_key,
    )


def pct(x):
    return "–" if x is None or pd.isna(x) else f"{x:+.1f}%"


def history_metrics(df):
    if df.empty:
        return {}
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date")
    # The API returns one row per day/variant. We aggregate by date.
    d["avg"] = pd.to_numeric(d["avg"], errors="coerce")
    d = d.dropna(subset=["avg"])
    if d.empty:
        return {}
    daily = d.groupby("date", as_index=True)["avg"].mean()
    last = float(daily.iloc[-1])
    out = {"current": last, "days": len(daily)}
    for days, label in [(30, "30d"), (90, "90d"), (180, "180d"), (365, "365d")]:
        cutoff = daily.index.max() - pd.Timedelta(days=days)
        old = daily[daily.index <= cutoff]
        if len(old):
            out[label] = (last / float(old.iloc[-1]) - 1) * 100
        else:
            out[label] = np.nan
    peak = float(daily.max())
    trough = float(daily.min())
    out["peak"] = peak
    out["trough"] = trough
    out["drawdown"] = (last / peak - 1) * 100 if peak else np.nan
    returns = daily.pct_change().dropna()
    out["volatility"] = float(returns.std() * np.sqrt(365) * 100) if len(returns) > 1 else np.nan
    return out


def candidate_score(metrics, spread_pct=None, offer_count=None):
    """Transparent screening score; not a forecast and not financial advice."""
    g90 = max(float(metrics.get("90d", 0) or 0), -100)
    g365 = max(float(metrics.get("365d", 0) or 0), -100)
    dd = float(metrics.get("drawdown", 0) or 0)
    vol = float(metrics.get("volatility", 0) or 0)
    score = 50 + g90 * 0.18 + g365 * 0.12 + max(dd, -50) * 0.08
    score -= min(vol, 100) * 0.08
    if spread_pct is not None:
        score -= min(max(spread_pct, 0), 50) * 0.10
    if offer_count is not None:
        score += min(offer_count, 20) * 0.25
    return round(float(score), 1)


with st.sidebar:
    st.header("⚙️ Einstellungen")
    api_key = st.text_input(
        "PkmnPrices API-Key",
        value=os.getenv("PKMNPRICES_API_KEY", ""),
        type="password",
        help="Den Key nicht öffentlich in GitHub speichern. Für Streamlit später als Secret hinterlegen.",
    )
    st.divider()
    st.markdown("**Datenbasis**")
    st.caption("Cardmarket EUR • Near Mint • English")
    st.caption("Historie: bis zu 365 Tage, abhängig vom API-Tarif.")
    st.divider()
    st.markdown("**V3-Fokus**")
    st.caption("Preis • Historie • Drawdown • Volatilität • Angebote • transparente Analyse")

st.title("🃏 PokéInvest V3")
st.caption("Pokémon-Karten Marktanalyse für Europa • Cardmarket EUR")

if api_key:
    st.success("Live-Datenmodus aktiv")
else:
    st.info("Demo-Modus. Links einen PkmnPrices API-Key eintragen, um echte Daten abzurufen.")

tab_dash, tab_search, tab_card, tab_watch, tab_portfolio = st.tabs(
    ["🏠 Dashboard", "🔎 Karten suchen", "📈 Kartenanalyse", "💎 Kandidaten", "📦 Sammlung"]
)

# ---------------- Dashboard ----------------
with tab_dash:
    st.subheader("🔥 Marktübersicht")

    if not api_key:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Demo-Karten", len(DEMO))
        c2.metric("Ø Preis", f"{DEMO['Preis €'].mean():.0f} €")
        c3.metric("Ø 1 Jahr", f"+{DEMO['1J %'].mean():.0f}%")
        c4.metric("Ø 5 Jahre", f"+{DEMO['5J %'].mean():.0f}%")
        st.dataframe(DEMO, use_container_width=True, hide_index=True)
        st.info("Die 3-/5-Jahreswerte oben sind ausschließlich Demo-Daten. Die Live-API liefert aktuell bis zu 365 Tage Historie.")
    else:
        st.markdown("### Schnellstart")
        st.write("Suche z. B. **Charizard**, **Umbreon**, **Pikachu** oder eine Kartennummer.")
        st.markdown("**Hinweis:** Eine echte Top-Liste des Gesamtmarktes benötigt einen API-Scan vieler Karten und verbraucht entsprechend Credits. V3 analysiert deshalb Karten auf Anfrage.")

# ---------------- Search ----------------
with tab_search:
    st.subheader("🔎 Pokémon-Karten suchen")
    q = st.text_input("Kartennamen eingeben", placeholder="z. B. Charizard, Umbreon VMAX, Pikachu")
    if q:
        if not api_key:
            hits = DEMO[DEMO["Karte"].str.contains(q, case=False, na=False) |
                        DEMO["Set"].str.contains(q, case=False, na=False)]
            if hits.empty:
                st.warning("Keine Demo-Treffer. API-Key eintragen für die vollständige Kartendatenbank.")
            else:
                st.dataframe(hits, use_container_width=True, hide_index=True)
        else:
            data, err = card_search(q, api_key)
            if err:
                st.error(err)
            else:
                rows = data.get("data", [])
                if not rows:
                    st.warning("Keine Karten gefunden.")
                else:
                    results = pd.DataFrame([{
                        "ID": x.get("id"),
                        "Karte": x.get("name"),
                        "Set": (x.get("set") or {}).get("name"),
                        "Nr.": x.get("number"),
                        "Seltenheit": x.get("rarity"),
                    } for x in rows])
                    st.dataframe(results, use_container_width=True, hide_index=True)
                    selected = st.selectbox(
                        "Karte für Analyse auswählen",
                        results.index,
                        format_func=lambda i: f"{results.loc[i,'Karte']} — {results.loc[i,'Set']} #{results.loc[i,'Nr.']}",
                    )
                    st.session_state["selected_card_id"] = int(results.loc[selected, "ID"])
                    st.session_state["selected_card_name"] = results.loc[selected, "Karte"]
                    st.success("Karte ausgewählt. Öffne den Tab „📈 Kartenanalyse“.")

# ---------------- Card analysis ----------------
with tab_card:
    st.subheader("📈 Kartenanalyse")

    if not api_key:
        st.info("Für die Live-Analyse zuerst links einen PkmnPrices API-Key eintragen.")
    elif "selected_card_id" not in st.session_state:
        st.info("Erst im Tab „🔎 Karten suchen“ eine Karte auswählen.")
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
                if str(p.get("currency","")).upper() == "EUR"
                and str(p.get("condition","")).lower() == "near mint"
            ]

            st.markdown(f"## {name}")
            st.caption(f"{set_name} • #{detail.get('number','–')} • {detail.get('rarity','–')}")

            c1,c2,c3,c4 = st.columns(4)
            if prices:
                p0 = prices[0]
                c1.metric("Cardmarket Marktpreis", f"{float(p0.get('market_price',0)):.2f} €")
                c2.metric("Variante", p0.get("variant","–"))
                c3.metric("Preisquelle", "Cardmarket")
                c4.metric("Stand", str(p0.get("created_at",""))[:10] or "–")
            else:
                c1.metric("Cardmarket", "keine Daten")
                c2.metric("Variante", "–")
                c3.metric("Preisquelle", "–")
                c4.metric("Stand", "–")

            if detail.get("image_url"):
                with st.expander("🖼️ Kartenbild"):
                    st.image(detail["image_url"], width=280)

            hist, herr = price_history(cid, api_key, "365d")
            if herr:
                st.warning(herr)
            else:
                hdf = pd.DataFrame(hist.get("data", []))
                m = history_metrics(hdf)
                if m:
                    a,b,c,d,e = st.columns(5)
                    a.metric("30 Tage", pct(m.get("30d")))
                    b.metric("90 Tage", pct(m.get("90d")))
                    c.metric("180 Tage", pct(m.get("180d")))
                    d.metric("365 Tage", pct(m.get("365d")))
                    e.metric("Vom Hoch", pct(m.get("drawdown")))

                    chart = hdf.copy()
                    chart["date"] = pd.to_datetime(chart["date"])
                    chart["avg"] = pd.to_numeric(chart["avg"], errors="coerce")
                    chart = chart.dropna(subset=["avg"]).groupby("date")["avg"].mean()
                    st.line_chart(chart)

                    st.markdown("### 📊 Risiko-/Stabilitätsdaten")
                    r1,r2,r3 = st.columns(3)
                    r1.metric("Historische Volatilität", f"{m.get('volatility', np.nan):.1f}% p.a." if pd.notna(m.get("volatility")) else "–")
                    r2.metric("Historisches Hoch", f"{m.get('peak', np.nan):.2f} €" if pd.notna(m.get("peak")) else "–")
                    r3.metric("Historisches Tief", f"{m.get('trough', np.nan):.2f} €" if pd.notna(m.get("trough")) else "–")

            offers, oerr = listings(cid, api_key)
            if not oerr:
                rows = offers.get("data", [])
                if rows:
                    odf = pd.DataFrame(rows)
                    clean = odf[(odf["condition"]=="Near Mint") & (odf["altered"]==False) & (odf["signed"]==False)]
                    st.markdown("### 🛒 Aktuelle Cardmarket-Angebote")
                    st.dataframe(
                        clean[["price","quantity","language","seller","graded","grader","grade"]].head(20),
                        use_container_width=True, hide_index=True
                    )

# ---------------- Candidates ----------------
with tab_watch:
    st.subheader("💎 Datenbasierte Kandidaten")
    st.caption("Der Score ist ein transparentes Screening-Modell. Er ist keine Renditeprognose und keine individuelle Anlageberatung.")

    if not api_key:
        st.dataframe(DEMO, use_container_width=True, hide_index=True)
    else:
        st.markdown("#### So funktioniert das Screening")
        st.write("V3 berücksichtigt beobachtete 90-/365-Tage-Entwicklung, Drawdown, historische Volatilität, Angebotsspanne und Anzahl sichtbarer Near-Mint-Angebote.")
        st.info("Für eine echte Markt-Rangliste müsste die App viele Karten systematisch abfragen. Das kostet API-Credits. Deshalb gibt es in V3 eine Einzelkartenanalyse; eine günstige Batch-Rangliste kann später ergänzt werden.")

# ---------------- Collection ----------------
with tab_portfolio:
    st.subheader("📦 Meine Sammlung")
    st.caption("Die Sammlung wird in V3 zunächst lokal in deiner Browser-Session verwaltet. Für dauerhafte Speicherung kommt eine Datenbank in V4.")

    if "collection" not in st.session_state:
        st.session_state["collection"] = []

    with st.form("add_collection"):
        c1,c2,c3,c4 = st.columns(4)
        card_name = c1.text_input("Karte")
        purchase_price = c2.number_input("Kaufpreis €", min_value=0.0, value=0.0, step=1.0)
        quantity = c3.number_input("Anzahl", min_value=1, value=1, step=1)
        condition = c4.selectbox("Zustand", ["Near Mint","Excellent","Good","Light Played","Played","Poor"])
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
        a,b = st.columns(2)
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
st.caption("PokéInvest V3 • Datenquelle: PkmnPrices / Cardmarket. Preise und historische Daten können unvollständig sein. Keine Garantie für zukünftige Wertentwicklung.")
