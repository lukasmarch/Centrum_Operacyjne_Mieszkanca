import logging
import re
import json
import os
import asyncio
import httpx
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
    BASE_URL = "https://biletyna.pl"
    CACHE_DIR = "data/cache"

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        self.apify_api_key = os.environ.get('APIFY_API_KEY')
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def fetch_repertoire(self, city: str, force_update: bool = False) -> CinemaRepertoire:
        """Sync wrapper — używany tylko dla Lubawy."""
        city_slug = self._normalize_city(city)
        if not force_update:
            cached_data = self._load_cache(city_slug)
            if cached_data:
                return cached_data

        if city_slug == 'Lubawa':
            data = self._fetch_kino_lubawa_pl()
            if data and data.movies:
                self._save_cache(city_slug, data)
            return data

        # Działdowo — użyj async przez asyncio.run (tylko gdy NIE ma running event loop)
        try:
            loop = asyncio.get_running_loop()
            # Jeśli jest running loop, zwróć pusty (cinema_job.py powinien używać fetch_repertoire_async)
            logger.warning("fetch_repertoire called in async context for Dzialdowo — use fetch_repertoire_async")
            return CinemaRepertoire(cinemaName="Kino Działdowo", date="", movies=[])
        except RuntimeError:
            data = asyncio.run(self._fetch_biletyna_via_apify(city_slug))
            if data and data.movies:
                self._save_cache(city_slug, data)
            return data or CinemaRepertoire(cinemaName="Kino Działdowo (Błąd)", date="", movies=[])

    async def fetch_repertoire_async(self, city: str, force_update: bool = False) -> CinemaRepertoire:
        """Async version — używany z cinema_job.py."""
        city_slug = self._normalize_city(city)
        if not force_update:
            cached_data = self._load_cache(city_slug)
            if cached_data:
                return cached_data

        if city_slug == 'Lubawa':
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._fetch_kino_lubawa_pl)
        else:
            data = await self._fetch_biletyna_via_apify(city_slug)

        if data and data.movies:
            self._save_cache(city_slug, data)
        return data or CinemaRepertoire(cinemaName=f"Kino {city_slug} (Błąd)", date="", movies=[])

    # -------------------------------------------------------------------------
    # Apify-based scraping for biletyna.pl (Cloudflare bypass via Playwright)
    # -------------------------------------------------------------------------

    async def _fetch_biletyna_via_apify(self, city_slug: str) -> Optional[CinemaRepertoire]:
        """
        Pobiera repertuar biletyna.pl przez Apify website-content-crawler
        z crawlerType=playwright:adaptive (omija Cloudflare JS challenge).

        Jeden run Apify crawluje stronę listingu + wszystkie podstrony filmów.
        """
        if not self.apify_api_key:
            logger.error("APIFY_API_KEY nie skonfigurowany — nie można pobrać biletyna.pl")
            return None

        listing_url = f"{self.BASE_URL}/film/{city_slug}"
        logger.info(f"Uruchamiam Apify dla biletyna.pl/{city_slug}")

        actor_input = {
            "startUrls": [{"url": listing_url}],
            "crawlerType": "playwright:adaptive",
            "maxCrawlDepth": 1,
            "includeUrlGlobs": [
                f"https://biletyna.pl/film/{city_slug}*",
                f"https://biletyna.pl/film/*/{city_slug}*",
            ],
            "maxCrawlPages": 25,
            "readableTextCharThreshold": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                # Uruchom actor
                run_resp = await client.post(
                    "https://api.apify.com/v2/acts/apify~website-content-crawler/runs",
                    json=actor_input,
                    params={"token": self.apify_api_key}
                )
                run_resp.raise_for_status()
                run_id = run_resp.json()['data']['id']
                logger.info(f"Apify run started: {run_id}")

                # Polling na zakończenie (max 10 minut)
                status = 'RUNNING'
                for i in range(120):
                    await asyncio.sleep(5)
                    status_resp = await client.get(
                        f"https://api.apify.com/v2/actor-runs/{run_id}",
                        params={"token": self.apify_api_key}
                    )
                    status = status_resp.json()['data']['status']
                    if i % 6 == 0:
                        logger.info(f"Apify status: {status} ({(i+1)*5}s)")
                    if status in ['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT']:
                        break

                if status != 'SUCCEEDED':
                    logger.error(f"Apify run nieudany: {status}")
                    return None

                # Pobierz wyniki (HTML wszystkich stron)
                dataset_resp = await client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items",
                    params={"token": self.apify_api_key, "limit": 50}
                )
                items = dataset_resp.json()

        except Exception as e:
            logger.error(f"Apify API error: {e}")
            return None

        if not items:
            logger.error("Apify nie zwrócił żadnych stron")
            return None

        logger.info(f"Apify zwrócił {len(items)} stron")

        # Zbuduj mapę URL → HTML
        html_map: Dict[str, str] = {}
        listing_html = None

        for item in items:
            url = item.get('url') or item.get('loadedUrl', '')
            html = item.get('html', '')
            if not html or not url:
                continue
            html_map[url] = html
            # Rozpoznaj stronę listingu: kończy się na /Dzialdowo lub /Dzialdowo/
            if re.search(rf'/film/{city_slug}/?$', url):
                listing_html = html
                logger.info(f"Strona listingu: {url}")

        if not listing_html:
            logger.error("Brak HTML strony listingu w wynikach Apify")
            return None

        # Parsuj listing → lista filmów i ich URLe
        soup = BeautifulSoup(listing_html, 'html.parser')
        movies = []
        today_date = datetime.now().strftime('%d.%m.%Y')

        movie_elems = soup.select('.event-left-side')
        logger.info(f"Znaleziono {len(movie_elems)} filmów na liście")

        for elem in movie_elems:
            try:
                title_elem = elem.select_one('h3 a')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get('href', '')
                if not href:
                    continue

                detail_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href

                # Dopasuj HTML podstrony
                detail_html = self._find_html_for_url(detail_url, href, html_map)
                if not detail_html:
                    logger.warning(f"Brak HTML dla: {title} ({detail_url})")
                    continue

                details = self._parse_movie_details_html(detail_html, today_date)

                if details and details['times']:
                    movies.append(Movie(
                        title=title,
                        genre=details.get('genre', 'Film'),
                        time=details['times'],
                        posterUrl=details.get('posterUrl', ''),
                        rating=details.get('rating', 'N/A'),
                        link=detail_url
                    ))

            except Exception as e:
                logger.warning(f"Błąd parsowania filmu: {e}")
                continue

        logger.info(f"Sparsowano {len(movies)} filmów z seansami")

        return CinemaRepertoire(
            cinemaName="Kino Działdowo",
            date=today_date,
            movies=movies
        )

    def _find_html_for_url(self, detail_url: str, href: str, html_map: Dict[str, str]) -> Optional[str]:
        """Znajdź HTML podstrony filmy w mapie wyników Apify."""
        # Dopasowanie dokładne
        if detail_url in html_map:
            return html_map[detail_url]
        if detail_url.rstrip('/') in html_map:
            return html_map[detail_url.rstrip('/')]
        # Dopasowanie przez suffix href
        for url, html in html_map.items():
            if href.rstrip('/') in url:
                return html
        return None

    def _parse_movie_details_html(self, html: str, target_date: str) -> Optional[Dict]:
        """
        Parsuj HTML podstrony filmy (biletyna.pl/film/TYTUL/MIASTO).
        Zwraca dict z: posterUrl, genre, times, rating.
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            poster_url = ""
            og_image = soup.find('meta', property='og:image')
            if og_image:
                poster_url = og_image.get('content', '')

            times = []

            from datetime import timedelta
            base = datetime.strptime(target_date, '%d.%m.%Y')
            next_7_days = {(base + timedelta(days=i)).strftime('%d.%m.%Y') for i in range(7)}
            valid_formats = next_7_days | {"Dzisiaj", "Dziś"}

            date_blocks = soup.select('.event-date')
            if not date_blocks:
                potential_spans = soup.select('.table-important-text')
                date_blocks = []
                for s in potential_spans:
                    if s.parent:
                        date_blocks.append(s.parent)
                    else:
                        date_blocks.append(s)

            for block in date_blocks:
                date_text = block.get_text(separator=' ', strip=True)
                if not any(fmt in date_text for fmt in valid_formats):
                    continue

                date_match = re.search(r'(\d{2}\.\d{2})\.\d{4}', date_text)
                date_label = date_match.group(1) if date_match else ""

                found_times = re.findall(r'godz\.\s*(\d{2}:\d{2})', date_text)
                if not found_times:
                    found_times = re.findall(r'(?<!\d)(\d{2}:\d{2})(?!\d)', date_text)

                for t in found_times:
                    label = f"{date_label} {t}".strip() if date_label else t
                    times.append(label)

            times = sorted(list(set(times)))

            return {
                'posterUrl': poster_url,
                'genre': 'Film',
                'times': times,
                'rating': 'N/A'
            }

        except Exception as e:
            logger.error(f"Błąd parsowania szczegółów filmu: {e}")
            return None

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

    def _normalize_city(self, city: str) -> str:
        mapping = {
            'Działdowo': 'Dzialdowo',
            'Lubawa': 'Lubawa'
        }
        return mapping.get(city, city)
