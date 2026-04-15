import logging
import re
import json
import os
from datetime import datetime
from typing import List, Optional, Dict
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class Movie(BaseModel):
    title: str
    genre: str = "Film"
    time: List[str]
    posterUrl: str
    rating: str = "N/A"
    link: Optional[str] = None

class CinemaRepertoire(BaseModel):
    cinemaName: str
    date: str
    movies: List[Movie]

class CinemaScraper:
    """
    Scraper dla kin lokalnych.

    Obsługuje:
    - Kino Pokój Lubawa (kino.lubawa.pl) — bezpośrednie HTTP scrapowanie
    - Kino Działdowo (biletyna.pl) — obsługiwane przez GitHub Actions
      (scrape_cinema_gha.py → POST /api/cinema/ingest), nie przez ten scraper
    """
    CACHE_DIR = "data/cache"

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def fetch_repertoire(self, city: str, force_update: bool = False) -> CinemaRepertoire:
        """Pobierz repertuar dla danego miasta."""
        city_slug = self._normalize_city(city)
        if not force_update:
            cached_data = self._load_cache(city_slug)
            if cached_data:
                return cached_data

        data = self._fetch_kino_lubawa_pl()
        if data and data.movies:
            self._save_cache(city_slug, data)
        return data

    async def fetch_repertoire_async(self, city: str, force_update: bool = False) -> CinemaRepertoire:
        """Async version — używany z cinema_job.py."""
        import asyncio
        city_slug = self._normalize_city(city)
        if not force_update:
            cached_data = self._load_cache(city_slug)
            if cached_data:
                return cached_data

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._fetch_kino_lubawa_pl)

        if data and data.movies:
            self._save_cache(city_slug, data)
        return data or CinemaRepertoire(cinemaName="Kino Pokój Lubawa (Błąd)", date="", movies=[])

    # -------------------------------------------------------------------------
    # Lubawa scraper (sync, działa bezpośrednio)
    # -------------------------------------------------------------------------

    def _fetch_kino_lubawa_pl(self) -> CinemaRepertoire:
        url = "https://kino.lubawa.pl/"
        try:
            response = requests.get(url, headers=self.headers, timeout=15, verify=False)
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')
            movies = []

            items = soup.select('.inweek')
            logger.info(f"KinoLubawa: Found {len(items)} items")

            for item in items:
                title_node = item.select_one('h4')
                if not title_node: continue

                title = title_node.get_text(strip=True)

                info_node = item.select_one('h5')
                info_text = info_node.get_text(separator=' ', strip=True) if info_node else ""

                MONTHS = {
                    'stycznia': '01', 'lutego': '02', 'marca': '03', 'kwietnia': '04',
                    'maja': '05', 'czerwca': '06', 'lipca': '07', 'sierpnia': '08',
                    'września': '09', 'października': '10', 'listopada': '11', 'grudnia': '12'
                }
                date_label = ""
                date_match = (
                    re.search(r'od\s+(\d{1,2})\s+do\s+\d{1,2}\s+(\w+)', info_text) or
                    re.search(r'od\s+(\d{1,2})\s+(\w+)', info_text) or
                    re.search(r'(\d{1,2})\s+(\w+)', info_text)
                )
                if date_match:
                    day = date_match.group(1).zfill(2)
                    month_name = date_match.group(2).lower()
                    month = MONTHS.get(month_name, '')
                    if month:
                        date_label = f"{day}.{month}"

                times_found = re.findall(r'(\d{2}:\d{2})', info_text)
                times = sorted(list(set(
                    f"{date_label} {t}".strip() if date_label else t
                    for t in times_found
                )))

                if not times:
                    times = [date_label if date_label else "Sprawdź godziny"]

                poster_url = ""
                img = item.select_one('img')
                if img and img.get('src'):
                    src = img['src']
                    if src.startswith('..'):
                         poster_url = f"https://kino.lubawa.pl/{src.replace('../', '')}"
                    elif src.startswith('/'):
                         poster_url = f"https://kino.lubawa.pl{src}"
                    else:
                         poster_url = f"https://kino.lubawa.pl/{src}"

                movies.append(Movie(
                    title=title,
                    genre="Kino",
                    time=times,
                    posterUrl=poster_url,
                    rating=info_text[:30] + "..." if len(info_text) > 30 else info_text,
                    link=url
                ))

            return CinemaRepertoire(
                cinemaName="Kino Pokój Lubawa",
                date=datetime.now().strftime('%d.%m.%Y'),
                movies=movies
            )

        except Exception as e:
            logger.error(f"Error fetching Kino Lubawa: {e}")
            return CinemaRepertoire(cinemaName="Kino Lubawa (Błąd)", date="", movies=[])

    # -------------------------------------------------------------------------
    # Cache
    # -------------------------------------------------------------------------

    def _get_cache_path(self, city_slug: str) -> str:
        return os.path.join(self.CACHE_DIR, f"cinema_{city_slug.lower()}.json")

    def _load_cache(self, city_slug: str) -> Optional[CinemaRepertoire]:
        try:
            cache_path = self._get_cache_path(city_slug)
            if not os.path.exists(cache_path):
                return None
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            today = datetime.now().strftime('%d.%m.%Y')
            if data.get('date') != today:
                return None
            return CinemaRepertoire(**data)
        except Exception as e:
            logger.warning(f"Błąd cache dla {city_slug}: {e}")
            return None

    def _save_cache(self, city_slug: str, data: CinemaRepertoire):
        try:
            cache_path = self._get_cache_path(city_slug)
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(data.json())
        except Exception as e:
            logger.error(f"Błąd zapisu cache dla {city_slug}: {e}")

    def _normalize_city(self, city: str) -> str:
        mapping = {
            'Działdowo': 'Dzialdowo',
            'Lubawa': 'Lubawa'
        }
        return mapping.get(city, city)
