"""
Bilyoner.com üzerinden Süper Lig maçlarını ve oranlarını çeker.
Playwright kullanılır (JavaScript ağır site).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from config import (
    BILYONER_TC,
    BILYONER_PASSWORD,
    CACHE_DIR,
    CACHE_TTL_MIN,
)

BILYONER_URL     = "https://www.bilyoner.com"
LOGIN_URL        = f"{BILYONER_URL}/giris"
SUPER_LIG_URL    = (
    f"{BILYONER_URL}/iddaa/futbol/turkiye/super-lig"
)

# ── Cache ─────────────────────────────────────────────────────────────────────

def _cache_path() -> Path:
    Path(CACHE_DIR).mkdir(exist_ok=True)
    return Path(CACHE_DIR) / "bilyoner_matches.json"


def _load_cache() -> Optional[list]:
    p = _cache_path()
    if not p.exists():
        return None
    age_min = (time.time() - p.stat().st_mtime) / 60
    if age_min > CACHE_TTL_MIN:
        return None
    with open(p) as f:
        return json.load(f)


def _save_cache(data: list) -> None:
    with open(_cache_path(), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Ana scraper fonksiyonu ────────────────────────────────────────────────────

def get_bilyoner_matches(headless: bool = True) -> list[dict]:
    """
    Bilyoner'den Süper Lig maçlarını ve oranlarını çekip döner.
    Hata durumunda boş liste döner (uygulama çalışmaya devam eder).
    """
    cached = _load_cache()
    if cached:
        return cached

    matches = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="tr-TR",
        )
        page = ctx.new_page()

        try:
            # 1. Giriş yap
            if BILYONER_TC and BILYONER_PASSWORD:
                _login(page)

            # 2. Süper Lig sayfasına git
            page.goto(SUPER_LIG_URL, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(2000)

            # 3. Tüm maçları yükle (lazy load için scroll)
            _scroll_to_bottom(page)

            # 4. Maç verilerini çıkart
            matches = _extract_matches(page)

        except PWTimeout:
            print("[Bilyoner] Sayfa zaman aşımı – cache yoksa boş döner.")
        except Exception as e:
            print(f"[Bilyoner] Hata: {e}")
        finally:
            browser.close()

    if matches:
        _save_cache(matches)
    return matches


# ── Login ──────────────────────────────────────────────────────────────────────

def _login(page) -> None:
    try:
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=20_000)
        page.wait_for_timeout(1500)

        # TC Kimlik No
        tc_sel = "input[name='identityNumber'], input[placeholder*='T.C'], input[placeholder*='TC'], input[name='tc'], input[id*='tc']"
        page.fill(tc_sel, BILYONER_TC)

        # Şifre
        pw_sel = "input[type='password']"
        page.fill(pw_sel, BILYONER_PASSWORD)

        # Giriş butonu
        page.click("button[type='submit']")
        page.wait_for_timeout(3000)
        print("[Bilyoner] Giriş başarılı.")
    except Exception as e:
        print(f"[Bilyoner] Giriş hatası (devam ediliyor): {e}")


# ── Scroll ────────────────────────────────────────────────────────────────────

def _scroll_to_bottom(page) -> None:
    for _ in range(5):
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(600)


# ── Maç verisi çıkarma ────────────────────────────────────────────────────────

def _extract_matches(page) -> list[dict]:
    matches = []

    # Bilyoner'in DOM yapısı güncellenebilir; birden fazla selector dene
    selectors = [
        ".event-row",
        ".coupon-item",
        "[class*='eventRow']",
        "[class*='matchRow']",
        "[data-testid*='event']",
    ]

    rows = []
    for sel in selectors:
        rows = page.query_selector_all(sel)
        if rows:
            print(f"[Bilyoner] {len(rows)} maç satırı bulundu ({sel})")
            break

    if not rows:
        # Son çare: JSON içindeki veri (window.__INITIAL_STATE__ vb.)
        matches = _extract_from_page_source(page)
        return matches

    for row in rows:
        try:
            match = _parse_row(row)
            if match:
                matches.append(match)
        except Exception:
            continue

    return matches


def _parse_row(row) -> dict | None:
    text = row.inner_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 4:
        return None

    # Oranları bul (ondalık sayılar)
    odds_raw = re.findall(r"\d+[.,]\d+", text)
    odds = []
    for o in odds_raw:
        try:
            odds.append(float(o.replace(",", ".")))
        except ValueError:
            pass

    # Oranlar: genellikle 1/X/2 sırasıyla, 1'den büyük olanlar
    odds = [o for o in odds if o > 1.0]

    if len(odds) < 3:
        return None

    # Takım isimlerini bulmaya çalış
    team_els = row.query_selector_all("[class*='team'], [class*='Team']")
    if len(team_els) >= 2:
        home_team = team_els[0].inner_text().strip()
        away_team = team_els[1].inner_text().strip()
    else:
        # Ham metinden çıkar: oranlardan önceki kısmı al
        parts = re.split(r"\d+[.,]\d+", text)
        team_part = parts[0] if parts else ""
        teams = [t.strip() for t in team_part.split("\n") if t.strip() and len(t.strip()) > 2]
        if len(teams) < 2:
            return None
        home_team = teams[-2]
        away_team = teams[-1]

    # Saat bul
    time_match = re.search(r"\b(\d{2}:\d{2})\b", text)
    match_time = time_match.group(1) if time_match else "?"

    return {
        "home_team":  home_team,
        "away_team":  away_team,
        "match_time": match_time,
        "odds": {
            "home_win":  odds[0] if len(odds) > 0 else None,
            "draw":      odds[1] if len(odds) > 1 else None,
            "away_win":  odds[2] if len(odds) > 2 else None,
        },
        "source": "bilyoner",
    }


def _extract_from_page_source(page) -> list[dict]:
    """Sayfanın kaynak kodundan JSON verisi çekmeyi dener."""
    matches = []
    try:
        source = page.content()
        # Bilyoner bazen __NEXT_DATA__ veya __REDUX_STATE__ gibi global state kullanır
        pattern = re.compile(
            r'"homeTeam"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)".*?'
            r'"awayTeam"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"',
            re.DOTALL
        )
        for m in pattern.finditer(source):
            matches.append({
                "home_team":  m.group(1),
                "away_team":  m.group(2),
                "match_time": "?",
                "odds":       {"home_win": None, "draw": None, "away_win": None},
                "source":     "bilyoner_raw",
            })
    except Exception:
        pass
    return matches
