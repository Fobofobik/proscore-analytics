"""
Futbol verisi — ESPN public API (API key gerekmez, güncel sezon) +
               The Odds API (fixtures + odds).
"""
from __future__ import annotations

import json
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

from config import (
    ODDS_API_KEY,
    CACHE_DIR,
    CACHE_TTL_MIN,
    FORM_MATCH_COUNT,
    SUPER_LIG_ID,
    CURRENT_SEASON,
)

# ── Sabitler ──────────────────────────────────────────────────────────────────

_ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
_ODDS_BASE = "https://api.the-odds-api.com/v4/sports"

# API-Football league_id → ESPN league slug
_LEAGUE_ESPN: dict[int, str] = {
    203: "tur.1",
    39:  "eng.1",
    78:  "ger.1",
    135: "ita.1",
    61:  "fra.1",
}

# API-Football league_id → The Odds API sport key
_LEAGUE_SPORT_KEYS: dict[int, str] = {
    203: "soccer_turkey_super_league",
    39:  "soccer_epl",
    78:  "soccer_germany_bundesliga",
    135: "soccer_italy_serie_a",
    61:  "soccer_france_ligue_one",
}

# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    Path(CACHE_DIR).mkdir(exist_ok=True)
    return Path(CACHE_DIR) / f"{key}.json"

def _load_cache(key: str, ttl: int | None = None) -> Optional[dict | list]:
    p = _cache_path(key)
    if not p.exists():
        return None
    age_min = (time.time() - p.stat().st_mtime) / 60
    limit = ttl if ttl is not None else CACHE_TTL_MIN
    if age_min > limit:
        return None
    with open(p) as f:
        return json.load(f)

def _save_cache(key: str, data: dict | list) -> None:
    with open(_cache_path(key), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── İsim normalize ────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.replace(" ", "").replace("-", "").replace("&", "and")

# ── ESPN: Lig takımları ────────────────────────────────────────────────────────

def _get_league_teams(league_id: int) -> list[dict]:
    """ESPN'den lig takımlarını çeker (30 gün önbellekleme)."""
    espn_slug = _LEAGUE_ESPN.get(league_id)
    if not espn_slug:
        return []

    key = f"espn_teams_{league_id}"
    cached = _load_cache(key, ttl=60 * 24 * 30)
    if cached is not None:
        return cached

    try:
        resp = requests.get(f"{_ESPN_BASE}/{espn_slug}/teams", timeout=15)
        resp.raise_for_status()
        raw = resp.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        teams = []
        for entry in raw:
            t = entry.get("team", {})
            logos = t.get("logos", [])
            logo  = logos[0].get("href", "") if logos else ""
            teams.append({"id": int(t["id"]), "name": t.get("displayName", ""), "logo": logo})
        if teams:
            _save_cache(key, teams)
        return teams
    except Exception as e:
        print(f"[ESPN] Takım listesi hatası ({league_id}): {e}")
        return []


def _find_team(name: str, teams: list[dict]) -> dict:
    """Takım ismini normalize ederek listede arar (fuzzy)."""
    norm = _norm(name)
    for t in teams:
        if _norm(t["name"]) == norm:
            return t
    for t in teams:
        tn = _norm(t["name"])
        if (norm in tn or tn in norm) and len(min(norm, tn, key=len)) >= 5:
            return t
    norm_first = norm.split("and")[0][:8]
    for t in teams:
        tn = _norm(t["name"])
        if len(norm_first) >= 5 and (norm_first in tn or tn[:len(norm_first)] == norm_first):
            return t
    return {}

# ── Skor parse helper ─────────────────────────────────────────────────────────

def _parse_score(score_val) -> int:
    """Scoreboard (string) veya schedule (dict) endpoint'inden skor çıkarır."""
    if isinstance(score_val, dict):
        return int(float(score_val.get("displayValue", score_val.get("value", 0)) or 0))
    try:
        return int(float(score_val or 0))
    except (ValueError, TypeError):
        return 0

# ── The Odds API: fixture listesi ─────────────────────────────────────────────

def _fetch_odds_events(sport_key: str) -> list[dict]:
    if not ODDS_API_KEY:
        return []
    cache_key = f"odds_events_{sport_key}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached
    try:
        resp = requests.get(
            f"{_ODDS_BASE}/{sport_key}/odds",
            params={"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"},
            timeout=15,
        )
        resp.raise_for_status()
        events = resp.json()
        print(f"[OddsAPI] {sport_key}: {len(events)} event | kalan: {resp.headers.get('x-requests-remaining')}")
        _save_cache(cache_key, events)
        return events
    except Exception as e:
        print(f"[OddsAPI] Fixture hatası ({sport_key}): {e}")
        return []


def _event_on_date(event: dict, date_str: str, tz_offset_hours: int = 3) -> bool:
    try:
        utc_dt   = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
        local_dt = utc_dt + timedelta(hours=tz_offset_hours)
        return local_dt.strftime("%Y-%m-%d") == date_str
    except Exception:
        return False

# ── Yaklaşan maçlar ───────────────────────────────────────────────────────────

def get_upcoming_matches(
    league_id: int = SUPER_LIG_ID,
    season: int = CURRENT_SEASON,
    date: str | None = None,
) -> list[dict]:
    """
    Yaklaşan maçları döner.
    Fixture listesi The Odds API'den, takım bilgisi (ID/logo) ESPN'den gelir.
    """
    sport_key = _LEAGUE_SPORT_KEYS.get(league_id)
    if not sport_key:
        return []

    cache_key = f"upcoming_odds_{league_id}_{date or 'next'}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    events = _fetch_odds_events(sport_key)
    if not events:
        return []

    if date:
        events = [e for e in events if _event_on_date(e, date)]

    teams = _get_league_teams(league_id)

    matches = []
    for event in events:
        home_name = event.get("home_team", "")
        away_name = event.get("away_team", "")
        home_info = _find_team(home_name, teams)
        away_info = _find_team(away_name, teams)

        try:
            utc_dt   = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
            local_dt = utc_dt + timedelta(hours=3)
            dt_iso   = local_dt.isoformat()
        except Exception:
            dt_iso = event.get("commence_time", "")

        matches.append({
            "match_id":     event.get("id", ""),
            "home_team":    home_name,
            "away_team":    away_name,
            "home_team_id": home_info.get("id", 0),
            "away_team_id": away_info.get("id", 0),
            "home_logo":    home_info.get("logo", ""),
            "away_logo":    away_info.get("logo", ""),
            "match_time":   dt_iso,
            "status":       "Not Started",
            "round":        "",
        })

    _save_cache(cache_key, matches)
    return matches

# ── Son N maç formu ───────────────────────────────────────────────────────────

def get_team_form(
    team_id: int,
    team_name: str,
    league_id: int = SUPER_LIG_ID,
    season: int = CURRENT_SEASON,
) -> list[dict]:
    """ESPN takım schedule endpoint'inden son FORM_MATCH_COUNT maçı döner."""
    if team_id == 0:
        return []
    espn_slug = _LEAGUE_ESPN.get(league_id)
    if not espn_slug:
        return []

    key = f"espn_form_{league_id}_{team_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    results = []
    try:
        resp = requests.get(f"{_ESPN_BASE}/{espn_slug}/teams/{team_id}/schedule", timeout=15)
        resp.raise_for_status()
        events = resp.json().get("events", [])

        completed = [
            e for e in events
            if e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("name", "") == "STATUS_FULL_TIME"
        ]
        completed.sort(key=lambda e: e.get("date", ""), reverse=True)

        for e in completed[:FORM_MATCH_COUNT]:
            comp        = e["competitions"][0]
            competitors = comp["competitors"]
            home_comp   = next((t for t in competitors if t["homeAway"] == "home"), None)
            away_comp   = next((t for t in competitors if t["homeAway"] == "away"), None)
            if not home_comp or not away_comp:
                continue

            h_score = _parse_score(home_comp.get("score", 0))
            a_score = _parse_score(away_comp.get("score", 0))
            is_home = int(home_comp["team"]["id"]) == team_id

            goals_for     = h_score if is_home else a_score
            goals_against = a_score if is_home else h_score
            result = "W" if goals_for > goals_against else ("D" if goals_for == goals_against else "L")

            try:
                dt       = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
                date_str = dt.strftime("%d.%m.%Y")
            except Exception:
                date_str = e.get("date", "")[:10]

            results.append({
                "date":          date_str,
                "home_team":     home_comp["team"].get("displayName", "?"),
                "away_team":     away_comp["team"].get("displayName", "?"),
                "is_home":       is_home,
                "score":         f"{h_score}-{a_score}",
                "result":        result,
                "goals_for":     goals_for,
                "goals_against": goals_against,
                "tournament":    espn_slug,
            })
    except Exception as e:
        print(f"[ESPN] Form hatası ({team_name}): {e}")

    _save_cache(key, results)
    return results

# ── H2H ──────────────────────────────────────────────────────────────────────

def get_h2h(home_id: int, away_id: int, league_id: int = SUPER_LIG_ID) -> list[dict]:
    """İki takım arasındaki son 5 maçı ESPN schedule'dan döner."""
    if home_id == 0 or away_id == 0:
        return []

    espn_slug = _LEAGUE_ESPN.get(league_id)
    if not espn_slug:
        return []

    key = f"espn_h2h_{min(home_id, away_id)}_{max(home_id, away_id)}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    results = []
    try:
        resp = requests.get(f"{_ESPN_BASE}/{espn_slug}/teams/{home_id}/schedule", timeout=15)
        resp.raise_for_status()
        events = resp.json().get("events", [])

        for e in events:
            comp = e.get("competitions", [{}])[0]
            if comp.get("status", {}).get("type", {}).get("name", "") != "STATUS_FULL_TIME":
                continue
            competitors = comp.get("competitors", [])
            team_ids = [int(t["team"]["id"]) for t in competitors]
            if away_id not in team_ids:
                continue

            home_comp = next((t for t in competitors if t["homeAway"] == "home"), None)
            away_comp = next((t for t in competitors if t["homeAway"] == "away"), None)
            if not home_comp or not away_comp:
                continue

            h_score = _parse_score(home_comp.get("score", 0))
            a_score = _parse_score(away_comp.get("score", 0))
            is_home = int(home_comp["team"]["id"]) == home_id

            goals_for     = h_score if is_home else a_score
            goals_against = a_score if is_home else h_score
            result = "W" if goals_for > goals_against else ("D" if goals_for == goals_against else "L")

            try:
                dt       = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
                date_str = dt.strftime("%d.%m.%Y")
            except Exception:
                date_str = e.get("date", "")[:10]

            results.append({
                "date":          date_str,
                "home_team":     home_comp["team"].get("displayName", "?"),
                "away_team":     away_comp["team"].get("displayName", "?"),
                "is_home":       is_home,
                "score":         f"{h_score}-{a_score}",
                "result":        result,
                "goals_for":     goals_for,
                "goals_against": goals_against,
                "tournament":    espn_slug,
            })
    except Exception as e:
        print(f"[ESPN] H2H hatası ({home_id}-{away_id}): {e}")

    results = sorted(results, key=lambda r: r["date"], reverse=True)[:5]
    _save_cache(key, results)
    return results

# ── Geçmiş maç sonuçları ─────────────────────────────────────────────────────

def get_results_by_date(
    league_id: int,
    season: int,
    date_str: str,
) -> list[dict]:
    """Belirtilen tarihteki tamamlanmış maçları döner (YYYY-MM-DD)."""
    espn_slug = _LEAGUE_ESPN.get(league_id)
    if not espn_slug:
        return []

    key = f"espn_results_{league_id}_{date_str}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    matches = []
    try:
        resp = requests.get(
            f"{_ESPN_BASE}/{espn_slug}/scoreboard",
            params={"dates": date_str.replace("-", "")},
            timeout=15,
        )
        resp.raise_for_status()
        events = resp.json().get("events", [])

        for e in events:
            comp = e["competitions"][0]
            if comp["status"]["type"]["name"] != "STATUS_FULL_TIME":
                continue
            competitors = comp["competitors"]
            home_comp = next((t for t in competitors if t["homeAway"] == "home"), None)
            away_comp = next((t for t in competitors if t["homeAway"] == "away"), None)
            if not home_comp or not away_comp:
                continue

            h_score = _parse_score(home_comp.get("score", 0))
            a_score = _parse_score(away_comp.get("score", 0))

            try:
                utc_dt   = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
                local_dt = utc_dt + timedelta(hours=3)
                dt_iso   = local_dt.isoformat()
            except Exception:
                dt_iso = e.get("date", "")

            home_logos = home_comp["team"].get("logos", [])
            away_logos = away_comp["team"].get("logos", [])

            matches.append({
                "match_id":     str(e.get("id", "")),
                "home_team":    home_comp["team"].get("displayName", ""),
                "away_team":    away_comp["team"].get("displayName", ""),
                "home_team_id": int(home_comp["team"]["id"]),
                "away_team_id": int(away_comp["team"]["id"]),
                "home_logo":    home_logos[0].get("href", "") if home_logos else "",
                "away_logo":    away_logos[0].get("href", "") if away_logos else "",
                "home_score":   h_score,
                "away_score":   a_score,
                "match_time":   dt_iso,
                "status":       "Full Time",
                "round":        "",
            })
    except Exception as e:
        print(f"[ESPN] Sonuçlar hatası ({date_str}): {e}")

    if matches:
        _save_cache(key, matches)
    return matches

# ── Sezon istatistikleri ───────────────────────────────────────────────────────

def get_team_season_stats(
    team_id: int,
    team_name: str,
    league_id: int = SUPER_LIG_ID,
    season: int = CURRENT_SEASON,
) -> dict:
    if team_id == 0:
        return {}
    espn_slug = _LEAGUE_ESPN.get(league_id)
    if not espn_slug:
        return {}

    key = f"espn_season_stats_{league_id}_{team_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(f"{_ESPN_BASE}/{espn_slug}/teams/{team_id}", timeout=15)
        resp.raise_for_status()
        record_items = resp.json().get("team", {}).get("record", {}).get("items", [])
        if not record_items:
            return {}

        stats = {s["name"]: s["value"] for s in record_items[0].get("stats", [])}

        home_played = int(stats.get("homeGamesPlayed", 0))
        home_wins   = int(stats.get("homeWins", 0))
        home_gf     = float(stats.get("homePointsFor", 0))
        home_ga     = float(stats.get("homePointsAgainst", 0))
        away_played = int(stats.get("awayGamesPlayed", 0))
        away_wins   = int(stats.get("awayWins", 0))
        away_gf     = float(stats.get("awayPointsFor", 0))
        away_ga     = float(stats.get("awayPointsAgainst", 0))

        home_wpct = (home_wins / home_played) if home_played > 0 else 0.5
        away_wpct = (away_wins / away_played) if away_played > 0 else 0.5

        result = {
            "home_wpct":              round(home_wpct, 3),
            "away_wpct":              round(away_wpct, 3),
            "avg_goals_for_home":     round(home_gf / home_played, 2) if home_played > 0 else 1.3,
            "avg_goals_for_away":     round(away_gf / away_played, 2) if away_played > 0 else 1.3,
            "avg_goals_against_home": round(home_ga / home_played, 2) if home_played > 0 else 1.3,
            "avg_goals_against_away": round(away_ga / away_played, 2) if away_played > 0 else 1.3,
            "xg_for":                 None,
            "xg_against":             None,
        }
        _save_cache(key, result)
        return result
    except Exception as e:
        print(f"[ESPN] Sezon istatistik hatası ({team_name}): {e}")
        return {}


# ── Lig sıralaması ────────────────────────────────────────────────────────────

def get_league_standings(league_id: int) -> dict[int, dict]:
    """
    ESPN'den lig tablosunu çeker.
    Döner: {team_id: {"rank": int, "points": int, "played": int, "total_teams": int}}
    """
    espn_slug = _LEAGUE_ESPN.get(league_id)
    if not espn_slug:
        return {}

    key = f"standings_{league_id}"
    cached = _load_cache(key, ttl=60 * 4)   # 4 saatlik önbellek
    if cached is not None:
        return {int(k): v for k, v in cached.items()}

    result: dict[int, dict] = {}
    try:
        resp = requests.get(
            f"https://site.api.espn.com/apis/v2/sports/soccer/{espn_slug}/standings",
            timeout=15,
        )
        resp.raise_for_status()
        entries = resp.json().get("standings", {}).get("entries", [])
        total   = len(entries)
        for entry in entries:
            tid   = int(entry.get("team", {}).get("id", 0))
            stats = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
            result[tid] = {
                "rank":        int(stats.get("rank", stats.get("position", 0))),
                "points":      int(stats.get("points", 0)),
                "played":      int(stats.get("gamesPlayed", 0)),
                "total_teams": total,
            }
    except Exception as e:
        print(f"[ESPN] Sıralama hatası ({league_id}): {e}")

    if result:
        _save_cache(key, {str(k): v for k, v in result.items()})
    return result
