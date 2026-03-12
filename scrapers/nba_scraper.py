"""
NBA maç verileri — nba_api (ücretsiz, stats.nba.com) kullanır.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import CACHE_DIR, CACHE_TTL_MIN, FORM_MATCH_COUNT

# ── NBA takım şehirleri → UTC saat dilimi (standart saat, kış) ────────────────
NBA_CITY_TIMEZONE: dict[str, int] = {
    "Atlanta Hawks": -5, "Boston Celtics": -5, "Brooklyn Nets": -5,
    "Charlotte Hornets": -5, "Chicago Bulls": -6, "Cleveland Cavaliers": -5,
    "Dallas Mavericks": -6, "Denver Nuggets": -7, "Detroit Pistons": -5,
    "Golden State Warriors": -8, "Houston Rockets": -6, "Indiana Pacers": -5,
    "Los Angeles Clippers": -8, "Los Angeles Lakers": -8, "Memphis Grizzlies": -6,
    "Miami Heat": -5, "Milwaukee Bucks": -6, "Minnesota Timberwolves": -6,
    "New Orleans Pelicans": -6, "New York Knicks": -5, "Oklahoma City Thunder": -6,
    "Orlando Magic": -5, "Philadelphia 76ers": -5, "Phoenix Suns": -7,
    "Portland Trail Blazers": -8, "Sacramento Kings": -8, "San Antonio Spurs": -6,
    "Toronto Raptors": -5, "Utah Jazz": -7, "Washington Wizards": -5,
}

# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    Path(CACHE_DIR).mkdir(exist_ok=True)
    return Path(CACHE_DIR) / f"nba_{key}.json"

def _load_cache(key: str) -> Optional[list]:
    p = _cache_path(key)
    if not p.exists():
        return None
    age_min = (time.time() - p.stat().st_mtime) / 60
    if age_min > CACHE_TTL_MIN:
        return None
    with open(p) as f:
        return json.load(f)

def _save_cache(key: str, data: list) -> None:
    with open(_cache_path(key), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Bugünkü / yaklaşan maçlar ─────────────────────────────────────────────────

def get_upcoming_nba_matches(date_str: str | None = None) -> list[dict]:
    """Henüz oynanmamış NBA maçlarını döner.

    Args:
        date_str: MM/DD/YYYY formatında ABD Doğu saatine göre tarih.
                  None ise bugün/yarın otomatik denenir.
    """
    if date_str:
        cache_key = f"upcoming_{date_str.replace('/', '-')}"
    else:
        cache_key = "upcoming"

    cached = _load_cache(cache_key)
    if cached:
        return cached

    from nba_api.stats.static import teams as nba_static
    all_teams = {t["id"]: t["full_name"] for t in nba_static.get_teams()}

    if date_str:
        matches = _fetch_scoreboard_day(all_teams=all_teams, target_date_str=date_str)
    else:
        matches = _fetch_live_upcoming(all_teams)
        if not matches:
            matches = _fetch_scoreboard_day(days_ahead=0, all_teams=all_teams)
        if not matches:
            matches = _fetch_scoreboard_day(days_ahead=1, all_teams=all_teams)

    if matches:
        _save_cache(cache_key, matches)
    return matches


def _fetch_live_upcoming(all_teams: dict) -> list[dict]:
    """Live scoreboard'dan henüz bitmemiş maçları döner."""
    matches = []
    try:
        from nba_api.live.nba.endpoints import scoreboard
        board = scoreboard.ScoreBoard()
        games = board.get_dict().get("scoreboard", {}).get("games", [])

        for g in games:
            # gameStatus: 1=Scheduled, 2=InProgress, 3=Final
            if g.get("gameStatus", 3) == 3:
                continue   # bitti, atla
            home = g["homeTeam"]
            away = g["awayTeam"]
            home_id = home["teamId"]
            away_id = away["teamId"]
            matches.append({
                "match_id":     g["gameId"],
                "home_team":    all_teams.get(home_id, home["teamName"]),
                "away_team":    all_teams.get(away_id, away["teamName"]),
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_logo":    f"https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg",
                "away_logo":    f"https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg",
                "match_time":   g.get("gameStatusText", ""),
                "status":       g.get("gameStatusText", ""),
                "round":        "",
                "sport":        "nba",
            })
    except Exception as e:
        print(f"[NBA] Live scoreboard hatası: {e}")
    return matches


def _fetch_scoreboard_day(
    days_ahead: int = 0,
    all_teams: dict = None,
    target_date_str: str = None,
    include_completed: bool = False,
) -> list[dict]:
    """Belirtilen günün NBA maçlarını stats API'den çeker (ABD Doğu saatine göre).

    Args:
        days_ahead: Bugünden kaç gün ilerisi (target_date_str yoksa kullanılır).
        all_teams: {team_id: full_name} sözlüğü.
        target_date_str: MM/DD/YYYY formatında hedef tarih (öncelik bu alır).
        include_completed: True ise tamamlanmış maçlar da dahil edilir.
    """
    from datetime import datetime, timedelta, timezone
    if target_date_str is None:
        eastern = timezone(timedelta(hours=-5))
        target_date_str = (datetime.now(eastern) + timedelta(days=days_ahead)).strftime("%m/%d/%Y")

    matches = []
    try:
        from nba_api.stats.endpoints.scoreboardv2 import ScoreboardV2
        board = ScoreboardV2(game_date=target_date_str, league_id="00")
        games_df = board.game_header.get_data_frame()

        for _, row in games_df.iterrows():
            status_id = int(row.get("GAME_STATUS_ID", 3))
            if not include_completed and status_id == 3:
                continue
            if include_completed and status_id != 3:
                continue
            home_id = int(row["HOME_TEAM_ID"])
            away_id = int(row["VISITOR_TEAM_ID"])
            matches.append({
                "match_id":     str(row["GAME_ID"]),
                "home_team":    all_teams.get(home_id, str(home_id)) if all_teams else str(home_id),
                "away_team":    all_teams.get(away_id, str(away_id)) if all_teams else str(away_id),
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_logo":    f"https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg",
                "away_logo":    f"https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg",
                "match_time":   f"{target_date_str} {row.get('GAME_STATUS_TEXT','')}",
                "status":       row.get("GAME_STATUS_TEXT", ""),
                "round":        "",
                "sport":        "nba",
            })
    except Exception as e:
        print(f"[NBA] ScoreboardV2 hatası ({target_date_str}): {e}")
    return matches

# ── Son N maç formu ───────────────────────────────────────────────────────────

def get_nba_team_form(team_id: int, team_name: str) -> list[dict]:
    """NBA takımının son FORM_MATCH_COUNT maçını döner.
    Her maç dict'ine opponent_abbr, opponent_full_name ve opponent_net_rtg eklenir.
    """
    key = f"form_{team_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    results = []
    try:
        from nba_api.stats.endpoints import leaguegamefinder
        from nba_api.stats.static import teams as nba_static

        finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team_id,
            season_nullable="2024-25",
            season_type_nullable="Regular Season",
        )
        games_df = finder.get_data_frames()[0].head(FORM_MATCH_COUNT)

        nba_teams_list = nba_static.get_teams()
        abbr_to_full   = {t["abbreviation"]: t["full_name"] for t in nba_teams_list}
        abbr_to_id     = {t["abbreviation"]: t["id"]        for t in nba_teams_list}

        for _, row in games_df.iterrows():
            matchup  = row.get("MATCHUP", "")
            is_home  = "vs." in matchup
            pts      = int(row.get("PTS", 0))
            plus_min = float(row.get("PLUS_MINUS", 0))
            result   = "W" if row.get("WL") == "W" else "L"
            opp_pts  = pts - plus_min

            # Rakip kısaltması: "LAL vs. GSW" veya "LAL @ GSW" → "GSW"
            opp_abbr = matchup.split("vs." if is_home else "@")[-1].strip()
            opp_full = abbr_to_full.get(opp_abbr, opp_abbr)
            opp_id   = abbr_to_id.get(opp_abbr, None)

            home_team = team_name if is_home else opp_full
            away_team = opp_full  if is_home else team_name

            results.append({
                "date":               str(row.get("GAME_DATE", ""))[:10],
                "home_team":          home_team,
                "away_team":          away_team,
                "is_home":            is_home,
                "score":              f"{int(pts)}-{int(opp_pts)}",
                "result":             result,
                "goals_for":          pts,
                "goals_against":      int(opp_pts),
                "tournament":         "NBA",
                "opponent_abbr":      opp_abbr,
                "opponent_full_name": opp_full,
                "opponent_team_id":   opp_id,
                "opponent_net_rtg":   None,   # aşağıda doldurulur
            })
    except Exception as e:
        print(f"[NBA] Form hatası ({team_name}): {e}")

    # Rakip net_rtg ile zenginleştir (önbellekli, ekstra API çağrısı yok)
    try:
        all_ratings = _get_all_team_ratings_cached()
        for m in results:
            tid = m.get("opponent_team_id")
            if tid:
                m["opponent_net_rtg"] = all_ratings.get(str(tid), {}).get("net_rtg")
    except Exception:
        pass

    _save_cache(key, results)
    return results

# ── Sakatlıklar (ESPN gayri resmi API) ────────────────────────────────────────

_espn_id_cache: dict[int, Optional[int]] = {}

def _get_espn_team_id(nba_team_id: int) -> Optional[int]:
    """nba_api team_id'sini ESPN team_id'ye dönüştürür (abbreviation eşleştirmesi)."""
    if nba_team_id in _espn_id_cache:
        return _espn_id_cache[nba_team_id]
    try:
        import requests
        from nba_api.stats.static import teams as nba_static
        nba_teams = nba_static.get_teams()
        nba_team  = next((t for t in nba_teams if t["id"] == nba_team_id), None)
        if not nba_team:
            return None
        abbr = nba_team["abbreviation"].upper()

        resp = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams",
            params={"limit": 50},
            timeout=10,
        )
        if not resp.ok:
            return None
        leagues = resp.json().get("sports", [{}])[0].get("leagues", [{}])[0]
        for entry in leagues.get("teams", []):
            t = entry.get("team", {})
            if t.get("abbreviation", "").upper() == abbr:
                espn_id = int(t["id"])
                _espn_id_cache[nba_team_id] = espn_id
                return espn_id
    except Exception as e:
        print(f"[NBA] ESPN ID çözümleme hatası: {e}")
    _espn_id_cache[nba_team_id] = None
    return None


def get_nba_injuries(team_id: int, team_name: str) -> list[dict]:
    """NBA takımının sakat oyuncularını ESPN core API'den çeker."""
    key = f"injuries_{team_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    injuries = []
    try:
        import requests
        espn_id = _get_espn_team_id(team_id)
        if espn_id is None:
            print(f"[NBA] ESPN ID bulunamadı: {team_name}")
        else:
            url  = f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams/{espn_id}/injuries"
            resp = requests.get(url, timeout=10)
            if not resp.ok:
                raise RuntimeError(f"HTTP {resp.status_code}")
            items = resp.json().get("items", [])
            for item in items:
                ref = item.get("$ref", "")
                if not ref:
                    continue
                r2 = requests.get(ref, timeout=10)
                if not r2.ok:
                    continue
                inj = r2.json()
                status = inj.get("type", {}).get("description", inj.get("status", "?"))
                detail_type = inj.get("details", {}).get("type", "")

                # Sporcu adını çek
                athlete_ref = inj.get("athlete", {}).get("$ref", "")
                name, position = "?", "?"
                if athlete_ref:
                    ra = requests.get(athlete_ref, timeout=10)
                    if ra.ok:
                        ad = ra.json()
                        name     = ad.get("displayName", "?")
                        position = ad.get("position", {}).get("abbreviation", "?")

                injuries.append({
                    "name":     name,
                    "position": position,
                    "status":   f"{status} ({detail_type})" if detail_type else status,
                })
    except Exception as e:
        print(f"[NBA] Sakatlık hatası ({team_name}): {e}")

    _save_cache(key, injuries)
    return injuries

# ── H2H ──────────────────────────────────────────────────────────────────────

def get_nba_h2h(home_id: int, away_id: int) -> list[dict]:
    """İki NBA takımı arasındaki son maçları döner."""
    key = f"h2h_{min(home_id, away_id)}_{max(home_id, away_id)}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    results = []
    try:
        from nba_api.stats.endpoints import leaguegamefinder
        finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=home_id,
            season_nullable="2024-25",
        )
        df = finder.get_data_frames()[0]
        opp_abbr = ""
        # Rakibin kısa adını bul
        try:
            from nba_api.stats.static import teams
            away_info = [t for t in teams.get_teams() if t["id"] == away_id]
            if away_info:
                opp_abbr = away_info[0]["abbreviation"]
        except Exception:
            pass

        if opp_abbr:
            df = df[df["MATCHUP"].str.contains(opp_abbr, na=False)]

        for _, row in df.head(5).iterrows():
            matchup  = row.get("MATCHUP", "")
            is_home  = "vs." in matchup
            pts      = int(row.get("PTS", 0))
            plus_min = float(row.get("PLUS_MINUS", 0))
            opp_pts  = pts - plus_min
            result   = "W" if row.get("WL") == "W" else "L"

            results.append({
                "date":          str(row.get("GAME_DATE", ""))[:10],
                "home_team":     matchup.split("vs.")[0].strip() if is_home else matchup.split("@")[-1].strip(),
                "away_team":     matchup.split("vs.")[-1].strip() if is_home else matchup.split("@")[0].strip(),
                "is_home":       is_home,
                "score":         f"{int(pts)}-{int(opp_pts)}",
                "result":        result,
                "goals_for":     pts,
                "goals_against": int(opp_pts),
                "tournament":    "NBA",
            })
    except Exception:
        pass

    _save_cache(key, results)
    return results


# ── Back-to-back tespiti ──────────────────────────────────────────────────────

def get_nba_back_to_back(team_id: int, game_date_str: str) -> bool:
    """Takımın dünkü tarihte maç oynayıp oynamadığını kontrol eder (B2B)."""
    cache_key = f"b2b_{team_id}_{game_date_str.replace('/', '-')}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached[0]

    try:
        from datetime import datetime, timedelta
        from nba_api.stats.endpoints import leaguegamefinder

        game_date = datetime.strptime(game_date_str, "%m/%d/%Y")
        yesterday = game_date - timedelta(days=1)
        yesterday_str = yesterday.strftime("%m/%d/%Y")

        finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team_id,
            date_from_nullable=yesterday_str,
            date_to_nullable=yesterday_str,
            season_nullable="2024-25",
        )
        df = finder.get_data_frames()[0]
        result = len(df) > 0
        _save_cache(cache_key, [result])
        return result
    except Exception as e:
        print(f"[NBA] B2B kontrol hatası (team_id={team_id}): {e}")
        _save_cache(cache_key, [False])
        return False


# ── Gelişmiş takım istatistikleri ────────────────────────────────────────────

def _get_all_team_ratings_cached() -> dict:
    """Tüm NBA takımlarının gelişmiş istatistiklerini çeker ve önbellekler."""
    cache_key = "all_team_ratings"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached[0]

    ratings: dict[str, dict] = {}
    try:
        from nba_api.stats.endpoints import leaguedashteamstats

        # 1) Gelişmiş istatistikler (OffRtg, DefRtg, NetRtg, Pace)
        adv = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
            season="2024-25",
        )
        adv_df = adv.get_data_frames()[0]
        for _, row in adv_df.iterrows():
            tid = str(int(row["TEAM_ID"]))
            ratings[tid] = {
                "off_rtg": round(float(row.get("OFF_RATING", 0) or 0), 1),
                "def_rtg": round(float(row.get("DEF_RATING", 0) or 0), 1),
                "net_rtg": round(float(row.get("NET_RATING", 0) or 0), 1),
                "pace":    round(float(row.get("PACE", 0) or 0), 1),
            }

        # 2) Ev maçı kazanma yüzdesi
        home_stats = leaguedashteamstats.LeagueDashTeamStats(
            per_mode_detailed="PerGame",
            season="2024-25",
            location_nullable="Home",
        )
        home_df = home_stats.get_data_frames()[0]
        for _, row in home_df.iterrows():
            tid = str(int(row["TEAM_ID"]))
            if tid in ratings:
                ratings[tid]["home_wpct"] = round(float(row.get("W_PCT", 0.5) or 0.5), 3)

        # 3) Deplasman kazanma yüzdesi
        away_stats = leaguedashteamstats.LeagueDashTeamStats(
            per_mode_detailed="PerGame",
            season="2024-25",
            location_nullable="Road",
        )
        away_df = away_stats.get_data_frames()[0]
        for _, row in away_df.iterrows():
            tid = str(int(row["TEAM_ID"]))
            if tid in ratings:
                ratings[tid]["away_wpct"] = round(float(row.get("W_PCT", 0.5) or 0.5), 3)

        # 4) Sezon PPG ve son 5 maç PPG (skoring trendi için)
        base_season = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense="Base",
            per_mode_detailed="PerGame",
            season="2024-25",
        )
        for _, row in base_season.get_data_frames()[0].iterrows():
            tid = str(int(row["TEAM_ID"]))
            if tid in ratings:
                ratings[tid]["season_ppg"] = round(float(row.get("PTS", 100) or 100), 1)

        base_last5 = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense="Base",
            per_mode_detailed="PerGame",
            season="2024-25",
            last_n_games=5,
        )
        for _, row in base_last5.get_data_frames()[0].iterrows():
            tid = str(int(row["TEAM_ID"]))
            if tid in ratings:
                ratings[tid]["last5_ppg"] = round(float(row.get("PTS", 100) or 100), 1)

    except Exception as e:
        print(f"[NBA] Takım istatistikleri hatası: {e}")

    _save_cache(cache_key, [ratings])
    return ratings


def get_all_nba_team_ratings() -> dict:
    """Tüm NBA takımlarının istatistiklerini döner (önbellekli)."""
    return _get_all_team_ratings_cached()


def get_nba_team_ratings(team_id: int) -> dict:
    """Belirtilen NBA takımının gelişmiş istatistiklerini döner."""
    try:
        all_ratings = _get_all_team_ratings_cached()
        return all_ratings.get(str(team_id), {})
    except Exception as e:
        print(f"[NBA] Takım rating hatası (team_id={team_id}): {e}")
        return {}


# ── Load management / dinlenme tespiti ───────────────────────────────────────

def get_nba_load_management(team_id: int, team_name: str) -> list[dict]:
    """Takımın yıldız oyuncularının yük yönetimini kontrol eder."""
    cache_key = f"load_{team_id}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    flags: list[dict] = []
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats

        # Sezon ortalamaları
        season_stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season="2024-25",
            team_id_nullable=team_id,
            per_mode_detailed="PerGame",
        )
        season_df = season_stats.get_data_frames()[0]

        # Son 5 maç ortalamaları
        last5_stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season="2024-25",
            team_id_nullable=team_id,
            per_mode_detailed="PerGame",
            last_n_games=5,
        )
        last5_df = last5_stats.get_data_frames()[0]

        # Son 5 maçtaki oyuncuları indeksle
        last5_map: dict[str, float] = {}
        for _, row in last5_df.iterrows():
            pid = str(int(row["PLAYER_ID"]))
            last5_map[pid] = float(row.get("MIN", 0) or 0)

        # PIE (Player Impact Estimate) haritası
        pie_map: dict[str, float] = {}
        for _, row in season_df.iterrows():
            pid = str(int(row["PLAYER_ID"]))
            pie_map[pid] = float(row.get("PIE", 0.10) or 0.10)

        # Yıldız oyuncuları tespit et (sezon ort >= 25 dk)
        for _, row in season_df.iterrows():
            season_min = float(row.get("MIN", 0) or 0)
            if season_min < 25:
                continue

            player_name = str(row.get("PLAYER_NAME", "?"))
            pid         = str(int(row["PLAYER_ID"]))
            last5_min   = last5_map.get(pid, None)
            pie         = pie_map.get(pid, 0.10)
            # impact: PIE 0.05→0, 0.20→1 (0-1 arası oyuncu etki skoru)
            impact      = round(max(0.0, min(1.0, (pie - 0.05) / 0.15)), 3)

            if last5_min is None:
                flag = "Son 5 Maçta Yok (Dinlenme?)"
                flags.append({
                    "name":       player_name,
                    "season_min": round(season_min, 1),
                    "last5_min":  0.0,
                    "flag":       flag,
                    "pie":        round(pie, 4),
                    "impact":     impact,
                })
            elif last5_min < season_min - 6:
                flag = f"Düşük Dakika ({round(last5_min, 1)} dk / Sezon: {round(season_min, 1)} dk)"
                flags.append({
                    "name":       player_name,
                    "season_min": round(season_min, 1),
                    "last5_min":  round(last5_min, 1),
                    "flag":       flag,
                    "pie":        round(pie, 4),
                    "impact":     impact,
                })

    except Exception as e:
        print(f"[NBA] Load management hatası ({team_name}): {e}")

    _save_cache(cache_key, flags)
    return flags


# ── Seyahat yorgunluğu ────────────────────────────────────────────────────────

def get_nba_travel_penalty(
    team_name: str,
    form_matches: list[dict],
    is_home_today: bool,
    opponent_name: str,
) -> float:
    """
    Son maçtan bugünkü maça saat dilimi farkına göre seyahat yorgunluk cezasını döner.
    Döner: 0.0 - 0.04 (float penalty, prediction.py'de h/a_score'dan düşülür)
    """
    if not form_matches:
        return 0.0

    last_match    = form_matches[-1]   # form eski→yeni sıralı, en son = son eleman
    last_was_home = last_match.get("is_home", True)

    # Son maçın oynanduğu şehrin saat dilimi
    if last_was_home:
        last_tz = NBA_CITY_TIMEZONE.get(team_name, -6)
    else:
        opp_full = last_match.get("opponent_full_name") or last_match.get("home_team", "")
        last_tz  = NBA_CITY_TIMEZONE.get(opp_full, -6)

    # Bugünkü maçın oynandığı şehrin saat dilimi
    today_tz = NBA_CITY_TIMEZONE.get(team_name, -6) if is_home_today else NBA_CITY_TIMEZONE.get(opponent_name, -6)

    tz_diff = abs(today_tz - last_tz)
    if tz_diff == 0:   return 0.0
    if tz_diff == 1:   return 0.01
    if tz_diff == 2:   return 0.025
    return 0.04   # 3+ saat dilimi farkı


# ── Geçmiş maç sonuçları ──────────────────────────────────────────────────────

def get_nba_results_by_date(date_str: str) -> list[dict]:
    """Belirtilen tarihteki tamamlanmış NBA maçlarını döner (MM/DD/YYYY)."""
    cache_key = f"results_{date_str.replace('/', '-')}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    from nba_api.stats.static import teams as nba_static
    all_teams = {t["id"]: t["full_name"] for t in nba_static.get_teams()}

    matches = []
    try:
        from nba_api.stats.endpoints.scoreboardv2 import ScoreboardV2
        board = ScoreboardV2(game_date=date_str, league_id="00")
        games_df    = board.game_header.get_data_frame()
        line_score  = board.line_score.get_data_frame()

        # Skor tablosu oluştur
        scores: dict[str, dict] = {}
        for _, row in line_score.iterrows():
            tid = int(row["TEAM_ID"])
            gid = str(row["GAME_ID"])
            scores.setdefault(gid, {})[tid] = int(row.get("PTS", 0) or 0)

        seen_ids: set[str] = set()
        for _, row in games_df.iterrows():
            status_id = int(row.get("GAME_STATUS_ID", 0))
            if status_id != 3:
                continue  # yalnızca tamamlanmış maçlar

            game_id = str(row["GAME_ID"])
            if game_id in seen_ids:
                continue  # çift kayıtı atla
            seen_ids.add(game_id)

            home_id = int(row["HOME_TEAM_ID"])
            away_id = int(row["VISITOR_TEAM_ID"])
            game_scores = scores.get(game_id, {})

            matches.append({
                "match_id":     game_id,
                "home_team":    all_teams.get(home_id, str(home_id)),
                "away_team":    all_teams.get(away_id, str(away_id)),
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_logo":    f"https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg",
                "away_logo":    f"https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg",
                "home_score":   game_scores.get(home_id, 0),
                "away_score":   game_scores.get(away_id, 0),
                "status":       row.get("GAME_STATUS_TEXT", "Final"),
            })
    except Exception as e:
        print(f"[NBA] Sonuçlar hatası ({date_str}): {e}")

    if matches:
        _save_cache(cache_key, matches)
    return matches


def get_nba_box_score(game_id: str, home_team_id: int = None, away_team_id: int = None) -> dict:
    """Belirtilen NBA maçının oyuncu istatistiklerini döner."""
    # NBA game ID 10 haneli olmalı (leading zero'lar korunur)
    game_id = str(game_id).zfill(10)
    cache_key = f"boxscore_{game_id}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    result: dict = {"home": [], "away": [], "error": None}
    try:
        from nba_api.stats.endpoints.boxscoretraditionalv3 import BoxScoreTraditionalV3
        time.sleep(1.0)  # rate limiting
        box = BoxScoreTraditionalV3(game_id=game_id)
        df  = box.get_data_frames()[0]  # player stats

        # Takım sırasını belirle
        teams_in_df = df["teamId"].unique().tolist()
        if not home_team_id and len(teams_in_df) >= 1:
            home_team_id = teams_in_df[0]
        if not away_team_id and len(teams_in_df) >= 2:
            away_team_id = teams_in_df[1]

        for _, row in df.iterrows():
            min_str = str(row.get("minutes", "") or "")
            if not min_str or min_str in ("nan", "None", ""):
                continue
            # Dakika formatı "PT35M22.00S" → "35:22" ya da zaten "35:22"
            if min_str.startswith("PT"):
                import re
                m = re.match(r"PT(\d+)M([\d.]+)S", min_str)
                min_display = f"{m.group(1)}:{int(float(m.group(2))):02d}" if m else min_str
            else:
                min_display = min_str.split(".")[0] if "." in min_str else min_str

            tid = int(row["teamId"])
            player = {
                "name":        f"{row.get('firstName', '')} {row.get('familyName', '')}".strip(),
                "pos":         str(row.get("position", "") or ""),
                "min":         min_display,
                "pts":         int(row.get("points", 0) or 0),
                "reb":         int(row.get("reboundsTotal", 0) or 0),
                "ast":         int(row.get("assists", 0) or 0),
                "stl":         int(row.get("steals", 0) or 0),
                "blk":         int(row.get("blocks", 0) or 0),
                "fg":          f"{int(row.get('fieldGoalsMade', 0) or 0)}/{int(row.get('fieldGoalsAttempted', 0) or 0)}",
                "fg3":         f"{int(row.get('threePointersMade', 0) or 0)}/{int(row.get('threePointersAttempted', 0) or 0)}",
                "plus_minus":  int(row.get("plusMinusPoints", 0) or 0),
            }

            if tid == home_team_id:
                result["home"].append(player)
            else:
                result["away"].append(player)

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        print(f"[NBA] BoxScore hatası ({game_id}): {err_msg}")
        result["error"] = err_msg

    if result["home"] or result["away"]:
        _save_cache(cache_key, result)
    return result
