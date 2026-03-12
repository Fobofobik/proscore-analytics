"""
İddaa Tahmin Uygulaması — Streamlit Dashboard
Çalıştır: streamlit run app.py
"""
from __future__ import annotations

import base64
import os as _os
from datetime import datetime, date as date_type, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import LEAGUES
from engine.prediction import predict_match, calculate_form_score, calculate_goal_stats
from scrapers.sofascore_scraper import (
    get_upcoming_matches, get_team_form, get_h2h,
    get_team_season_stats, get_results_by_date,
    get_league_standings,
)
from scrapers.nba_scraper import (
    get_upcoming_nba_matches, get_nba_team_form,
    get_nba_injuries, get_nba_h2h,
    get_nba_team_ratings, get_nba_back_to_back, get_nba_load_management,
    get_nba_travel_penalty, get_all_nba_team_ratings,
    get_nba_results_by_date, get_nba_box_score,
)
from scrapers.odds_scraper import get_odds, match_odds

# ── Sayfa ayarları ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ProScore Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Logo base64 ────────────────────────────────────────────────────────────────
_logo_path = _os.path.join(_os.path.dirname(__file__), 'logo.png')
with open(_logo_path, 'rb') as _f:
    _logo_b64 = base64.b64encode(_f.read()).decode()

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Base ── */
html, body, .stApp {
    background: #060d1a !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #e2e8f0 !important;
}

.main .block-container {
    padding: 2rem 2.5rem !important;
    max-width: 1400px !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #080f1f !important;
    border-right: 1px solid #0f1f38 !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}


/* ── Expanders ── */
[data-testid="stExpander"] {
    background: #0b1628 !important;
    border: 1px solid #132035 !important;
    border-radius: 16px !important;
    overflow: hidden !important;
    margin-bottom: 10px !important;
}
[data-testid="stExpander"] summary {
    background: #0b1628 !important;
    padding: 14px 20px !important;
    color: #e2e8f0 !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}
[data-testid="stExpander"] summary:hover {
    background: #0f1f38 !important;
}
[data-testid="stExpander"] > details > div {
    background: #0b1628 !important;
    padding: 0 20px 16px !important;
}

/* ── Plotly charts ── */
.js-plotly-plot .plotly .bg {
    fill: transparent !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    background: #0b1628 !important;
    border-radius: 12px !important;
    border: 1px solid #132035 !important;
}
.stDataFrame th {
    background: #0f1f38 !important;
    color: #64748b !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: .6px !important;
}
.stDataFrame td {
    color: #cbd5e1 !important;
    font-size: 13px !important;
}

/* ── Progress columns ── */
[data-testid="stProgressColumn"] {
    color: #3b82f6 !important;
}

/* ── Divider ── */
hr {
    border-color: #0f1f38 !important;
    margin: 18px 0 !important;
}

/* ── Spinner ── */
.stSpinner > div {
    border-top-color: #3b82f6 !important;
}

/* ── Warnings / Errors ── */
[data-testid="stAlert"] {
    background: #1a1a2e !important;
    border-radius: 10px !important;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
    background: #0f1929 !important;
    border: 1px solid #1a2f4e !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    padding-left: 48px !important;
}

/* ── Sidebar header ── */
.sidebar-logo-wrapper {
    padding: 22px 20px 18px;
    margin: -1rem -1rem 0 -1rem;
    border-bottom: 1px solid #0f1f38;
}

/* ── Nav etiketleri ── */
.sb-sep { border:none; border-top:1px solid #111d2e; margin:12px 0; }
.sb-label {
    font-size: 10px; color: #3a5070; text-transform: uppercase;
    letter-spacing: 1.6px; font-weight: 700; padding: 0 2px; margin: 18px 0 6px;
}

/* ── Sidebar footer ── */
.sidebar-footer { font-size:11px; color:#253a52; text-align:center; padding:14px 0 4px; }

/* ── Nav butonları — profesyonel sol-çizgi stili ── */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    border-radius: 0 8px 8px 0 !important;
    color: #4a6580 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 10px 16px !important;
    text-align: left !important;
    width: 100% !important;
    transition: all .15s !important;
    letter-spacing: .2px !important;
    margin-left: -4px !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #0d1e33 !important;
    color: #94b4cc !important;
    border-left: 3px solid #1e40af60 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #0d1e33 !important;
    color: #93c5fd !important;
    font-weight: 600 !important;
    border-left: 3px solid #3b82f6 !important;
}

/* Selectbox logo badge */
[data-testid="stSelectbox"] > div > div::before {
    content: ''; position: absolute; left: 12px; top: 50%;
    transform: translateY(-50%); width: 24px; height: 24px;
    border-radius: 6px; background-size: 18px 18px;
    background-position: center; background-repeat: no-repeat; z-index: 1;
    pointer-events: none;
}
</style>
""", unsafe_allow_html=True)

# ── Zaman dilimleri ────────────────────────────────────────────────────────────
EASTERN_TZ = timezone(timedelta(hours=-5))
TURKISH_TZ  = timezone(timedelta(hours=3))

# ── Sidebar ────────────────────────────────────────────────────────────────────
if "section" not in st.session_state:
    st.session_state["section"] = "tahmin"

with st.sidebar:
    st.markdown("""
<div class="sidebar-logo-wrapper">
  <div style="line-height:1.15;">
    <span style="font-size:22px;font-weight:900;color:#e2e8f0;letter-spacing:-.5px;">Pro</span><span style="font-size:22px;font-weight:900;color:#3b82f6;letter-spacing:-.5px;">Score</span>
  </div>
  <div style="font-size:9.5px;color:#2d4a66;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-top:4px;">Analytics</div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    _sec = st.session_state["section"]
    if st.button("Tahmin", use_container_width=True,
                 type="primary" if _sec == "tahmin" else "secondary", key="nav_tahmin"):
        st.session_state["section"] = "tahmin"; st.rerun()
    if st.button("Sonuçlar", use_container_width=True,
                 type="primary" if _sec == "sonuclar" else "secondary", key="nav_sonuclar"):
        st.session_state["section"] = "sonuclar"; st.rerun()

    st.markdown('<hr class="sb-sep"><div class="sb-label">Lig Seçimi</div>', unsafe_allow_html=True)

    selected_league = st.selectbox("Lig seçin:", list(LEAGUES.keys()),
                                   label_visibility="collapsed", key="_league_selectbox")
    league_cfg = LEAGUES[selected_league]
    is_nba     = league_cfg["sport"] == "nba"
    _sb_logo   = league_cfg.get("logo", "")
    _badge_bg  = "#17408b" if is_nba else "#ffffff"
    _logo_size = "20px"    if is_nba else "18px"
    st.markdown(f"""
<style>
[data-testid="stSelectbox"] > div > div::before {{
    background-color: {_badge_bg};
    background-image: url({_sb_logo});
    background-size: {_logo_size} {_logo_size};
}}
</style>""", unsafe_allow_html=True)

    st.markdown('<hr class="sb-sep">', unsafe_allow_html=True)
    if st.button("Verileri Yenile", use_container_width=True, key="btn_refresh"):
        import shutil, os
        if os.path.exists("data"): shutil.rmtree("data")
        os.makedirs("data", exist_ok=True)
        st.cache_data.clear(); st.rerun()

    st.markdown(f"""
<div class="sidebar-footer">
  Önbellek 30 dk &nbsp;·&nbsp; {datetime.now().strftime('%H:%M')}
</div>""", unsafe_allow_html=True)


# ── HTML yardımcı bileşenler ───────────────────────────────────────────────────

def _logo_img(url: str, size: int = 22, radius: str = "50%") -> str:
    if not url: return ""
    return (f'<img src="{url}" width="{size}" height="{size}" '
            f'style="vertical-align:middle;border-radius:{radius};flex-shrink:0">')

def _section_header(title: str, icon: str = "") -> str:
    return (f'<div style="display:flex;align-items:center;gap:8px;margin:20px 0 12px">'
            f'<span style="font-size:13px">{icon}</span>'
            f'<span style="font-size:13px;font-weight:700;color:#94a3b8;text-transform:uppercase;'
            f'letter-spacing:1.2px">{title}</span>'
            f'<div style="flex:1;height:1px;background:#0f1f38;margin-left:8px"></div></div>')

def _metric_card(label: str, value: str, sub: str = "",
                 accent: str = "#3b82f6", glow: bool = False) -> str:
    glow_css = f"box-shadow:0 0 18px {accent}22;" if glow else ""
    sub_html = f'<div style="font-size:11px;color:#334155;margin-top:6px">{sub}</div>' if sub else ""
    return (f'<div style="background:#0b1628;border:1px solid #132035;border-radius:14px;'
            f'padding:16px 18px;{glow_css}">'
            f'<div style="font-size:10px;color:#475569;text-transform:uppercase;letter-spacing:1.1px;'
            f'margin-bottom:10px;font-weight:700">{label}</div>'
            f'<div style="font-size:22px;font-weight:800;color:{accent};line-height:1.1">{value}</div>'
            f'{sub_html}'
            f'</div>')

def _badge(text: str, color: str = "#3b82f6") -> str:
    return (f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
            f'border-radius:6px;padding:3px 10px;font-size:12px;font-weight:700;'
            f'letter-spacing:.3px">{text}</span>')

def _team_row(name: str, logo_url: str, side: str = "home") -> str:
    img = _logo_img(logo_url, size=28, radius="8px")
    flex = "flex-end" if side == "home" else "flex-start"
    return (f'<div style="display:flex;align-items:center;gap:10px;justify-content:{flex}">'
            f'{"" if side == "away" else img}'
            f'<span style="font-size:15px;font-weight:700;color:#f1f5f9">{name}</span>'
            f'{img if side == "away" else ""}'
            f'</div>')

def _normalize(name: str) -> str:
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return name.lower().translate(tr_map).replace(" ", "_")


def _render_form_strip(form: list[dict]) -> str:
    """Form geçmişini mini renkli kutucuk şeridine dönüştürür."""
    if not form: return '<span style="color:#334155;font-size:12px">Veri yok</span>'
    colors = {"W": "#10b981", "D": "#f59e0b", "L": "#ef4444"}
    labels = {"W": "G", "D": "B", "L": "M"}
    recent = list(reversed(form))
    boxes  = ""
    for m in recent:
        r   = m.get("result", "?")
        c   = colors.get(r, "#334155")
        lbl = labels.get(r, "?")
        score = m.get("score", "")
        date_ = m.get("date", "")
        ht = m.get("home_team",""); at = m.get("away_team","")
        tip = f"{ht} {score} {at} ({date_})"
        boxes += (f'<div title="{tip}" style="width:32px;height:32px;background:{c}22;'
                  f'border:2px solid {c};border-radius:8px;display:flex;align-items:center;'
                  f'justify-content:center;font-size:13px;font-weight:900;color:{c};'
                  f'cursor:default;flex-shrink:0">{lbl}</div>')
    return f'<div style="display:flex;gap:5px;align-items:center">{boxes}</div>'


def _render_form_chart_html(form: list[dict], trend: dict) -> None:
    """Form şeridini + trend badge'ini Streamlit'e yazar."""
    strip = _render_form_strip(form)
    t = trend.get("trend", "➡ Stabil")
    tc = "#10b981" if "Yükselen" in t else "#ef4444" if "Düşen" in t else "#64748b"
    l3 = trend.get("last3", 0); l6 = trend.get("last6", 0)
    trend_html = (f'<div style="display:flex;align-items:center;gap:8px;margin-top:8px">'
                  f'<span style="font-size:13px;font-weight:700;color:{tc}">{t}</span>'
                  f'<span style="font-size:11px;color:#334155">Son3: %{l3}</span>'
                  f'<span style="font-size:11px;color:#1e3a5f">·</span>'
                  f'<span style="font-size:11px;color:#334155">Son6: %{l6}</span>'
                  f'</div>')
    st.markdown(f'<div style="padding:4px 0 10px">{strip}{trend_html}</div>',
                unsafe_allow_html=True)


def _render_nba_box_score(box, home_team, away_team, home_logo="", away_logo=""):
    if box.get("error"):
        st.error(f"Box score yüklenemedi: {box['error']}")
    col_h, col_a = st.columns(2)
    def _player_table(players, title, logo, col):
        with col:
            st.markdown(f'<div style="font-size:13px;font-weight:700;color:#94a3b8;'
                        f'margin-bottom:8px">{_logo_img(logo,18,"4px")} {title}</div>',
                        unsafe_allow_html=True)
            if not players: st.info("Oyuncu verisi yok."); return
            sorted_p = sorted(players, key=lambda p: -int(p["min"].split(":")[0]) if ":" in p["min"] else -int(p["min"] or 0))
            rows = []
            for p in sorted_p:
                pm = p["plus_minus"]
                rows.append({"Oyuncu": p["name"], "Dk": p["min"], "Sayı": p["pts"],
                             "Rib": p["reb"], "Ast": p["ast"], "Sti": p["stl"],
                             "Blk": p["blk"], "İsabet": p["fg"], "3P": p["fg3"],
                             "+/-": f"+{pm}" if pm > 0 else str(pm)})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    _player_table(box.get("home", []), home_team, home_logo, col_h)
    _player_table(box.get("away", []), away_team, away_logo, col_a)


# ── Veri yükleme ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def load_all_data(league_name: str, date_str: str | None = None):
    cfg   = LEAGUES[league_name]
    sport = cfg["sport"]
    with st.spinner("💰 Oranlar çekiliyor..."):
        raw_odds = get_odds(league_name)
    odds_lookup = raw_odds
    if sport == "nba":
        with st.spinner("🏀 NBA maçları yükleniyor..."):
            upcoming = get_upcoming_nba_matches(date_str=date_str)
        form_fn  = get_nba_team_form
        h2h_fn   = get_nba_h2h
    else:
        with st.spinner("📡 Maç verileri çekiliyor..."):
            upcoming = get_upcoming_matches(league_id=cfg["id"], season=cfg["season"], date=date_str)
        form_fn = lambda tid, tnm: get_team_form(tid, tnm, cfg["id"], cfg["season"])
        h2h_fn  = lambda hid, aid: get_h2h(hid, aid, cfg["id"])

    results = []
    for match in upcoming:
        home_id   = match["home_team_id"]
        away_id   = match["away_team_id"]
        home_name = match["home_team"]
        away_name = match["away_team"]
        with st.spinner(f"🔍 {home_name} vs {away_name} analiz ediliyor..."):
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
                home_season  = away_season = {}
                # Seyahat yorgunluğu: form zaten yüklendi, ev sahibi bilgisi maçtan alınır
                home_travel  = get_nba_travel_penalty(home_name, home_form, True,  away_name)
                away_travel  = get_nba_travel_penalty(away_name, away_form, False, home_name)
                home_standing = away_standing = None
            else:
                home_ratings = away_ratings = {}
                home_load    = away_load    = []
                home_b2b     = away_b2b     = False
                home_travel  = away_travel  = 0.0
                home_season  = get_team_season_stats(home_id, home_name, cfg["id"], cfg["season"])
                away_season  = get_team_season_stats(away_id, away_name, cfg["id"], cfg["season"])
                # Lig sıralaması (motivasyon)
                standings     = get_league_standings(cfg["id"])
                home_standing = standings.get(home_id)
                away_standing = standings.get(away_id)

        odds = match_odds(odds_lookup, home_name, away_name)
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
            "match": match, "home_form": home_form, "away_form": away_form,
            "h2h": h2h, "odds": odds, "prediction": pred, "sport": sport,
            "home_ratings": home_ratings if sport == "nba" else {},
            "away_ratings": away_ratings if sport == "nba" else {},
            "home_load": home_load if sport == "nba" else [],
            "away_load": away_load if sport == "nba" else [],
            "home_b2b": home_b2b if sport == "nba" else False,
            "away_b2b": away_b2b if sport == "nba" else False,
        })
    return results


# ══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 1 — Tahmin
# ══════════════════════════════════════════════════════════════════════════════
if _sec == "tahmin":

    if is_nba:
        default_tahmin = datetime.now(EASTERN_TZ).date()
        date_label = "Tarih (ABD Doğu)"
    else:
        default_tahmin = datetime.now(TURKISH_TZ).date()
        date_label = "Tarih (TR)"

    # ── Başlık satırı ─────────────────────────────────────────────────────────
    _lig_logo = league_cfg.get("logo", "")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:24px">'
        f'{_logo_img(_lig_logo, 40, "10px")}'
        f'<div>'
        f'<div style="font-size:24px;font-weight:900;color:#f1f5f9;letter-spacing:-.3px">{selected_league}</div>'
        f'<div style="font-size:12px;color:#334155;font-weight:600;letter-spacing:.8px;text-transform:uppercase">Maç Tahmin Analizi</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    col_date, col_btn = st.columns([4, 1])
    with col_date:
        tahmin_date = st.date_input(date_label, value=default_tahmin, format="DD/MM/YYYY", key="tahmin_date_input")
    with col_btn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        sorgula = st.button("🔍  Analiz Et", type="primary", use_container_width=True, key="btn_tahmin")

    if sorgula:
        tahmin_date_str = tahmin_date.strftime("%m/%d/%Y") if is_nba else tahmin_date.strftime("%Y-%m-%d")
        if tahmin_date == default_tahmin:
            tahmin_date_str = None
        try:
            st.session_state["tahmin_data"]   = load_all_data(selected_league, tahmin_date_str)
            st.session_state["tahmin_league"] = selected_league
        except Exception as e:
            st.error(f"Veri yükleme hatası: {e}")

    data = st.session_state.get("tahmin_data")

    if data is None:
        st.markdown("""
<div style="text-align:center;padding:80px 20px">
  <div style="font-size:56px;margin-bottom:20px;opacity:.4">🔮</div>
  <div style="font-size:20px;font-weight:700;color:#1e3a5f;margin-bottom:8px">Analiz için hazır</div>
  <div style="font-size:14px;color:#1a2f4e">Lig ve tarih seçtikten sonra <b style="color:#2563eb">Analiz Et</b> butonuna basın.</div>
</div>""", unsafe_allow_html=True)

    elif not data:
        st.warning(f"{selected_league} — bu tarihte programlanmış maç bulunamadı.")

    else:
        sport       = data[0]["sport"]
        is_nba_data = sport == "nba"

        # ── Özet kart tablosu ─────────────────────────────────────────────────
        pred_colors = {"1": "#3b82f6", "X": "#f59e0b", "2": "#ef4444"}

        rows_html = ""
        for d in data:
            m    = d["match"]
            pred = d["prediction"]
            odds = d["odds"]
            p    = pred["probabilities"]
            hl   = m.get("home_logo", "")
            al   = m.get("away_logo", "")

            pred_lbl = {"1": m["home_team"], "2": m["away_team"], "X": "Beraberlik"}.get(pred["prediction"], pred["prediction"])
            pred_col = pred_colors.get(pred["prediction"], "#64748b")
            conf     = pred["confidence"]
            conf_col = "#10b981" if conf >= 55 else "#f59e0b" if conf >= 45 else "#64748b"

            if is_nba_data:
                raw = m["match_time"].split(" ")[0] if m.get("match_time") else ""
                try:
                    pts = raw.split("/"); time_str = f"{pts[1]}/{pts[0]}/{pts[2]}"
                except Exception:
                    time_str = raw
            else:
                raw = m.get("match_time", "")
                try:
                    from datetime import datetime as _dt
                    time_str = _dt.fromisoformat(raw[:16]).strftime("%d/%m %H:%M")
                except Exception:
                    time_str = raw[:16].replace("T", " ")

            h_img = _logo_img(hl, 20, "6px")
            a_img = _logo_img(al, 20, "6px")
            o_home = odds.get("home_win", "—"); o_draw = odds.get("draw", "—"); o_away = odds.get("away_win", "—")

            rows_html += f"""
<tr style="border-bottom:1px solid #0f1f38;transition:background .15s" onmouseover="this.style.background='#0d1e35'" onmouseout="this.style.background='transparent'">
  <td style="padding:12px 14px;color:#475569;font-size:12px;white-space:nowrap">{time_str}</td>
  <td style="padding:12px 14px">
    <div style="display:flex;align-items:center;gap:8px">
      {h_img}<span style="color:#e2e8f0;font-weight:600;font-size:13px">{m["home_team"]}</span>
      <span style="color:#1e3a5f;font-size:11px;margin:0 4px">vs</span>
      {a_img}<span style="color:#e2e8f0;font-weight:600;font-size:13px">{m["away_team"]}</span>
    </div>
  </td>
  <td style="padding:12px 14px;text-align:center;color:#334155;font-size:12px">{o_home}</td>
  <td style="padding:12px 14px;text-align:center;color:#334155;font-size:12px">{o_draw}</td>
  <td style="padding:12px 14px;text-align:center;color:#334155;font-size:12px">{o_away}</td>
  <td style="padding:12px 14px;text-align:center">
    <span style="background:{pred_col}22;color:{pred_col};border:1px solid {pred_col}44;
                 border-radius:8px;padding:4px 12px;font-size:12px;font-weight:700">{pred_lbl}</span>
  </td>
  <td style="padding:12px 16px;min-width:120px">
    <div style="background:#0a1526;border-radius:6px;height:6px;overflow:hidden">
      <div style="width:{conf}%;height:100%;background:{conf_col};border-radius:6px;transition:width .6s"></div>
    </div>
    <div style="font-size:11px;color:{conf_col};margin-top:4px;font-weight:700">%{conf}</div>
  </td>
</tr>"""

        header_cols = ("Saat", "Maç", "1", "X", "2", "Tahmin", "Güven") if not is_nba_data else ("Tarih", "Maç", "", "", "", "Tahmin", "Güven")
        th_html = "".join(
            f'<th style="padding:10px 14px;text-align:{"center" if i > 1 else "left"};'
            f'color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.8px;white-space:nowrap">{h}</th>'
            for i, h in enumerate(header_cols)
        )

        st.markdown(f"""
<div style="background:#080f1f;border:1px solid #0f1f38;border-radius:16px;overflow:hidden;margin-bottom:24px">
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:#0a1526">{th_html}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>""", unsafe_allow_html=True)

        # ── Her maç için detay kartı ──────────────────────────────────────────
        for d in data:
            m         = d["match"]
            pred      = d["prediction"]
            odds      = d["odds"]
            home_form = d["home_form"]
            away_form = d["away_form"]
            prob      = pred["probabilities"]

            exp_pred  = {"1": m["home_team"], "2": m["away_team"], "X": "Beraberlik"}.get(pred["prediction"], pred["prediction"])
            pred_col  = pred_colors.get(pred["prediction"], "#64748b")

            _hl = m.get("home_logo", "")
            _al = m.get("away_logo", "")
            sport_icon = "🏀" if is_nba_data else "⚽"

            with st.expander(
                f"{sport_icon}  {m['home_team']}  vs  {m['away_team']}   —   "
                f"{exp_pred}   ·   %{pred['confidence']} güven",
                expanded=False,
            ):
                # ── Maç başlığı ──────────────────────────────────────────────
                ph = round(prob["home"] * 100, 1)
                px = round(prob.get("draw", 0) * 100, 1)
                pa = round(prob["away"] * 100, 1)

                st.markdown(f"""
<div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:16px;
            padding:20px 4px 16px;border-bottom:1px solid #0f1f38;margin-bottom:20px">
  <div style="display:flex;align-items:center;justify-content:flex-end;gap:12px">
    {_logo_img(_hl, 44, "12px")}
    <div style="text-align:right">
      <div style="font-size:17px;font-weight:800;color:#f1f5f9">{m["home_team"]}</div>
      <div style="font-size:12px;color:#334155;margin-top:2px">Ev Sahibi</div>
    </div>
  </div>
  <div style="text-align:center;padding:0 16px">
    <div style="font-size:11px;color:#1e3a5f;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Tahmin</div>
    <div style="background:{pred_col}22;border:1px solid {pred_col}55;border-radius:10px;
                padding:8px 20px;font-size:16px;font-weight:900;color:{pred_col}">{exp_pred}</div>
    <div style="font-size:11px;color:#334155;margin-top:6px">%{pred['confidence']} güven</div>
  </div>
  <div style="display:flex;align-items:center;gap:12px">
    <div style="text-align:left">
      <div style="font-size:17px;font-weight:800;color:#f1f5f9">{m["away_team"]}</div>
      <div style="font-size:12px;color:#334155;margin-top:2px">Deplasman</div>
    </div>
    {_logo_img(_al, 44, "12px")}
  </div>
</div>
""", unsafe_allow_html=True)

                # B2B uyarısı NBA
                if is_nba_data:
                    alerts = []
                    if d.get("home_b2b"): alerts.append(f"⚠️ {m['home_team']} dün maç oynadı")
                    if d.get("away_b2b"): alerts.append(f"⚠️ {m['away_team']} dün maç oynadı")
                    if alerts: st.warning("  ·  ".join(alerts))

                if not is_nba_data:
                    # ── Metrik satırı 1 ──────────────────────────────────────
                    _btts  = pred.get("btts_prob", 0)
                    _kg    = "KG VAR ✓" if _btts >= 50 else "KG YOK ✗"
                    _kg_c  = "#10b981" if _btts >= 50 else "#ef4444"
                    _o25   = pred.get("over25_prob", 0)
                    _o35   = pred.get("over35_prob", 0)
                    _o25c  = "#10b981" if _o25 >= 52 else "#64748b"
                    _o35c  = "#10b981" if _o35 >= 52 else "#64748b"
                    _hr    = pred.get("home_rest_days")
                    _ar    = pred.get("away_rest_days")

                    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                    mc1.markdown(_metric_card("Gol Tahmini", pred["goal_prediction"],
                                              f"λ {pred['exp_total_goals']} beklenen", "#3b82f6"), unsafe_allow_html=True)
                    mc2.markdown(_metric_card("KG VAR/YOK", _kg, f"%{_btts} olasılık", _kg_c, glow=True), unsafe_allow_html=True)
                    mc3.markdown(_metric_card("Üst 2.5", f"%{_o25}", "Gol toplamı", _o25c), unsafe_allow_html=True)
                    mc4.markdown(_metric_card("Üst 3.5", f"%{_o35}", "Gol toplamı", _o35c), unsafe_allow_html=True)
                    mc5.markdown(_metric_card("Dinlenme", f"{_hr or '?'} / {_ar or '?'}",
                                              "Ev / Dep gün", "#64748b"), unsafe_allow_html=True)
                    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

                else:
                    mc1, mc2 = st.columns(2)
                    mc1.markdown(_metric_card("Tahmin", exp_pred, "", pred_col, glow=True), unsafe_allow_html=True)
                    mc2.markdown(_metric_card("Güven", f"%{pred['confidence']}", "", "#3b82f6"), unsafe_allow_html=True)
                    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

                # ── İki sütunlu alan ─────────────────────────────────────────
                col_left, col_right = st.columns([1, 1])

                with col_left:
                    # Olasılık barı (futbol)
                    if not is_nba_data:
                        st.markdown(_section_header("1 / X / 2 Olasılıkları", "📊"), unsafe_allow_html=True)
                        fig = go.Figure()
                        cats = ["Ev (1)", "Beraberlik (X)", "Deplasman (2)"]
                        vals = [ph, px, pa]
                        colrs = ["#3b82f6", "#f59e0b", "#ef4444"]
                        def _hex_to_rgba(h: str, a: float) -> str:
                            r, g, b = int(h[1:3],16), int(h[3:5],16), int(h[5:7],16)
                            return f"rgba({r},{g},{b},{a})"
                        fig.add_trace(go.Bar(
                            x=cats, y=vals,
                            marker=dict(color=colrs,
                                        line=dict(color=[_hex_to_rgba(c, 0.4) for c in colrs], width=1)),
                            text=[f"%{v}" for v in vals], textposition="outside",
                            textfont=dict(size=14, color="#f1f5f9", family="Inter"),
                        ))
                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            yaxis=dict(range=[0, 100], gridcolor="#0f1f38", tickfont=dict(color="#334155"), ticksuffix="%"),
                            xaxis=dict(tickfont=dict(color="#94a3b8", size=12)),
                            showlegend=False, margin=dict(t=20, b=10, l=0, r=0), height=230,
                            font=dict(family="Inter"),
                        )
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                        # Oran vs Tahmin
                        if any(odds.get(k) for k in ["home_win", "draw", "away_win"]):
                            st.markdown(_section_header("Piyasa vs Tahminimiz", "⚖️"), unsafe_allow_html=True)
                            labels2, bil_probs2, our_probs2 = [], [], []
                            for lbl, ok, op in [("1","home_win",prob["home"]),("X","draw",prob.get("draw",0)),("2","away_win",prob["away"])]:
                                odd = odds.get(ok)
                                if odd and odd > 1:
                                    labels2.append(lbl); bil_probs2.append(round(100/odd, 1))
                                    our_probs2.append(round(op*100, 1))
                            if labels2:
                                fig2 = go.Figure()
                                fig2.add_trace(go.Bar(name="Piyasa", x=labels2, y=bil_probs2,
                                                      marker_color="rgba(99,102,241,0.13)", marker_line_color="#6366f1",
                                                      marker_line_width=1,
                                                      text=[f"%{v}" for v in bil_probs2], textposition="outside",
                                                      textfont=dict(color="#6366f1", size=12)))
                                fig2.add_trace(go.Bar(name="Tahminimiz", x=labels2, y=our_probs2,
                                                      marker_color="rgba(16,185,129,0.13)", marker_line_color="#10b981",
                                                      marker_line_width=1,
                                                      text=[f"%{v}" for v in our_probs2], textposition="outside",
                                                      textfont=dict(color="#10b981", size=12)))
                                fig2.update_layout(
                                    barmode="group", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                    yaxis=dict(range=[0,100], gridcolor="#0f1f38", tickfont=dict(color="#334155"), ticksuffix="%"),
                                    xaxis=dict(tickfont=dict(color="#94a3b8", size=13)),
                                    legend=dict(font=dict(color="#64748b", size=11), bgcolor="rgba(0,0,0,0)"),
                                    margin=dict(t=20, b=10, l=0, r=0), height=200, font=dict(family="Inter"),
                                )
                                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

                    else:
                        # NBA olasılık barı
                        st.markdown(_section_header("Kazanma Olasılığı", "📊"), unsafe_allow_html=True)
                        h_bold = "font-weight:900;" if ph >= pa else "opacity:.55;"
                        a_bold = "font-weight:900;" if pa > ph  else "opacity:.55;"
                        st.markdown(f"""
<div style="padding:4px 0 16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div style="display:flex;align-items:center;gap:8px">{_logo_img(_hl,24,"6px")}
      <span style="font-size:14px;color:#e2e8f0;{h_bold}">{m["home_team"]}</span></div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="font-size:14px;color:#e2e8f0;{a_bold}">{m["away_team"]}</span>{_logo_img(_al,24,"6px")}</div>
  </div>
  <div style="position:relative;height:24px;border-radius:12px;overflow:hidden;background:#0a1526">
    <div style="position:absolute;left:0;top:0;height:100%;width:{ph}%;background:linear-gradient(90deg,#1d4ed8,#3b82f6);border-radius:12px 0 0 12px"></div>
    <div style="position:absolute;right:0;top:0;height:100%;width:{pa}%;background:linear-gradient(270deg,#991b1b,#ef4444);border-radius:0 12px 12px 0"></div>
    <div style="position:absolute;inset:0;display:flex;justify-content:space-between;align-items:center;padding:0 12px">
      <span style="font-size:13px;font-weight:900;color:#fff">%{ph}</span>
      <span style="font-size:13px;font-weight:900;color:#fff">%{pa}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

                with col_right:
                    st.markdown(_section_header(f"{m['home_team']} — Son Form", "📋"), unsafe_allow_html=True)
                    _render_form_chart_html(home_form, pred.get("home_form_trend", {}))
                    st.markdown(_section_header(f"{m['away_team']} — Son Form", "📋"), unsafe_allow_html=True)
                    _render_form_chart_html(away_form, pred.get("away_form_trend", {}))

                # ── Skor matrisi (futbol) ─────────────────────────────────────
                if not is_nba_data:
                    correct_scores = pred.get("correct_scores", [])
                    if correct_scores:
                        st.markdown(_section_header("En Olası Skorlar (Poisson)", "🎯"), unsafe_allow_html=True)
                        max_prob = max((cs["prob"] for cs in correct_scores), default=1)
                        cs_html = ""
                        for idx, cs in enumerate(correct_scores):
                            intensity = cs["prob"] / max_prob
                            bg = f"rgba(37,99,235,{intensity * 0.35:.2f})"
                            brd = f"rgba(59,130,246,{intensity * 0.6:.2f})"
                            rank_badge = ' <span style="font-size:9px;background:#2563eb;color:#fff;border-radius:4px;padding:1px 5px;vertical-align:middle">TOP</span>' if idx == 0 else ""
                            cs_html += (
                                f'<div style="background:{bg};border:1px solid {brd};border-radius:12px;'
                                f'padding:14px 8px;text-align:center">'
                                f'<div style="font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:2px">{cs["score"]}{rank_badge}</div>'
                                f'<div style="font-size:12px;color:#475569;margin-top:6px;font-weight:600">%{cs["prob"]}</div>'
                                f'</div>'
                            )
                        st.markdown(
                            f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:4px">{cs_html}</div>',
                            unsafe_allow_html=True,
                        )

                # ── Value Bet ─────────────────────────────────────────────────
                vbets = pred.get("value_bets", [])
                if vbets:
                    st.markdown(_section_header("Value Bet Fırsatları", "💰"), unsafe_allow_html=True)
                    for vb in vbets:
                        edge_w = min(100, int(vb["edge"] * 3))
                        st.markdown(f"""
<div style="background:#051a0f;border:1px solid #14532d;border-radius:12px;padding:14px 18px;margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
    <div>
      <span style="font-size:15px;font-weight:800;color:#4ade80">{vb["market"]}</span>
      <span style="font-size:12px;color:#166534;margin-left:10px">Oran: <b style="color:#86efac">{vb["odd"]}</b></span>
    </div>
    <div style="display:flex;gap:20px;align-items:center">
      <div style="text-align:center">
        <div style="font-size:10px;color:#166534;text-transform:uppercase;letter-spacing:.8px">Tahminimiz</div>
        <div style="font-size:18px;font-weight:800;color:#4ade80">%{vb["our_prob"]}</div>
      </div>
      <div style="text-align:center">
        <div style="font-size:10px;color:#166534;text-transform:uppercase;letter-spacing:.8px">Piyasa</div>
        <div style="font-size:18px;font-weight:800;color:#64748b">%{vb["implied_prob"]}</div>
      </div>
      <div style="text-align:center">
        <div style="font-size:10px;color:#166534;text-transform:uppercase;letter-spacing:.8px">Avantaj</div>
        <div style="font-size:18px;font-weight:800;color:#10b981">+%{vb["edge"]}</div>
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

                # ── NBA gelişmiş istatistikler ─────────────────────────────────
                if is_nba_data:
                    h_rtg = d.get("home_ratings", {}); a_rtg = d.get("away_ratings", {})
                    if h_rtg or a_rtg:
                        st.markdown(_section_header("Gelişmiş İstatistikler", "📈"), unsafe_allow_html=True)
                        rtg_c1, rtg_c2 = st.columns(2)
                        for col_, rtg, name, logo in [(rtg_c1, h_rtg, m["home_team"], _hl), (rtg_c2, a_rtg, m["away_team"], _al)]:
                            with col_:
                                st.markdown(f'<div style="font-size:13px;font-weight:700;color:#64748b;margin-bottom:10px">{_logo_img(logo,16,"4px")} {name}</div>', unsafe_allow_html=True)
                                if rtg:
                                    r1,r2,r3,r4 = st.columns(4)
                                    r1.markdown(_metric_card("OffRtg", f"{rtg.get('off_rtg',0):.1f}" if rtg.get('off_rtg') else "—","","#3b82f6"), unsafe_allow_html=True)
                                    r2.markdown(_metric_card("DefRtg", f"{rtg.get('def_rtg',0):.1f}" if rtg.get('def_rtg') else "—","","#ef4444"), unsafe_allow_html=True)
                                    r3.markdown(_metric_card("NetRtg", f"{rtg.get('net_rtg',0):.1f}" if rtg.get('net_rtg') else "—","","#10b981"), unsafe_allow_html=True)
                                    r4.markdown(_metric_card("Pace",   f"{rtg.get('pace',0):.1f}"   if rtg.get('pace')   else "—","","#f59e0b"), unsafe_allow_html=True)

                    home_load_data = d.get("home_load", [])
                    away_load_data = d.get("away_load", [])
                    if home_load_data or away_load_data:
                        st.markdown(_section_header("Load Management", "⏱"), unsafe_allow_html=True)
                        lc1, lc2 = st.columns(2)
                        for col_, ld, name, logo in [(lc1, home_load_data, m["home_team"], _hl), (lc2, away_load_data, m["away_team"], _al)]:
                            with col_:
                                st.markdown(f'<div style="font-size:12px;font-weight:700;color:#64748b;margin-bottom:8px">{_logo_img(logo,16,"4px")} {name}</div>', unsafe_allow_html=True)
                                if ld:
                                    st.dataframe(pd.DataFrame(ld)[["name","season_min","last5_min","flag"]].rename(columns={"name":"Oyuncu","season_min":"Sezon Dk","last5_min":"Son5 Dk","flag":"Uyarı"}), hide_index=True, use_container_width=True)
                                else:
                                    st.success("Load management uyarısı yok ✅")


# ══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 2 — Sonuçlar
# ══════════════════════════════════════════════════════════════════════════════
elif _sec == "sonuclar":
    if is_nba:
        max_sonuc_date = datetime.now(EASTERN_TZ).date() - timedelta(days=1)
    else:
        max_sonuc_date = datetime.now(TURKISH_TZ).date() - timedelta(days=1)

    _lig_logo = league_cfg.get("logo", "")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:24px">'
        f'{_logo_img(_lig_logo, 40, "10px")}'
        f'<div>'
        f'<div style="font-size:24px;font-weight:900;color:#f1f5f9;letter-spacing:-.3px">{selected_league}</div>'
        f'<div style="font-size:12px;color:#334155;font-weight:600;letter-spacing:.8px;text-transform:uppercase">Geçmiş Sonuçlar</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    sc_col_date, sc_col_btn = st.columns([4, 1])
    with sc_col_date:
        sonuc_date = st.date_input("Tarih seçin:", value=max_sonuc_date, max_value=max_sonuc_date,
                                   format="DD/MM/YYYY", key="sonuclar_date_input")
    with sc_col_btn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        getir = st.button("📥  Getir", type="primary", use_container_width=True, key="btn_sonuclar")

    if getir:
        if is_nba:
            _sd = sonuc_date.strftime("%m/%d/%Y")
            with st.spinner("Sonuçlar yükleniyor..."):
                try:
                    st.session_state["sonuc_data"]         = get_nba_results_by_date(_sd)
                    st.session_state["sonuc_league"]       = selected_league
                    st.session_state["sonuc_date_display"] = sonuc_date.strftime("%d/%m/%Y")
                    st.session_state["sonuc_sport"]        = "nba"
                except Exception as e:
                    st.error(f"Hata: {e}")
        else:
            _sd  = sonuc_date.strftime("%Y-%m-%d")
            cfg2 = LEAGUES[selected_league]
            with st.spinner("Sonuçlar yükleniyor..."):
                try:
                    st.session_state["sonuc_data"]         = get_results_by_date(cfg2["id"], cfg2["season"], _sd)
                    st.session_state["sonuc_league"]       = selected_league
                    st.session_state["sonuc_date_display"] = sonuc_date.strftime("%d/%m/%Y")
                    st.session_state["sonuc_sport"]        = "football"
                except Exception as e:
                    st.error(f"Hata: {e}")

    sonuc_data   = st.session_state.get("sonuc_data")
    sonuc_sport  = st.session_state.get("sonuc_sport", "nba" if is_nba else "football")
    sonuc_league = st.session_state.get("sonuc_league", selected_league)
    sonuc_date_d = st.session_state.get("sonuc_date_display", "")

    if sonuc_data is None:
        st.markdown("""
<div style="text-align:center;padding:80px 20px">
  <div style="font-size:56px;margin-bottom:20px;opacity:.4">📊</div>
  <div style="font-size:20px;font-weight:700;color:#1e3a5f;margin-bottom:8px">Sonuçlar için hazır</div>
  <div style="font-size:14px;color:#1a2f4e">Geçmiş bir tarih seçip <b style="color:#2563eb">Getir</b> butonuna basın.</div>
</div>""", unsafe_allow_html=True)

    elif sonuc_sport == "nba":
        results = sonuc_data
        if not results:
            st.info("Bu tarihte tamamlanmış NBA maçı bulunamadı.")
        else:
            rows_html = ""
            for r in results:
                hl  = r.get("home_logo", ""); al = r.get("away_logo", "")
                hw  = r["home_score"] > r["away_score"]
                h_s = "font-weight:800;color:#f1f5f9" if hw else "color:#334155"
                a_s = "font-weight:800;color:#f1f5f9" if not hw else "color:#334155"
                w_tag = (f'<span style="background:#14532d;color:#4ade80;border:1px solid #166534;'
                         f'border-radius:7px;padding:3px 10px;font-size:11px;font-weight:700">'
                         f'{r["home_team"] if hw else r["away_team"]}</span>')
                rows_html += f"""
<tr style="border-bottom:1px solid #0f1f38">
  <td style="padding:12px 14px;{h_s}">{_logo_img(hl,22,"5px")} {r['home_team']}</td>
  <td style="padding:12px 20px;text-align:center;font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:3px">{r['home_score']} — {r['away_score']}</td>
  <td style="padding:12px 14px;{a_s}">{_logo_img(al,22,"5px")} {r['away_team']}</td>
  <td style="padding:12px 14px;text-align:center">{w_tag}</td>
</tr>"""

            st.markdown(f"""
<div style="background:#080f1f;border:1px solid #0f1f38;border-radius:16px;overflow:hidden;margin-bottom:20px">
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:#0a1526">
      <th style="padding:10px 14px;text-align:left;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Ev Sahibi</th>
      <th style="padding:10px 20px;text-align:center;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Skor</th>
      <th style="padding:10px 14px;text-align:left;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Deplasman</th>
      <th style="padding:10px 14px;text-align:center;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Kazanan</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>""", unsafe_allow_html=True)

            st.divider()
            for r in results:
                home_pts = r["home_score"]; away_pts = r["away_score"]
                home_won = home_pts > away_pts
                hl = r.get("home_logo",""); al = r.get("away_logo","")
                game_id  = r["match_id"]
                with st.expander(f"🏀  {r['home_team']}  {home_pts} — {away_pts}  {r['away_team']}", expanded=False):
                    h_b = "font-weight:900;color:#f1f5f9" if home_won else "color:#334155"
                    a_b = "font-weight:900;color:#f1f5f9" if not home_won else "color:#334155"
                    st.markdown(f"""
<div style="display:flex;justify-content:center;align-items:center;gap:32px;padding:24px 0 16px">
  <div style="text-align:right;flex:1">
    <div style="font-size:11px;color:#1e3a5f;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Ev Sahibi</div>
    <div style="display:flex;align-items:center;justify-content:flex-end;gap:10px">
      <span style="font-size:17px;{h_b}">{r['home_team']}</span>
      {_logo_img(hl, 40, "10px")}
    </div>
  </div>
  <div style="text-align:center;background:#0a1526;border:1px solid #0f1f38;border-radius:16px;padding:16px 28px">
    <div style="font-size:44px;font-weight:900;color:#f1f5f9;letter-spacing:8px;line-height:1">{home_pts}–{away_pts}</div>
    <div style="font-size:10px;color:#1e3a5f;margin-top:8px;text-transform:uppercase;letter-spacing:1.2px">Final</div>
  </div>
  <div style="text-align:left;flex:1">
    <div style="font-size:11px;color:#1e3a5f;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Deplasman</div>
    <div style="display:flex;align-items:center;gap:10px">
      {_logo_img(al, 40, "10px")}
      <span style="font-size:17px;{a_b}">{r['away_team']}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
                    st.divider()
                    _safe_date = sonuc_date_d.replace("/", "")
                    btn_key = f"box_{_safe_date}_{game_id}"
                    state_key = f"box_loaded_{_safe_date}_{game_id}"
                    if not st.session_state.get(state_key):
                        if st.button("📊  Oyuncu İstatistiklerini Göster", key=btn_key):
                            st.session_state[state_key] = True; st.rerun()
                    else:
                        with st.spinner("Yükleniyor..."):
                            box = get_nba_box_score(game_id, home_team_id=r["home_team_id"], away_team_id=r["away_team_id"])
                        _render_nba_box_score(box, r["home_team"], r["away_team"], r.get("home_logo",""), r.get("away_logo",""))

    elif sonuc_sport == "football":
        results = sonuc_data
        if not results:
            st.info("Bu tarihte tamamlanmış maç bulunamadı.")
        else:
            rows_html = ""
            for r in results:
                hl = r.get("home_logo",""); al = r.get("away_logo","")
                hs = r["home_score"]; as_ = r["away_score"]
                hw = hs > as_
                h_s = "font-weight:800;color:#f1f5f9" if hw else "color:#334155"
                a_s = "font-weight:800;color:#f1f5f9" if not hw else "color:#334155"
                if hw:
                    w_tag = f'<span style="background:#14532d;color:#4ade80;border:1px solid #166534;border-radius:7px;padding:3px 10px;font-size:11px;font-weight:700">{r["home_team"]}</span>'
                elif as_ > hs:
                    w_tag = f'<span style="background:#14532d;color:#4ade80;border:1px solid #166634;border-radius:7px;padding:3px 10px;font-size:11px;font-weight:700">{r["away_team"]}</span>'
                else:
                    w_tag = '<span style="background:#1c1a06;color:#fbbf24;border:1px solid #92400e;border-radius:7px;padding:3px 10px;font-size:11px;font-weight:700">Beraberlik</span>'
                try:
                    from datetime import datetime as _dt
                    dt_s = _dt.fromisoformat(r["match_time"][:16]).strftime("%H:%M")
                except Exception:
                    dt_s = ""
                rows_html += f"""
<tr style="border-bottom:1px solid #0f1f38">
  <td style="padding:10px 14px;color:#1e3a5f;font-size:12px">{dt_s}</td>
  <td style="padding:12px 14px;{h_s}">{_logo_img(hl,22,"50%")} {r['home_team']}</td>
  <td style="padding:12px 20px;text-align:center;font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:3px">{hs} — {as_}</td>
  <td style="padding:12px 14px;{a_s}">{_logo_img(al,22,"50%")} {r['away_team']}</td>
  <td style="padding:12px 14px;text-align:center">{w_tag}</td>
</tr>"""

            st.markdown(f"""
<div style="background:#080f1f;border:1px solid #0f1f38;border-radius:16px;overflow:hidden">
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:#0a1526">
      <th style="padding:10px 14px;text-align:left;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Saat</th>
      <th style="padding:10px 14px;text-align:left;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Ev Sahibi</th>
      <th style="padding:10px 20px;text-align:center;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Skor</th>
      <th style="padding:10px 14px;text-align:left;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Deplasman</th>
      <th style="padding:10px 14px;text-align:center;color:#1e3a5f;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px">Sonuç</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>""", unsafe_allow_html=True)
