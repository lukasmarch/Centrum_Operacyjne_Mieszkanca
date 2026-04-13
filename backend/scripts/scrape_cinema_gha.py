"""
Cinema scraper dla GitHub Actions.

Uruchamiany codziennie przez .github/workflows/cinema_scrape.yml.
Nie importuje nic z projektu — działa jako standalone script.

GitHub Actions IP nie jest blokowany przez Cloudflare na biletyna.pl.
"""
import sys
import re
import json
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BACKEND_URL = os.environ.get("BACKEND_URL", "https://api.rybnolive.pl")
CINEMA_INGEST_TOKEN = os.environ["CINEMA_INGEST_TOKEN"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9",
}
BASE_URL = "https://biletyna.pl"


def scrape_dzialdowo():
    today = datetime.now().strftime("%d.%m.%Y")
    base = datetime.now()
    next_14_days = {(base + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(14)}

    print(f"[cinema] Scraping biletyna.pl/film/Dzialdowo...")
    resp = requests.get(f"{BASE_URL}/film/Dzialdowo", headers=HEADERS, timeout=20)
    print(f"[cinema] Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"[cinema] ERROR: got {resp.status_code}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select(".event-left-side")
    print(f"[cinema] Found {len(items)} movies on listing")

    movies = []
    seen_titles = set()

    for item in items:
        title_elem = item.select_one("h3 a")
        if not title_elem:
            continue

        title = title_elem.get_text(strip=True)
        href = title_elem.get("href", "")
        if not href:
            continue

        # Tylko filmy przypisane do Dzialdowo (href kończy się /Dzialdowo)
        if not href.rstrip("/").endswith("Dzialdowo"):
            print(f"[cinema] Skipping non-Dzialdowo href: {href}")
            continue

        if title in seen_titles:
            continue
        seen_titles.add(title)

        detail_url = f"{BASE_URL}{href}" if href.startswith("/") else href

        try:
            dr = requests.get(detail_url, headers=HEADERS, timeout=10)
            if dr.status_code != 200:
                print(f"[cinema] Detail {dr.status_code} for {title}")
                continue

            ds = BeautifulSoup(dr.text, "html.parser")

            # Poster
            og = ds.find("meta", property="og:image")
            poster = og.get("content", "") if og else ""

            # Seanse w ciągu 14 dni
            times = []
            for block in ds.select(".event-date"):
                dt = block.get_text(separator=" ", strip=True)
                if not any(f in dt for f in next_14_days | {"Dzisiaj", "Dziś"}):
                    continue
                dm = re.search(r"(\d{2}\.\d{2})\.\d{4}", dt)
                date_label = dm.group(1) if dm else ""
                ft = re.findall(r"godz\.\s*(\d{2}:\d{2})", dt) or re.findall(r"(?<!\d)(\d{2}:\d{2})(?!\d)", dt)
                for t in ft:
                    times.append(f"{date_label} {t}".strip() if date_label else t)

            times = sorted(set(times))
            if not times:
                print(f"[cinema] No times for: {title}")
                continue

            movies.append({
                "title": title,
                "times": times,
                "poster": poster,
                "link": detail_url,
            })
            print(f"[cinema] OK: {title} ({len(times)} seansów)")

        except Exception as e:
            print(f"[cinema] Error parsing {title}: {e}", file=sys.stderr)
            continue

    return movies


def post_to_backend(movies: list, cinema_name: str, date: str):
    url = f"{BACKEND_URL}/api/cinema/ingest"
    payload = {
        "cinema_name": cinema_name,
        "date": date,
        "movies": movies,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CINEMA_INGEST_TOKEN}",
    }
    print(f"[ingest] POSTing {len(movies)} movies to {url}")
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"[ingest] Response: {resp.status_code} {resp.text}")
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    today = datetime.now().strftime("%d.%m.%Y")
    movies = scrape_dzialdowo()

    if not movies:
        print("[cinema] No movies scraped — nothing to send", file=sys.stderr)
        sys.exit(1)

    result = post_to_backend(movies, "Kino Działdowo", today)
    print(f"[done] Saved {result.get('saved')} movies for {result.get('date')}")
