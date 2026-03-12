"""
The Odds API üzerinden maç oranlarını çeker.
Desteklenen ligler: Süper Lig, Premier League, NBA
API: https://the-odds-api.com  (500 istek/ay ücretsiz)
"""
from __future__ import annotations

import json
import time
import unicodedata
from pathlib import Path
from typing import Optional

import requests

from config import ODDS_API_KEY, CACHE_DIR, CACHE_TTL_MIN

BASE_URL = "https://api.the-odds-api.com/v4/sports"

# sport_key → The Odds API sport key
SPORT_KEYS: dict[str, str] = {
    "Süper Lig":      "soccer_turkey_super_league",
    "Premier League": "soccer_epl",
    "Bundesliga":     "soccer_germany_bundesliga",
    "Serie A":        "soccer_italy_serie_a",
    "Ligue 1":        "soccer_france_ligue_one",
    "NBA":            "basketball_nba",
}

BOOKMAKERS = "pinnacle,bet365,betway,unibet"


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_path(league: str) -> Path:
    Path(CACHE_DIR).mkdir(exist_ok=True)
    safe = league.lower().replace(" ", "_")
    return Path(CACHE_DIR) / f"odds_{safe}.json"


def _load_cache(league: str) -> Optional[dict]:
    p = _cache_path(league)
    if not p.exists():
        return None
    age_min = (time.time() - p.stat().st_mtime) / 60
    if age_min > CACHE_TTL_MIN:
        return None
    with open(p) as f:
        return json.load(f)


def _save_cache(league: str, data: dict) -> None:
    with open(_cache_path(league), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Normalize ──────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """Küçük harf, aksansız, boşuksuz normalize."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace(" ", "").replace("-", "").replace(".", "")


# ── API ────────────────────────────────────────────────────────────────────────

def get_odds(league_name: str) -> dict[str, dict]:
    """
    Verilen lig için oranları çekip şu formatta döner:
    {
        "norm_home_norm_away": {
            "home_win": 1.85,
            "draw":     3.40,
            "away_win": 4.20,
        },
        ...
    }
    Hata durumunda boş dict döner.
    """
    if not ODDS_API_KEY:
        return {}

    sport_key = SPORT_KEYS.get(league_name)
    if not sport_key:
        return {}

    cached = _load_cache(league_name)
    if cached is not None:
        return cached

    try:
        url = f"{BASE_URL}/{sport_key}/odds"
        params = {
            "apiKey":    ODDS_API_KEY,
            "regions":   "eu",
            "markets":   "h2h",
            "oddsFormat":"decimal",
            "bookmakers": BOOKMAKERS,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        events = resp.json()
        print(f"[OddsAPI] {league_name}: {len(events)} maç, "
              f"kalan istek: {resp.headers.get('x-requests-remaining', '?')}")
    except Exception as e:
        print(f"[OddsAPI] Hata ({league_name}): {e}")
        return {}

    result: dict[str, dict] = {}
    for event in events:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        key  = f"{_norm(home)}_{_norm(away)}"

        # Bookmaker'lardan ortalama oran hesapla
        h_odds_list, d_odds_list, a_odds_list = [], [], []

        for bm in event.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                # Draw yoksa NBA (2'li market)
                if home in outcomes:
                    h_odds_list.append(outcomes[home])
                if away in outcomes:
                    a_odds_list.append(outcomes[away])
                if "Draw" in outcomes:
                    d_odds_list.append(outcomes["Draw"])

        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else None

        result[key] = {
            "home_team": home,
            "away_team": away,
            "home_win":  avg(h_odds_list),
            "draw":      avg(d_odds_list) if d_odds_list else None,
            "away_win":  avg(a_odds_list),
        }

    _save_cache(league_name, result)
    return result


def match_odds(odds_data: dict[str, dict], home_name: str, away_name: str) -> dict:
    """
    odds_data içinden home/away ismine en yakın eşleşmeyi bulup döner.
    Tam eşleşme yoksa normalize karşılaştırma yapar.
    """
    key = f"{_norm(home_name)}_{_norm(away_name)}"
    if key in odds_data:
        return odds_data[key]

    # Kısmi eşleşme: her iki takım için de içerik kontrolü
    norm_home = _norm(home_name)
    norm_away = _norm(away_name)
    for k, v in odds_data.items():
        nk_home = _norm(v.get("home_team", ""))
        nk_away = _norm(v.get("away_team", ""))
        if (norm_home[:6] in nk_home or nk_home[:6] in norm_home) and \
           (norm_away[:6] in nk_away or nk_away[:6] in norm_away):
            return v

    return {}
