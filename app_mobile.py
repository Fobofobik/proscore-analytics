"""
ProScore Analytics — Mobil Uygulama
Telefon ekranı için optimize edilmiş, tek sütun tasarım.
"""
from __future__ import annotations

import os as _os
from datetime import datetime, timedelta, timezone

import streamlit as st

from config import LEAGUES
from engine.prediction import predict_match
from scrapers.sofascore_scraper import (
    get_upcoming_matches, get_team_form, get_h2h,
    get_team_season_stats, get_results_by_date, get_league_standings,
)
from scrapers.nba_scraper import (
    get_upcoming_nba_matches, get_nba_team_form,
    get_nba_h2h, get_nba_team_ratings, get_nba_back_to_back,
    get_nba_load_management, get_nba_travel_penalty, get_nba_results_by_date,
)
from scrapers.odds_scraper import get_odds, match_odds

# ── Sayfa ayarları ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ProScore",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

EASTERN_TZ = timezone(timedelta(hours=-5))
TURKISH_TZ  = timezone(timedelta(hours=3))

# ── CSS ────────────────────────────────────────────────────────────────────────
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, .stApp {
    background: #060d1a !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    color: #e2e8f0 !important;
}
.main .block-container {
    padding: 0 !important;
    max-width: 480px !important;
    margin: 0 auto !important;
}
/* Başlık şeridi */
.mob-header {
    background: #080f1f;
    border-bottom: 1px solid #0f1f38;
    padding: 14px 16px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
/* Nav sekmeleri */
.stTabs [data-baseweb="tab-list"] {
    background: #080f1f !important;
    border-bottom: 1px solid #0f1f38 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #3a5070 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 12px 20px !important;
    border-bottom: 2px solid transparent !important;
    flex: 1 !important;
    justify-content: center !important;
}
.stTabs [aria-selected="true"] {
    color: #3b82f6 !important;
    border-bottom: 2px solid #3b82f6 !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding: 0 !important;
}
/* Input alanları */
[data-testid="stDateInput"] input,
[data-testid="stSelectbox"] > div > div {
    background: #0b1628 !important;
    border: 1px solid #132035 !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-size: 14px !important;
}
/* Butonlar */
.stButton > button {
    background: #1d4ed8 !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    padding: 12px !important;
    width: 100% !important;
}
.stButton > button[kind="secondary"] {
    background: #0b1628 !important;
    color: #64748b !important;
    border: 1px solid #132035 !important;
}
/* Expander */
[data-testid="stExpander"] {
    background: #0b1628 !important;
    border: 1px solid #132035 !important;
    border-radius: 14px !important;
    margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary {
    background: #0b1628 !important;
    padding: 14px 16px !important;
    color: #cbd5e1 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}
[data-testid="stExpander"] > details > div {
    background: #0b1628 !important;
    padding: 0 16px 14px !important;
}
/* Uyarılar */
[data-testid="stAlert"] {
    background: #1a1a2e !important;
    border-radius: 10px !important;
    font-size: 13px !important;
}
/* Gizle: sidebar toggle, hamburger */
[data-testid="collapsedControl"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden !important; }
hr { border-color: #0f1f38 !important; margin: 10px 0 !important; }
</style>
""")

# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────────

def _logo_img(url: str, size: int = 22, radius: str = "50%") -> str:
    if not url:
        return ""
    return (f'<img src="{url}" width="{size}" height="{size}" '
            f'style="vertical-align:middle;border-radius:{radius};flex-shrink:0">')


def _badge(text: str, color: str = "#3b82f6") -> str:
    return (f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
            f'border-radius:6px;padding:3px 10px;font-size:12px;font-weight:700">{text}</span>')


def _form_strip(form: list[dict]) -> str:
    if not form:
        return '<span style="color:#334155;font-size:11px">Veri yok</span>'
    colors = {"W": "#10b981", "D": "#f59e0b", "L": "#ef4444"}
    labels = {"W": "G", "D": "B", "L": "M"}
    boxes  = ""
    for m in reversed(form):
        r = m.get("result", "?")
        c = colors.get(r, "#334155")
        l = labels.get(r, "?")
        boxes += (f'<div style="width:26px;height:26px;background:{c}22;border:2px solid {c};'
                  f'border-radius:6px;display:flex;align-items:center;justify-content:center;'
                  f'font-size:11px;font-weight:900;color:{c}">{l}</div>')
    return f'<div style="display:flex;gap:4px">{boxes}</div>'


def _prob_bar(label: str, pct: float, color: str) -> str:
    return (f'<div style="margin-bottom:8px">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:3px">'
            f'<span style="font-size:12px;color:#64748b">{label}</span>'
            f'<span style="font-size:12px;font-weight:700;color:{color}">%{pct}</span></div>'
            f'<div style="background:#0a1526;border-radius:4px;height:5px">'
            f'<div style="width:{pct}%;height:100%;background:{color};border-radius:4px"></div>'
            f'</div></div>')


# ── Veri yükleme ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def load_all_data(league_name: str, date_str: str | None = None):
    cfg   = LEAGUES[league_name]
    sport = cfg["sport"]
    raw_odds = get_odds(league_name)

    if sport == "nba":
        upcoming = get_upcoming_nba_matches(date_str=date_str)
        form_fn  = get_nba_team_form
        h2h_fn   = get_nba_h2h
    else:
        upcoming = get_upcoming_matches(league_id=cfg["id"], season=cfg["season"], date=date_str)
        form_fn  = lambda tid, tnm: get_team_form(tid, tnm, cfg["id"], cfg["season"])
        h2h_fn   = lambda hid, aid: get_h2h(hid, aid, cfg["id"])

    results = []
    for match in upcoming:
        home_id   = match["home_team_id"]
        away_id   = match["away_team_id"]
        home_name = match["home_team"]
        away_name = match["away_team"]

        home_form = form_fn(home_id, home_name)
        away_form = form_fn(away_id, away_name)
        h2h       = h2h_fn(home_id, away_id)

        if sport == "nba":
            home_ratings = get_nba_team_ratings(home_id)
            away_ratings = get_nba_team_ratings(away_id)
            home_load    = get_nba_load_management(home_id, home_name)
            away_load    = get_nba_load_management(away_id, away_name)
            raw_date     = match["match_time"].split(" ")[0]
            home_b2b     = get_nba_back_to_back(home_id, raw_date)
            away_b2b     = get_nba_back_to_back(away_id, raw_date)
            home_travel  = get_nba_travel_penalty(home_name, home_form, True,  away_name)
            away_travel  = get_nba_travel_penalty(away_name, away_form, False, home_name)
            home_season  = away_season = {}
            home_standing = away_standing = None
        else:
            home_ratings = away_ratings = {}
            home_load    = away_load    = []
            home_b2b     = away_b2b     = False
            home_travel  = away_travel  = 0.0
            home_season  = get_team_season_stats(home_id, home_name, cfg["id"], cfg["season"])
            away_season  = get_team_season_stats(away_id, away_name, cfg["id"], cfg["season"])
            standings     = get_league_standings(cfg["id"])
            home_standing = standings.get(home_id)
            away_standing = standings.get(away_id)

        odds = match_odds(raw_odds, home_name, away_name)
        pred = predict_match(
            home_form=home_form, away_form=away_form, h2h=h2h,
            home_odds=odds.get("home_win"), draw_odds=odds.get("draw"),
            away_odds=odds.get("away_win"), no_draw=(sport == "nba"),
            home_b2b=home_b2b, away_b2b=away_b2b,
            home_ratings=home_ratings or None, away_ratings=away_ratings or None,
            home_load_flags=home_load or None, away_load_flags=away_load or None,
            home_season_stats=home_season or None, away_season_stats=away_season or None,
            home_travel_penalty=home_travel, away_travel_penalty=away_travel,
            home_standing=home_standing, away_standing=away_standing,
        )
        results.append({
            "match": match, "prediction": pred, "odds": odds, "sport": sport,
            "home_form": home_form, "away_form": away_form,
            "home_b2b": home_b2b, "away_b2b": away_b2b,
        })
    return results


@st.cache_data(ttl=1800, show_spinner=False)
def load_results(league_name: str, date_str: str | None = None):
    cfg   = LEAGUES[league_name]
    sport = cfg["sport"]
    if sport == "nba":
        return get_nba_results_by_date(date_str), sport
    return get_results_by_date(league_id=cfg["id"], season=cfg["season"], date_str=date_str), sport


# ══════════════════════════════════════════════════════════════════════════════
# BAŞLIK
# ══════════════════════════════════════════════════════════════════════════════
st.html("""
<div class="mob-header">
  <div>
    <span style="font-size:20px;font-weight:900;color:#e2e8f0">Pro</span><span style="font-size:20px;font-weight:900;color:#3b82f6">Score</span>
    <span style="font-size:9px;color:#2d4a66;letter-spacing:2px;text-transform:uppercase;
                 font-weight:700;margin-left:6px">Analytics</span>
  </div>
  <span style="font-size:20px">📊</span>
</div>
""")

# ── Lig seçimi ─────────────────────────────────────────────────────────────────
with st.container():
    st.html('<div style="padding:12px 16px 0">')
    selected_league = st.selectbox("Lig", list(LEAGUES.keys()), label_visibility="collapsed")
    st.html('</div>')

league_cfg = LEAGUES[selected_league]
is_nba     = league_cfg["sport"] == "nba"

pred_colors = {"1": "#3b82f6", "X": "#f59e0b", "2": "#ef4444"}

# ── Navigasyon sekmeleri ───────────────────────────────────────────────────────
tab_tahmin, tab_sonuclar = st.tabs(["🔮  Tahmin", "📋  Sonuçlar"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TAHMİN
# ══════════════════════════════════════════════════════════════════════════════
with tab_tahmin:
    st.html('<div style="padding:12px 16px 8px">')

    default_date = datetime.now(EASTERN_TZ if is_nba else TURKISH_TZ).date()
    date_label   = "Tarih (ABD)" if is_nba else "Tarih"
    tahmin_date  = st.date_input(date_label, value=default_date,
                                  format="DD/MM/YYYY", key="mob_tahmin_date")
    sorgula = st.button("🔍  Analiz Et", key="mob_btn_tahmin")
    st.html('</div>')

    if sorgula:
        date_str = tahmin_date.strftime("%m/%d/%Y") if is_nba else tahmin_date.strftime("%Y-%m-%d")
        if tahmin_date == default_date:
            date_str = None
        with st.spinner("Veriler yükleniyor..."):
            try:
                st.session_state["mob_data"]   = load_all_data(selected_league, date_str)
                st.session_state["mob_league"] = selected_league
            except Exception as e:
                st.error(f"Hata: {e}")

    data = st.session_state.get("mob_data")

    if data is None:
        st.html("""
<div style="text-align:center;padding:60px 20px">
  <div style="font-size:44px;margin-bottom:16px;opacity:.35">🔮</div>
  <div style="font-size:16px;font-weight:700;color:#1e3a5f">Analiz için hazır</div>
  <div style="font-size:12px;color:#1a2f4e;margin-top:6px">Lig ve tarihi seçip Analiz Et'e bas</div>
</div>""")

    elif not data:
        st.warning(f"{selected_league} — bu tarihte maç yok.")

    else:
        sport = data[0]["sport"]
        st.html(f'<div style="padding:8px 16px 4px;font-size:11px;color:#2d4a66;'
                f'text-transform:uppercase;letter-spacing:1px;font-weight:700">'
                f'{len(data)} maç bulundu</div>')

        for d in data:
            m    = d["match"]
            pred = d["prediction"]
            odds = d["odds"]
            prob = pred["probabilities"]
            hl   = m.get("home_logo", "")
            al   = m.get("away_logo", "")

            ph   = round(prob["home"] * 100, 1)
            px   = round(prob.get("draw", 0) * 100, 1)
            pa   = round(prob["away"] * 100, 1)
            conf = pred["confidence"]
            conf_col = "#10b981" if conf >= 55 else "#f59e0b" if conf >= 45 else "#64748b"

            pred_lbl = {"1": "Ev", "2": "Dep", "X": "Beraberlik"}.get(pred["prediction"], pred["prediction"])
            pred_col = pred_colors.get(pred["prediction"], "#64748b")

            # Saat
            raw = m.get("match_time", "")
            try:
                from datetime import datetime as _dt
                if is_nba:
                    pts = raw.split(" ")[0].split("/")
                    time_str = f"{pts[1]}/{pts[0]}"
                else:
                    time_str = _dt.fromisoformat(raw[:16]).strftime("%H:%M")
            except Exception:
                time_str = ""

            exp_label = {
                "1": m["home_team"], "2": m["away_team"], "X": "Beraberlik"
            }.get(pred["prediction"], pred["prediction"])

            with st.expander(
                f"{m['home_team']}  vs  {m['away_team']}  ·  {pred_lbl}  %{conf}",
                expanded=False,
            ):
                # ── Maç özeti ─────────────────────────────────────────────────
                h_img = _logo_img(hl, 36, "8px")
                a_img = _logo_img(al, 36, "8px")
                st.html(f"""
<div style="padding:12px 0 10px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <div style="font-size:10px;color:#334155">{time_str}</div>
    <span style="background:{pred_col}22;color:{pred_col};border:1px solid {pred_col}44;
                 border-radius:6px;padding:3px 10px;font-size:12px;font-weight:700">{exp_label}</span>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:8px">
      {h_img}
      <span style="font-size:14px;font-weight:700;color:#f1f5f9">{m["home_team"]}</span>
    </div>
    <span style="font-size:12px;color:#1e3a5f;font-weight:600">vs</span>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="font-size:14px;font-weight:700;color:#f1f5f9">{m["away_team"]}</span>
      {a_img}
    </div>
  </div>
  <div style="background:#0a1526;border-radius:6px;height:6px;overflow:hidden;margin-bottom:4px">
    <div style="width:{conf}%;height:100%;background:{conf_col};border-radius:6px"></div>
  </div>
  <div style="font-size:11px;color:{conf_col};font-weight:700">%{conf} güven</div>
</div>""")

                # ── 1/X/2 olasılıkları ─────────────────────────────────────
                if not is_nba:
                    st.html(f"""
<div style="margin-bottom:12px">
  {_prob_bar("1 — Ev", ph, "#3b82f6")}
  {_prob_bar("X — Beraberlik", px, "#f59e0b")}
  {_prob_bar("2 — Deplasman", pa, "#ef4444")}
</div>""")
                else:
                    st.html(f"""
<div style="margin-bottom:12px">
  {_prob_bar(m["home_team"], ph, "#3b82f6")}
  {_prob_bar(m["away_team"], pa, "#ef4444")}
</div>""")

                # ── Metrikler (futbol) ─────────────────────────────────────
                if not is_nba:
                    _btts = pred.get("btts_prob", 0)
                    _o25  = pred.get("over25_prob", 0)
                    _o35  = pred.get("over35_prob", 0)
                    _kg   = "KG VAR ✓" if _btts >= 50 else "KG YOK ✗"
                    _kg_c = "#10b981" if _btts >= 50 else "#ef4444"
                    _o25c = "#10b981" if _o25 >= 52 else "#64748b"
                    _o35c = "#10b981" if _o35 >= 52 else "#64748b"
                    st.html(f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
  <div style="background:#060d1a;border:1px solid #0f1f38;border-radius:10px;padding:10px 12px">
    <div style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px">KG</div>
    <div style="font-size:15px;font-weight:800;color:{_kg_c}">{_kg}</div>
    <div style="font-size:10px;color:#334155;margin-top:3px">%{_btts} olasılık</div>
  </div>
  <div style="background:#060d1a;border:1px solid #0f1f38;border-radius:10px;padding:10px 12px">
    <div style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px">Üst 2.5</div>
    <div style="font-size:15px;font-weight:800;color:{_o25c}">%{_o25}</div>
    <div style="font-size:10px;color:#334155;margin-top:3px">Gol toplamı</div>
  </div>
  <div style="background:#060d1a;border:1px solid #0f1f38;border-radius:10px;padding:10px 12px">
    <div style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px">Üst 3.5</div>
    <div style="font-size:15px;font-weight:800;color:{_o35c}">%{_o35}</div>
    <div style="font-size:10px;color:#334155;margin-top:3px">Gol toplamı</div>
  </div>
  <div style="background:#060d1a;border:1px solid #0f1f38;border-radius:10px;padding:10px 12px">
    <div style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px">Beklenen Gol</div>
    <div style="font-size:15px;font-weight:800;color:#3b82f6">{pred.get("goal_prediction","—")}</div>
    <div style="font-size:10px;color:#334155;margin-top:3px">λ {pred.get("exp_total_goals","")}</div>
  </div>
</div>""")

                # ── NBA metrikleri ─────────────────────────────────────────
                if is_nba:
                    if d.get("home_b2b"): st.warning(f"⚠️ {m['home_team']} B2B")
                    if d.get("away_b2b"): st.warning(f"⚠️ {m['away_team']} B2B")

                # ── Oranlar ────────────────────────────────────────────────
                o_h = odds.get("home_win"); o_d = odds.get("draw"); o_a = odds.get("away_win")
                if o_h or o_a:
                    parts = []
                    if o_h: parts.append(f'<div style="text-align:center"><div style="font-size:9px;color:#1e3a5f;margin-bottom:3px">1</div><div style="font-size:14px;font-weight:700;color:#94a3b8">{o_h}</div></div>')
                    if o_d: parts.append(f'<div style="text-align:center"><div style="font-size:9px;color:#1e3a5f;margin-bottom:3px">X</div><div style="font-size:14px;font-weight:700;color:#94a3b8">{o_d}</div></div>')
                    if o_a: parts.append(f'<div style="text-align:center"><div style="font-size:9px;color:#1e3a5f;margin-bottom:3px">2</div><div style="font-size:14px;font-weight:700;color:#94a3b8">{o_a}</div></div>')
                    st.html(f"""
<div style="background:#060d1a;border:1px solid #0f1f38;border-radius:10px;
            padding:10px 16px;display:flex;justify-content:space-around;margin-bottom:12px">
  {''.join(parts)}
</div>""")

                # ── Form şeritleri ─────────────────────────────────────────
                hf = _form_strip(d["home_form"])
                af = _form_strip(d["away_form"])
                st.html(f"""
<div style="margin-top:4px">
  <div style="margin-bottom:8px">
    <div style="font-size:10px;color:#3a5070;text-transform:uppercase;letter-spacing:.8px;
                font-weight:700;margin-bottom:6px">{m["home_team"]} — Form</div>
    {hf}
  </div>
  <div>
    <div style="font-size:10px;color:#3a5070;text-transform:uppercase;letter-spacing:.8px;
                font-weight:700;margin-bottom:6px">{m["away_team"]} — Form</div>
    {af}
  </div>
</div>""")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SONUÇLAR
# ══════════════════════════════════════════════════════════════════════════════
with tab_sonuclar:
    st.html('<div style="padding:12px 16px 8px">')
    default_sc   = datetime.now(EASTERN_TZ if is_nba else TURKISH_TZ).date()
    sonuc_date   = st.date_input("Tarih", value=default_sc,
                                  format="DD/MM/YYYY", key="mob_sonuc_date")
    getir = st.button("📥  Getir", key="mob_btn_sonuc")
    st.html('</div>')

    if getir:
        date_str = sonuc_date.strftime("%m/%d/%Y") if is_nba else sonuc_date.strftime("%Y-%m-%d")
        with st.spinner("Sonuçlar yükleniyor..."):
            try:
                sc_data, sc_sport = load_results(selected_league, date_str)
                st.session_state["mob_sc_data"]  = sc_data
                st.session_state["mob_sc_sport"] = sc_sport
            except Exception as e:
                st.error(f"Hata: {e}")

    sc_data  = st.session_state.get("mob_sc_data")
    sc_sport = st.session_state.get("mob_sc_sport", "football")

    if sc_data is None:
        st.html("""
<div style="text-align:center;padding:60px 20px">
  <div style="font-size:44px;margin-bottom:16px;opacity:.35">📋</div>
  <div style="font-size:16px;font-weight:700;color:#1e3a5f">Sonuçları görmek için</div>
  <div style="font-size:12px;color:#1a2f4e;margin-top:6px">Tarih seçip Getir'e bas</div>
</div>""")
    elif not sc_data:
        st.warning("Bu tarihte sonuç bulunamadı.")
    else:
        for r in sc_data:
            hs = r.get("home_score", "")
            as_ = r.get("away_score", "")
            ht = r["home_team"]; at = r["away_team"]
            hl = r.get("home_logo", ""); al = r.get("away_logo", "")
            home_won = isinstance(hs, int) and isinstance(as_, int) and hs > as_
            away_won = isinstance(hs, int) and isinstance(as_, int) and as_ > hs

            h_bold = "font-weight:900;color:#f1f5f9" if home_won else "color:#334155"
            a_bold = "font-weight:900;color:#f1f5f9" if away_won else "color:#334155"
            h_img  = _logo_img(hl, 24, "6px")
            a_img  = _logo_img(al, 24, "6px")

            st.html(f"""
<div style="background:#080f1f;border:1px solid #0f1f38;border-radius:12px;
            padding:12px 14px;margin:0 0 8px;display:flex;
            align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:7px;flex:1;min-width:0">
    {h_img}
    <span style="font-size:13px;{h_bold};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{ht}</span>
  </div>
  <div style="text-align:center;padding:0 10px;flex-shrink:0">
    <span style="font-size:18px;font-weight:900;color:#f1f5f9">{hs}</span>
    <span style="font-size:14px;color:#334155;margin:0 4px">—</span>
    <span style="font-size:18px;font-weight:900;color:#f1f5f9">{as_}</span>
  </div>
  <div style="display:flex;align-items:center;gap:7px;flex:1;min-width:0;justify-content:flex-end">
    <span style="font-size:13px;{a_bold};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{at}</span>
    {a_img}
  </div>
</div>""")
