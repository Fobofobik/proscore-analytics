import os
from dotenv import load_dotenv

load_dotenv()

def _get_secret(key: str) -> str:
    """Önce .env / ortam değişkenine, yoksa Streamlit secrets'a bakar."""
    val = os.getenv(key, "")
    if not val:
        try:
            import streamlit as st
            val = st.secrets.get(key, "")
        except Exception:
            pass
    return val

# ── The Odds API ───────────────────────────────────────────────────────────────
ODDS_API_KEY = _get_secret("ODDS_API_KEY")

# ── API-Football ──────────────────────────────────────────────────────────────
API_FOOTBALL_KEY     = _get_secret("API_FOOTBALL_KEY")
API_FOOTBALL_BASE    = "https://v3.football.api-sports.io"
API_FOOTBALL_HEADERS = {
    "x-apisports-key": API_FOOTBALL_KEY,
}
SUPER_LIG_ID       = 203   # API-Football Türkiye Süper Lig ID
PREMIER_LEAGUE_ID  = 39    # API-Football İngiltere Premier League ID
CURRENT_SEASON     = 2024  # Sezon yılı
FORM_MATCH_COUNT   = 6     # kaç maç geriye bakılsın

LEAGUES = {
    "Süper Lig":      {"id": 203, "season": 2024, "sport": "football", "logo": "https://media.api-sports.io/football/leagues/203.png"},
    "Premier League": {"id": 39,  "season": 2024, "sport": "football", "logo": "https://media.api-sports.io/football/leagues/39.png"},
    "Bundesliga":     {"id": 78,  "season": 2024, "sport": "football", "logo": "https://media.api-sports.io/football/leagues/78.png"},
    "Serie A":        {"id": 135, "season": 2024, "sport": "football", "logo": "https://media.api-sports.io/football/leagues/135.png"},
    "Ligue 1":        {"id": 61,  "season": 2024, "sport": "football", "logo": "https://media.api-sports.io/football/leagues/61.png"},
    "NBA":            {"id": None, "season": 2024, "sport": "nba",      "logo": "https://cdn.nba.com/logos/leagues/logo-nba.svg"},
}

# ── Tahmin ağırlıkları ────────────────────────────────────────────────────────
# Son maçlara daha yüksek ağırlık verilir (yeni → eski)
RECENCY_WEIGHTS = [1.0, 0.85, 0.70, 0.55, 0.40, 0.30]

# Gol / Galip sonuç başına puan
RESULT_POINTS = {"W": 3, "D": 1, "L": 0}

# Ev sahibi avantajı çarpanı
HOME_ADVANTAGE = 1.08

# Sakatlık etkisi: her sakat kilit oyuncu için takım gücünden düşülecek %
INJURY_PENALTY_PER_PLAYER = 0.04   # %4

# Value bet eşiği: bizim olasılığımız ile implied probability arasındaki min fark
VALUE_BET_EDGE_THRESHOLD = 0.05    # %5

# ── Futbol lig ortalamaları (Avrupa ortalaması) ───────────────────────────────
# Maher/Dixon-Coles modelinde lambda normalizasyonu için referans değerler
LEAGUE_AVG_GOALS_HOME = 1.50   # ev sahibinin maç başı ortalama golü
LEAGUE_AVG_GOALS_AWAY = 1.15   # deplasmanın maç başı ortalama golü

# Dixon-Coles düzeltme katsayısı (negatif değer → küçük skor çiftlerini düzeltir)
# Literatür: ρ ≈ −0.13  (Dixon & Coles, 1997)
DIXON_COLES_RHO = -0.13

# ── NBA lig ortalamaları (2023-24 sezonu NBA.com) ─────────────────────────────
NBA_LEAGUE_AVG_ORTG = 115.0   # 100 atakta ortalama sayı
NBA_LEAGUE_AVG_DRTG = 115.0
NBA_LEAGUE_AVG_PACE = 100.0   # 48 dakikada ortalama atak sayısı

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_DIR     = "data"
CACHE_TTL_MIN = 30   # dakika
