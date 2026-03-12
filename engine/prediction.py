"""
Tahmin motoru:
  - Form skoru & trend analizi (son 3 vs son 6)
  - Dinlenme günü faktörü
  - Poisson gol modeli (futbol) → 1/X/2, BTTS, O/U 2.5 & 3.5, doğru skor matrisi
  - Bradley-Terry modeli (NBA)
  - Value bet tespiti
"""
from __future__ import annotations

import math
from datetime import datetime, date as date_type

import numpy as np

from config import (
    HOME_ADVANTAGE,
    RECENCY_WEIGHTS,
    RESULT_POINTS,
    VALUE_BET_EDGE_THRESHOLD,
    LEAGUE_AVG_GOALS_HOME,
    LEAGUE_AVG_GOALS_AWAY,
    DIXON_COLES_RHO,
    NBA_LEAGUE_AVG_ORTG,
    NBA_LEAGUE_AVG_DRTG,
    NBA_LEAGUE_AVG_PACE,
)


# ── Poisson yardımcısı ──────────────────────────────────────────────────────────

def _poisson_pmf(k: int, lam: float) -> float:
    """Poisson PMF: P(X=k; λ)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _dixon_coles_tau(i: int, j: int, lam_h: float, lam_a: float) -> float:
    """
    Dixon-Coles (1997) düzeltme faktörü.
    Standart Poisson 0-0, 1-0, 0-1, 1-1 skorlarını sistematik olarak
    yanlış tahmin eder; bu fonksiyon o sapmaları giderir.
    ρ = DIXON_COLES_RHO (≈ −0.13) ile bağımsızlık varsayımı yumuşatılır.
    """
    rho = DIXON_COLES_RHO
    if i == 0 and j == 0:
        return max(0.0, 1.0 - lam_h * lam_a * rho)
    if i == 1 and j == 0:
        return max(0.0, 1.0 + lam_a * rho)
    if i == 0 and j == 1:
        return max(0.0, 1.0 + lam_h * rho)
    if i == 1 and j == 1:
        return max(0.0, 1.0 - rho)
    return 1.0


# ── NBA olasılık kalibrasyonu ────────────────────────────────────────────────

def _calibrate_nba_prob(p: float) -> float:
    """
    Ham Bradley-Terry olasılığını NBA için gerçekçi aralığa çeker.
    Logit sıkıştırma (0.65): p=0.82 → ~0.73, p=0.70 → ~0.65
    NBA'de en büyük favori bile nadiren %73 üzerinde kazanır.
    """
    p = max(0.001, min(0.999, p))
    logit_p = math.log(p / (1 - p))
    return 1.0 / (1.0 + math.exp(-logit_p * 0.65))


# ── Form skoru ─────────────────────────────────────────────────────────────────

def calculate_form_score(matches: list[dict], as_home: bool | None = None) -> float:
    """
    Son maçlara ağırlıklı form skoru hesaplar (0-1 arası).
    as_home=True → sadece ev maçları, False → deplasman, None → hepsi
    matches: eski → yeni sıralı (en yeni en sonda)
    """
    filtered = matches
    if as_home is not None:
        filtered = [m for m in matches if m.get("is_home") == as_home]

    if not filtered:
        return 0.5

    recent = list(reversed(filtered))   # yeni → eski
    weights = RECENCY_WEIGHTS[:len(recent)]

    total_w      = sum(weights)
    weighted_sum = sum(
        RESULT_POINTS.get(m["result"], 0) * w
        for m, w in zip(recent, weights)
    )
    return weighted_sum / (3.0 * total_w)


def calculate_form_trend(matches: list[dict]) -> dict:
    """
    Son 3 maç vs son 6 maç form karşılaştırması → ⬆/⬇/➡ trend.
    matches: eski → yeni sıralı
    """
    if len(matches) < 3:
        return {"trend": "➡ Stabil", "last3": 50.0, "last6": 50.0, "delta": 0.0}

    last3 = calculate_form_score(matches[-3:])
    last6 = calculate_form_score(matches[-min(6, len(matches)):])
    delta = last3 - last6

    if delta > 0.07:
        trend = "⬆ Yükselen"
    elif delta < -0.07:
        trend = "⬇ Düşen"
    else:
        trend = "➡ Stabil"

    return {
        "trend": trend,
        "last3": round(last3 * 100, 1),
        "last6": round(last6 * 100, 1),
        "delta": round(delta * 100, 1),
    }


def calculate_rest_days(matches: list[dict]) -> int | None:
    """Form maçlarından son maç tarihini bulur, bugünden farkını (gün) döner."""
    if not matches:
        return None
    dates = []
    for m in matches:
        d = m.get("date", "")
        if d:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    dates.append(datetime.strptime(d, fmt).date())
                    break
                except ValueError:
                    continue
    if not dates:
        return None
    return (date_type.today() - max(dates)).days


def calculate_nba_opp_adj_form(matches: list[dict]) -> float:
    """
    Rakip kalitesine göre düzeltilmiş NBA form skoru.
    Güçlü rakibe galibiyet daha değerli, zayıf rakibe mağlubiyet daha ağır cezalandırılır.
    Her maçtaki 'opponent_net_rtg' alanı opsiyonel — eksikse düz form skoru kullanılır.
    """
    if not matches:
        return 0.5

    recent  = list(reversed(matches))
    weights = RECENCY_WEIGHTS[:len(recent)]
    total_w = sum(weights)

    scores = []
    for m in recent:
        wl   = 1.0 if m.get("result") == "W" else 0.0
        pd   = (m.get("goals_for", 0) or 0) - (m.get("goals_against", 0) or 0)
        pd_n = max(0.0, min(1.0, (pd + 25) / 50))
        base = 0.60 * wl + 0.40 * pd_n

        opp_net_rtg = m.get("opponent_net_rtg", None)
        if opp_net_rtg is not None:
            # -8..+8 → 0.75..1.25 çarpanı
            quality_mult = max(0.75, min(1.25, 1.0 + float(opp_net_rtg) / 32))
            if wl > 0.5:   # galibiyet: güçlü rakip → daha değerli
                base = min(1.0, base * quality_mult)
            else:           # mağlubiyet: zayıf rakip → daha ağır ceza
                base = max(0.0, base * (2.0 - quality_mult))

        scores.append(base)

    return sum(s * w for s, w in zip(scores, weights)) / total_w


def _nba_scoring_trend(form_matches: list[dict]) -> float:
    """
    Son 3 maç PPG / tüm form PPG oranı.
    Sıcak (ısınan) takım 1.0+ değer, soğuyan takım <1.0 değer alır.
    Aralık: [0.92, 1.08]
    """
    if len(form_matches) < 4:
        return 1.0
    all_ppg  = sum(m.get("goals_for", 100) or 100 for m in form_matches) / len(form_matches)
    last3_ppg = sum(m.get("goals_for", 100) or 100 for m in form_matches[-3:]) / 3
    if all_ppg == 0:
        return 1.0
    return max(0.92, min(1.08, last3_ppg / all_ppg))


def _motivation_factor(standing: dict | None) -> float:
    """
    Lig sırasına göre motivasyon çarpanı (futbol).
    Şampiyonluk veya küme düşme yarışındaki takımlar daha motive.
    """
    if not standing:
        return 1.0
    rank  = standing.get("rank", 0)
    total = standing.get("total_teams", 20)
    if rank == 0 or total == 0:
        return 1.0
    if rank <= 3:                    return 1.03   # şampiyonluk yarışı
    if rank <= 6:                    return 1.01   # Avrupa kupası hattı
    if rank >= total - 2:            return 1.04   # küme düşme bölgesi
    if rank >= total - 5:            return 1.02   # küme düşme tehlikesi
    return 1.0


def calculate_nba_form_score(matches: list[dict], as_home: bool | None = None) -> float:
    """
    NBA'ye özel form skoru: W/L (%60) + normalize edilmiş point differential (%40).
    Salt galibiyet/mağlubiyet yerine skor farkını da hesaba katar.
    PD normalizasyon: +25 sayı fark → 1.0, -25 → 0.0, 0 → 0.5
    """
    filtered = matches
    if as_home is not None:
        filtered = [m for m in matches if m.get("is_home") == as_home]
    if not filtered:
        return 0.5

    recent  = list(reversed(filtered))   # yeni → eski
    weights = RECENCY_WEIGHTS[:len(recent)]
    total_w = sum(weights)

    scores = []
    for m in recent:
        wl   = 1.0 if m.get("result") == "W" else 0.0
        pd   = (m.get("goals_for", 0) or 0) - (m.get("goals_against", 0) or 0)
        pd_n = max(0.0, min(1.0, (pd + 25) / 50))   # -25..+25 → 0..1
        scores.append(0.60 * wl + 0.40 * pd_n)

    return sum(s * w for s, w in zip(scores, weights)) / total_w


def calculate_goal_stats(matches: list[dict]) -> dict:
    """Ortalama atılan/yenilen gol ve 2.5 üstü oranı."""
    if not matches:
        return {"avg_for": 1.3, "avg_against": 1.3, "over25_rate": 0.5}

    goals_for     = [m["goals_for"]     for m in matches if "goals_for"     in m]
    goals_against = [m["goals_against"] for m in matches if "goals_against" in m]

    avg_for     = float(np.mean(goals_for))     if goals_for     else 1.3
    avg_against = float(np.mean(goals_against)) if goals_against else 1.3

    total_goals = [f + a for f, a in zip(goals_for, goals_against)]
    over25_rate = sum(1 for g in total_goals if g > 2.5) / len(total_goals) if total_goals else 0.5

    return {
        "avg_for":      round(avg_for, 2),
        "avg_against":  round(avg_against, 2),
        "over25_rate":  round(over25_rate, 2),
    }


# ── Poisson skor matrisi ────────────────────────────────────────────────────────

def compute_poisson_probs(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 8,
) -> dict:
    """
    Tam Poisson skor matrisiyle maç olasılıklarını hesaplar.
    Döndürür: home_win, draw, away_win, btts, over25, over35, correct_scores (top 9)
    """
    score_probs: dict[tuple[int, int], float] = {}
    p_home_win = p_draw = p_away_win = 0.0

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = (_poisson_pmf(i, lambda_home)
                 * _poisson_pmf(j, lambda_away)
                 * _dixon_coles_tau(i, j, lambda_home, lambda_away))
            score_probs[(i, j)] = p
            if i > j:
                p_home_win += p
            elif i == j:
                p_draw += p
            else:
                p_away_win += p

    # BTTS: her iki takım ≥ 1 gol
    p_btts = (1 - _poisson_pmf(0, lambda_home)) * (1 - _poisson_pmf(0, lambda_away))

    # Over 2.5 ve Over 3.5
    p_over25 = sum(p for (i, j), p in score_probs.items() if i + j > 2)
    p_over35 = sum(p for (i, j), p in score_probs.items() if i + j > 3)

    # Top 9 skor
    top9 = sorted(score_probs.items(), key=lambda x: -x[1])[:9]
    correct_scores = [
        {"score": f"{i}-{j}", "prob": round(p * 100, 1)}
        for (i, j), p in top9
    ]

    # Normalize (kesim hatasını düzelt)
    total = p_home_win + p_draw + p_away_win
    if total > 0:
        p_home_win /= total
        p_draw     /= total
        p_away_win /= total

    return {
        "home_win":       round(p_home_win, 4),
        "draw":           round(p_draw,     4),
        "away_win":       round(p_away_win, 4),
        "btts":           round(p_btts,     4),
        "over25":         round(p_over25,   4),
        "over35":         round(p_over35,   4),
        "correct_scores": correct_scores,
        "lambda_home":    round(lambda_home, 3),
        "lambda_away":    round(lambda_away, 3),
    }


# ── Lig-normalize lambda hesabı (Maher / Dixon-Coles modeli) ───────────────────

def _league_normalized_lambdas(
    home_season_stats: dict | None,
    away_season_stats: dict | None,
    h_goals: dict,
    a_goals: dict,
) -> tuple[float, float]:
    """
    Her takımın hücum/savunma gücünü lig ortalamasına bölerek normalize eder.
      lambda_ev  = hücum_ev  × savunma_zafiyeti_dep × lig_ort_ev
      lambda_dep = hücum_dep × savunma_zafiyeti_ev  × lig_ort_dep
    Season stats varsa daha güvenilir; yoksa form maçlarından tahmin edilir.
    """
    avg_h = LEAGUE_AVG_GOALS_HOME
    avg_a = LEAGUE_AVG_GOALS_AWAY

    if home_season_stats and away_season_stats:
        h_atk = (home_season_stats.get("avg_goals_for_home")     or avg_h) / avg_h
        h_def = (home_season_stats.get("avg_goals_against_home") or avg_a) / avg_a
        a_atk = (away_season_stats.get("avg_goals_for_away")     or avg_a) / avg_a
        a_def = (away_season_stats.get("avg_goals_against_away") or avg_h) / avg_h
    else:
        h_atk = h_goals["avg_for"]      / avg_h
        h_def = h_goals["avg_against"]  / avg_a
        a_atk = a_goals["avg_for"]      / avg_a
        a_def = a_goals["avg_against"]  / avg_h

    lam_h = h_atk * a_def * avg_h
    lam_a = a_atk * h_def * avg_a
    return max(0.1, lam_h), max(0.1, lam_a)


# ── Monte Carlo güven aralığı ──────────────────────────────────────────────────

def _monte_carlo_ci(lam_h: float, lam_a: float, n: int = 600) -> dict:
    """
    Lambda değerlerine %10 Gaussian gürültü ekleyerek n simülasyon çalıştırır.
    Her sonuç için [p10, ortalama, p90] güven aralığı döner.
    """
    rng = np.random.default_rng(42)
    noise_h = rng.normal(1.0, 0.10, n)
    noise_a = rng.normal(1.0, 0.10, n)

    hw, dr, aw = [], [], []
    for nh, na in zip(noise_h, noise_a):
        p = compute_poisson_probs(max(0.1, lam_h * nh), max(0.1, lam_a * na))
        hw.append(p["home_win"])
        dr.append(p["draw"])
        aw.append(p["away_win"])

    def _ci(arr: list) -> dict:
        a = np.array(arr)
        return {
            "low":  round(float(np.percentile(a, 10)) * 100, 1),
            "mid":  round(float(np.mean(a))            * 100, 1),
            "high": round(float(np.percentile(a, 90))  * 100, 1),
        }

    return {"home": _ci(hw), "draw": _ci(dr), "away": _ci(aw)}


# ── Ana tahmin ─────────────────────────────────────────────────────────────────

def predict_match(
    home_form:    list[dict],
    away_form:    list[dict],
    h2h:          list[dict] | None = None,
    home_odds:    float | None = None,
    draw_odds:    float | None = None,
    away_odds:    float | None = None,
    no_draw:      bool = False,
    home_b2b:     bool = False,
    away_b2b:     bool = False,
    home_ratings: dict | None = None,
    away_ratings: dict | None = None,
    home_load_flags: list | None = None,
    away_load_flags: list | None = None,
    home_season_stats: dict | None = None,
    away_season_stats: dict | None = None,
    home_travel_penalty: float = 0.0,
    away_travel_penalty: float = 0.0,
    home_standing: dict | None = None,
    away_standing: dict | None = None,
) -> dict:
    """
    Maç tahmini döner:
      - probabilities: 1/X/2 olasılıkları
      - prediction / confidence / value_bets
      - home/away_form_trend: ⬆/⬇/➡ trend
      - home/away_rest_days: son maçtan bu yana gün
      - btts_prob, over25_prob, over35_prob
      - correct_scores: top-9 en olası skor
      - goal_prediction / exp_total_goals
    """

    # ── Form trend & dinlenme günü ────────────────────────────────────────────
    home_trend = calculate_form_trend(home_form)
    away_trend = calculate_form_trend(away_form)
    home_rest  = calculate_rest_days(home_form)
    away_rest  = calculate_rest_days(away_form)

    # NBA mı yoksa futbol mu?
    is_nba = no_draw or (bool(home_ratings) and "net_rtg" in (home_ratings or {}))

    # ══════════════════════════════════════════════════════════════════════════
    # FUTBOL — Poisson modeli
    # ══════════════════════════════════════════════════════════════════════════
    if not is_nba:
        h_goals = calculate_goal_stats(home_form)
        a_goals = calculate_goal_stats(away_form)

        # Expected goals hesabı
        if home_season_stats and "avg_goals_for_home" in home_season_stats:
            lam_h = (float(home_season_stats.get("avg_goals_for_home", 0) or 0) +
                     float(away_season_stats.get("avg_goals_against_away", 0) if away_season_stats else 0 or 0)) / 2
            lam_a = (float(away_season_stats.get("avg_goals_for_away",    0) if away_season_stats else 0 or 0) +
                     float(home_season_stats.get("avg_goals_against_home", 0) or 0)) / 2
        else:
            lam_h = (h_goals["avg_for"] + a_goals["avg_against"]) / 2
            lam_a = (a_goals["avg_for"] + h_goals["avg_against"]) / 2

        lam_h = max(0.1, lam_h or h_goals["avg_for"])
        lam_a = max(0.1, lam_a or a_goals["avg_for"])

        # Ev sahibi avantajı
        lam_h *= HOME_ADVANTAGE

        # Dinlenme/yorgunluk cezası
        if home_rest is not None:
            if home_rest < 3:
                lam_h *= 0.92   # yorgunluk
            elif home_rest > 7:
                lam_h *= 0.97   # pas tutma
        if away_rest is not None:
            if away_rest < 3:
                lam_a *= 0.92
            elif away_rest > 7:
                lam_a *= 0.97

        # B2B cezası
        if home_b2b:
            lam_h *= 0.93
        if away_b2b:
            lam_a *= 0.93

        # H2H düzeltmesi
        if h2h:
            h2h_score  = calculate_form_score(h2h)
            h2h_factor = 0.9 + h2h_score * 0.2    # 0.90 – 1.10
            lam_h *= h2h_factor
            lam_a *= (2.0 - h2h_factor)             # ters etki (0.90 – 1.10 ayna)

        # Motivasyon faktörü (lig sırası)
        lam_h *= _motivation_factor(home_standing)
        lam_a *= _motivation_factor(away_standing)

        lam_h = max(0.1, lam_h)
        lam_a = max(0.1, lam_a)

        pois = compute_poisson_probs(lam_h, lam_a)

        p_home = pois["home_win"]
        p_draw = pois["draw"]
        p_away = pois["away_win"]
        btts_prob  = round(pois["btts"]   * 100, 1)
        over25_prob = round(pois["over25"] * 100, 1)
        over35_prob = round(pois["over35"] * 100, 1)
        correct_scores  = pois["correct_scores"]
        exp_total_goals  = round(lam_h + lam_a, 2)
        goal_prediction  = "Üst 2.5" if pois["over25"] >= 0.52 else "Alt 2.5"

    # ══════════════════════════════════════════════════════════════════════════
    # NBA — Bradley-Terry modeli (geliştirilmiş)
    # ══════════════════════════════════════════════════════════════════════════
    else:
        # 1) Rakip kalitesi düzeltmeli form (point differential dahil)
        h_form_g  = calculate_nba_opp_adj_form(home_form)
        a_form_g  = calculate_nba_opp_adj_form(away_form)

        # Ev/deplasman alt-form (yeterli örnek varsa)
        h_ev_count  = sum(1 for m in home_form if m.get("is_home") is True)
        a_dep_count = sum(1 for m in away_form if m.get("is_home") is False)

        h_form_ev  = calculate_nba_form_score(home_form, as_home=True)  if h_ev_count  >= 2 else h_form_g
        a_form_dep = calculate_nba_form_score(away_form, as_home=False) if a_dep_count >= 2 else a_form_g

        h_form = 0.55 * h_form_g + 0.45 * h_form_ev
        a_form = 0.55 * a_form_g + 0.45 * a_form_dep

        # Skoring trendi: son 3 maç ısınıyor mu soğuyor mu?
        h_trend_mult = _nba_scoring_trend(home_form)
        a_trend_mult = _nba_scoring_trend(away_form)
        h_form = max(0.05, min(0.97, h_form * h_trend_mult))
        a_form = max(0.05, min(0.97, a_form * a_trend_mult))

        # 2) Net rating — düzeltilmiş normalizasyon aralığı (-8 / +8)
        #    NBA'de gerçek aralık yaklaşık -7 ile +8 arası; -15/+15 farkları sıkıştırıyordu
        if home_ratings and "net_rtg" in home_ratings:
            h_net_norm = max(0.0, min(1.0, (home_ratings["net_rtg"] + 8) / 16))
            a_net_norm = max(0.0, min(1.0, (away_ratings.get("net_rtg", 0) + 8) / 16)) if away_ratings else 0.5

            # Lokasyon kazanma yüzdesi varsa ağırlığa dahil et
            h_hwpct = home_ratings.get("home_wpct", None)
            a_awpct = away_ratings.get("away_wpct", None) if away_ratings else None

            if h_hwpct is not None and a_awpct is not None:
                # Form %25 + Net_rtg %50 + Lokasyon W% %25
                h_score = 0.25 * h_form + 0.50 * h_net_norm + 0.25 * h_hwpct
                a_score = 0.25 * a_form + 0.50 * a_net_norm + 0.25 * a_awpct
            else:
                # Form %35 + Net_rtg %65
                h_score = 0.35 * h_form + 0.65 * h_net_norm
                a_score = 0.35 * a_form + 0.65 * a_net_norm
        else:
            h_score = h_form
            a_score = a_form

        # 3) PIE ağırlıklı load management cezası (etki skoruna göre kişiselleştirilmiş)
        NBA_LOAD_MAX = 0.20
        if home_load_flags:
            # Her yıldızın PIE impact skoruna göre ceza: base 0.035 × (0.5 + impact)
            h_penalty = sum(0.035 * (0.5 + f.get("impact", 0.5)) for f in home_load_flags)
            h_score = max(0.05, h_score - min(h_penalty, NBA_LOAD_MAX))
        if away_load_flags:
            a_penalty = sum(0.035 * (0.5 + f.get("impact", 0.5)) for f in away_load_flags)
            a_score = max(0.05, a_score - min(a_penalty, NBA_LOAD_MAX))

        # 4) B2B cezası
        B2B_PENALTY = 0.07
        if home_b2b:
            h_score = max(0.05, h_score - B2B_PENALTY)
        if away_b2b:
            a_score = max(0.05, a_score - B2B_PENALTY)

        # 5) Seyahat yorgunluğu
        if home_travel_penalty > 0:
            h_score = max(0.05, h_score - home_travel_penalty)
        if away_travel_penalty > 0:
            a_score = max(0.05, a_score - away_travel_penalty)

        # 6) Ev sahibi avantajı — toplamalı (+0.04) daha kontrollü etki verir
        NBA_HOME_BOOST = 0.04
        h_score_adj = min(0.97, h_score + NBA_HOME_BOOST)

        # 7) Pace uyuşmazlığı: deplasman daha hızlıysa ev sahibi avantajı biraz azalır
        home_pace = (home_ratings or {}).get("pace")
        away_pace = (away_ratings or {}).get("pace")
        if home_pace and away_pace:
            pace_diff = (float(away_pace) - float(home_pace)) / 100.0
            h_score_adj = max(0.05, h_score_adj - pace_diff * 0.025)

        # 8) H2H düzeltmesi
        if h2h:
            h2h_score   = calculate_form_score(h2h)
            h_score_adj = h_score_adj * 0.85 + h2h_score * 0.15

        # 9) Bradley-Terry oranı
        total  = h_score_adj + a_score + 0.001
        p_home = h_score_adj / total
        p_away = a_score     / total
        p_draw = 0.0
        total_pa = p_home + p_away
        if total_pa > 0:
            p_home /= total_pa
            p_away /= total_pa

        # 10) Gerçekçi NBA aralığına kalibre et (logit sıkıştırma)
        p_home = _calibrate_nba_prob(p_home)
        p_away = 1.0 - p_home

        btts_prob        = 0.0
        over25_prob      = 0.0
        over35_prob      = 0.0
        correct_scores   = []
        exp_total_goals  = 0.0
        goal_prediction  = "—"

    # ── Son yuvarlama ─────────────────────────────────────────────────────────
    p_home = round(p_home, 3)
    p_draw = round(p_draw, 3)
    p_away = round(max(0.0, 1.0 - p_home - p_draw), 3)

    # ── Tahmin & güven ────────────────────────────────────────────────────────
    probs      = {"home": p_home, "draw": p_draw, "away": p_away}
    best_label = max(probs, key=probs.__getitem__)
    confidence = round(probs[best_label] * 100, 1)
    prediction = {"home": "1", "draw": "X", "away": "2"}[best_label]

    # ── Value bet ─────────────────────────────────────────────────────────────
    value_bets = []
    for market, odd_key, our_p in [
        ("1 (Ev)",         home_odds, p_home),
        ("X (Beraberlik)", draw_odds, p_draw),
        ("2 (Deplasman)",  away_odds, p_away),
    ]:
        if odd_key and odd_key > 1.0:
            implied_p = round(1 / odd_key, 3)
            edge      = round(our_p - implied_p, 3)
            if edge >= VALUE_BET_EDGE_THRESHOLD:
                value_bets.append({
                    "market":       market,
                    "odd":          odd_key,
                    "our_prob":     round(our_p * 100, 1),
                    "implied_prob": round(implied_p * 100, 1),
                    "edge":         round(edge * 100, 1),
                })

    return {
        "probabilities":    probs,
        "prediction":       prediction,
        "confidence":       confidence,
        "goal_prediction":  goal_prediction,
        "exp_total_goals":  exp_total_goals,
        "over25_prob":      over25_prob,
        "over35_prob":      over35_prob,
        "btts_prob":        btts_prob,
        "correct_scores":   correct_scores,
        "value_bets":       value_bets,
        "home_form_score":  round(calculate_form_score(home_form) * 100, 1),
        "away_form_score":  round(calculate_form_score(away_form) * 100, 1),
        "home_form_trend":  home_trend,
        "away_form_trend":  away_trend,
        "home_rest_days":   home_rest,
        "away_rest_days":   away_rest,
        "home_b2b":         home_b2b,
        "away_b2b":         away_b2b,
        "home_ratings":     home_ratings or {},
        "away_ratings":     away_ratings or {},
        "home_load_flags":  home_load_flags or [],
        "away_load_flags":  away_load_flags or [],
    }
