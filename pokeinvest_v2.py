import os
import requests
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(page_title="PokéInvest V2", page_icon="🃏", layout="wide")

st.title("🃏 PokéInvest V2")
st.caption("Pokémon-Karten: Marktpreise, Historie, Gewinner & datenbasierte Watchlist")

with st.sidebar:
    st.header("⚙️ Datenquellen")
    cm_key = st.text_input(
        "Cardmarket API Key",
        value=os.getenv("CARDMARKET_API_KEY", ""),
        type="password",
        help="Optional. Ohne Key läuft die App im Demo-Modus."
    )
    pk_key = st.text_input(
        "PkmnPrices API Key",
        value=os.getenv("PKMNPRICES_API_KEY", ""),
        type="password",
        help="Optional. Für historische Cardmarket-Zeitreihen."
    )
    st.divider()
    st.caption("Preise sind Marktbeobachtungen und keine Garantie für zukünftige Renditen.")

DEMO = pd.DataFrame([
    ["Umbreon VMAX", "Evolving Skies", 680, .51, 1.43, 3.90, "Hoch", "Hoch"],
    ["Charizard VMAX", "Darkness Ablaze", 310, .28, .84, 2.40, "Hoch", "Hoch"],
    ["Pikachu VMAX", "Vivid Voltage", 190, .17, .61, 1.80, "Mittel", "Hoch"],
    ["Lugia V Alt Art", "Silver Tempest", 245, .34, .92, 2.15, "Mittel", "Hoch"],
    ["Gengar VMAX Alt Art", "Fusion Strike", 410, .39, 1.11, 2.85, "Mittel", "Mittel"],
    ["Rayquaza VMAX Alt Art", "Evolving Skies", 520, .31, 1.25, 3.10, "Hoch", "Mittel"],
], columns=["Karte","Set","Preis €","1J","3J","5J","Volatilität","Liquidität"])

def cm_get(path, params=None):
    if not cm_key:
        return None, "Kein Cardmarket API-Key hinterlegt."
    try:
        r = requests.get(
            "https://cardmarketapi.com/api/v1" + path,
            params=params or {},
            headers={"X-API-Key": cm_key},
            timeout=20,
        )
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)

def search_cards(q):
    data, err = cm_get("/search", {"q": q, "game": "pokemon", "limit": 20})
    if err or not data:
        return pd.DataFrame(), err
    rows = []
    for x in data.get("results", []):
        rows.append({
            "id": x.get("id"),
            "Karte": x.get("name"),
            "Set": x.get("expansion"),
            "Code": x.get("code"),
            "Bild": x.get("image_url"),
        })
    return pd.DataFrame(rows), None

def get_card(card_id):
    return cm_get(f"/card/{card_id}", {"game":"pokemon", "language":"english", "condition":"nm"})

def history(card_id, days=365):
    if not pk_key:
        return pd.DataFrame(), "Kein PkmnPrices API-Key hinterlegt."
    try:
        r = requests.get(
            f"https://api.pkmnprices.com/v1/cards/{card_id}/prices/history",
            params={"currency":"eur","period":f"{min(days,365)}d",
                    "condition":"Near Mint","limit":365},
            headers={"X-API-Key": pk_key},
            timeout=20,
        )
        r.raise_for_status()
        rows = r.json().get("data", [])
        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

def pct(v):
    return f"{v:+.1%}" if pd.notna(v) else "–"

def analysis_score(g1, g3, g5, vol, liq):
    vol_penalty = {"Niedrig":0, "Mittel":7, "Hoch":15}.get(vol, 7)
    liq_bonus = {"Niedrig":2, "Mittel":8, "Hoch":14}.get(liq, 8)
    return round((g1*20 + g3*35 + g5*25) + liq_bonus - vol_penalty, 1)

tabs = st.tabs(["🏠 Dashboard", "🔎 Karten", "📈 Historie", "💎 Watchlist"])

with tabs[0]:
    if cm_key:
        st.success("Live-Modus aktiviert.")
    else:
        st.info("Demo-Modus. Trage links einen API-Key ein, um echte Cardmarket-Daten abzurufen.")

    st.subheader("🔥 Marktübersicht")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Demo-Karten", len(DEMO))
    c2.metric("Ø Preis", f"{DEMO['Preis €'].mean():.0f} €")
    c3.metric("Ø 3J", pct(DEMO["3J"].mean()))
    c4.metric("Ø 5J", pct(DEMO["5J"].mean()))

    show = DEMO.copy()
    show["Analyse-Score"] = [
        analysis_score(r["1J"],r["3J"],r["5J"],r["Volatilität"],r["Liquidität"])
        for _,r in show.iterrows()
    ]
    st.dataframe(
        show.sort_values("Analyse-Score", ascending=False)
        [["Karte","Set","Preis €","1J","3J","5J","Volatilität","Liquidität","Analyse-Score"]]
        .style.format({"Preis €":"{:.0f}","1J":"{:.0%}","3J":"{:.0%}","5J":"{:.0%}"}),
        use_container_width=True, hide_index=True
    )

with tabs[1]:
    st.subheader("🔎 Pokémon-Karte suchen")
    q = st.text_input("Suche", placeholder="z. B. Charizard ex oder ASC 276")
    if q:
        if cm_key:
            results, err = search_cards(q)
            if err:
                st.error(err)
            elif results.empty:
                st.warning("Keine Treffer.")
            else:
                st.dataframe(results.drop(columns=["Bild"]), use_container_width=True, hide_index=True)
                selected = st.selectbox("Karte auswählen", results["Karte"].tolist())
                cid = results.loc[results["Karte"]==selected, "id"].iloc[0]
                if st.button("💶 Live-Preis laden"):
                    card, err = get_card(cid)
                    if err:
                        st.error(err)
                    else:
                        p = card.get("prices", {})
                        a,b,c,d = st.columns(4)
                        a.metric("Ab", f"{p.get('from','–')} €")
                        b.metric("Ø 5 günstigste", f"{p.get('avg5','–')} €")
                        c.metric("Trend", f"{p.get('trend','–')} €")
                        d.metric("Ø 30 Tage", f"{p.get('avg30','–')} €")
                        st.write(f"**Angebote:** {p.get('available','–')}")
                        if card.get("image_url"):
                            st.image(card["image_url"], width=260)
        else:
            matches = DEMO[DEMO["Karte"].str.contains(q, case=False, na=False) |
                           DEMO["Set"].str.contains(q, case=False, na=False)]
            st.dataframe(matches, use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("📈 Historische Preisentwicklung")
    if cm_key:
        st.caption("Suche eine Karte im Karten-Tab und nutze dort die Cardmarket-ID. Für echte Historie wird ein PkmnPrices-Key benötigt.")
    demo_card = st.selectbox("Demo-Karte", DEMO["Karte"])
    row = DEMO[DEMO["Karte"]==demo_card].iloc[0]
    years = pd.DataFrame({
        "Jahre":[5,4,3,2,1,0],
        "Index":[100, 100/(1+row["5J"])*1.35, 100/(1+row["5J"])*1.65,
                 100/(1+row["5J"])*2.05, 100/(1+row["5J"])*2.75, 100],
    })
    # Normierter Demo-Chart, ausdrücklich als Demo gekennzeichnet.
    st.caption("Demo-Chart: normierte Darstellung. Keine historischen Einzelpreise.")
    st.line_chart(years.set_index("Jahre")["Index"])

    if pk_key and cm_key:
        st.info("Für eine echte Historie: Im Karten-Tab die Cardmarket-ID auswählen; die automatische Verknüpfung kommt in V2.1.")

with tabs[3]:
    st.subheader("💎 Datenbasierte Watchlist")
    budget = st.number_input("Budget (€)", 50, 100000, 500, 50)
    risk = st.select_slider("Maximale Schwankung", ["Niedrig","Mittel","Hoch"], value="Mittel")
    horizon = st.selectbox("Fokus", ["1 Jahr","3 Jahre","5 Jahre"], index=1)

    candidates = DEMO[DEMO["Preis €"] <= budget].copy()
    if risk == "Niedrig":
        candidates = candidates[candidates["Volatilität"]=="Niedrig"]
    elif risk == "Mittel":
        candidates = candidates[candidates["Volatilität"].isin(["Niedrig","Mittel"])]

    candidates["Score"] = candidates.apply(
        lambda r: analysis_score(r["1J"],r["3J"],r["5J"],r["Volatilität"],r["Liquidität"]), axis=1
    )
    candidates["Begründung"] = candidates.apply(
        lambda r: f"5J {pct(r['5J'])}, 3J {pct(r['3J'])}, Liquidität {r['Liquidität']}, Volatilität {r['Volatilität']}",
        axis=1
    )

    if candidates.empty:
        st.warning("Keine Karten erfüllen die aktuellen Filter.")
    else:
        st.dataframe(
            candidates.sort_values("Score", ascending=False)
            [["Karte","Set","Preis €","1J","3J","5J","Volatilität","Liquidität","Score","Begründung"]]
            .style.format({"Preis €":"{:.0f}","1J":"{:.0%}","3J":"{:.0%}","5J":"{:.0%}"}),
            use_container_width=True, hide_index=True
        )

        st.markdown("### 🧠 So entsteht der Score")
        st.write("Historische Entwicklung + Liquiditätsbonus − Volatilitätsabschlag. Der Score ist ein Screening-Werkzeug und keine Kaufempfehlung.")

st.divider()
st.caption("PokéInvest V2 • Cardmarket-Daten werden nur mit gültigem API-Key abgerufen. Historische Daten werden als beobachtete Preisreihen behandelt.")
