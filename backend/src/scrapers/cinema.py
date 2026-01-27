import logging
import re
import json
import os
from datetime import datetime
from typing import List, Optional, Dict
import httpx
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
        # Ensure cache directory exists
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    async def fetch_repertoire(self, city: str, force_update: bool = False) -> CinemaRepertoire:
        """
        Fetches cinema repertoire for a specific city.
        Dzialdowo -> Biletyna.pl
        Lubawa -> Kino.lubawa.pl

        Args:
            city: City name
            force_update: If True, bypass cache and fetch fresh data
        """
        city_slug = self._normalize_city(city)
        logger.info(f"Fetching repertoire for {city_slug} (force_update={force_update})...")

        # Try cache first
        if not force_update:
            cached_data = self._load_cache(city_slug)
            if cached_data:
                logger.info(f"Using cached data for {city_slug}")
                return cached_data

        # Fetch fresh data
        if city_slug == 'Lubawa':
            data = await self._fetch_kino_lubawa_pl()
        else:
            data = await self._fetch_biletyna_dzialdowo(city_slug)

        # Save to cache if valid movies found or empty (so we don't hammer on error, but maybe better not to cache empty?)
        if data and data.movies:
            self._save_cache(city_slug, data)

        return data

    def _get_cache_path(self, city_slug: str) -> str:
        return os.path.join(self.CACHE_DIR, f"cinema_{city_slug.lower()}.json")

    def _load_cache(self, city_slug: str) -> Optional[CinemaRepertoire]:
        try:
            cache_path = self._get_cache_path(city_slug)
            if not os.path.exists(cache_path):
                return None
                
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Check if cache is from today
            today = datetime.now().strftime('%d.%m.%Y')
            if data.get('date') != today:
                return None
                
            return CinemaRepertoire(**data)
        except Exception as e:
            logger.warning(f"Failed to load cache for {city_slug}: {e}")
            return None

    def _save_cache(self, city_slug: str, data: CinemaRepertoire):
        try:
            cache_path = self._get_cache_path(city_slug)
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(data.json())
        except Exception as e:
            logger.error(f"Failed to save cache for {city_slug}: {e}")

    async def _fetch_biletyna_dzialdowo(self, city_slug: str) -> CinemaRepertoire:
        # Specific URL for Dzialdowo that works well
        url = f"{self.BASE_URL}/film/{city_slug}"
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                movies = await self._parse_biletyna_list(response.text, city_slug)

                return CinemaRepertoire(
                    cinemaName=f"Kino {city_slug}",
                    date=datetime.now().strftime('%d.%m.%Y'),
                    movies=movies
                )
        except Exception as e:
            logger.error(f"Error fetching Dzialdowo: {e}")
            return CinemaRepertoire(cinemaName=f"Kino {city_slug} (Błąd)", date="", movies=[])

    async def _fetch_kino_lubawa_pl(self) -> CinemaRepertoire:
        url = "https://kino.lubawa.pl/"
        try:
            # verify=False because of local cert issues often found on such sites
            async with httpx.AsyncClient(headers=self.headers, timeout=15.0, verify=False) as client:
                response = await client.get(url)
                # httpx automatically handles encoding, but we can force it if needed
                response.encoding = 'utf-8'

                soup = BeautifulSoup(response.text, 'html.parser')
                movies = []

                # Parsing strategy:
                # Container class "inweek" contains h4 (Title) and h5 (Date/Time info)

                items = soup.select('.inweek')
                logger.info(f"KinoLubawa: Found {len(items)} items")

                for item in items:
                    title_node = item.select_one('h4')
                    if not title_node: continue

                    title = title_node.get_text(strip=True)

                    info_node = item.select_one('h5')
                    info_text = info_node.get_text(separator=' ', strip=True) if info_node else ""

                    # Extract time pattern: HH:MM
                    times_found = re.findall(r'(\d{2}:\d{2})', info_text)
                    times = sorted(list(set(times_found)))

                    # Handling missing specific times or "Coming Soon"
                    if not times:
                        times = ["Sprawdź godziny"]

                    # Store extra info in rating or similar if needed,
                    # but currently UI only uses title, time, genre.
                    # info_text often has "od 16 stycznia", which is useful.

                    # Image/Poster
                    poster_url = ""
                    img = item.select_one('img')
                    if img and img.get('src'):
                        # relative path "../media/week/1.jpg"
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
                        # We can put small info in rating field as hacked info display if needed
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
        # Simple mapping or normalization
        mapping = {
            'Działdowo': 'Dzialdowo',
            'Lubawa': 'Lubawa'
        }
        return mapping.get(city, city)

    async def _parse_biletyna_list(self, html: str, city_slug: str) -> List[Movie]:
        # Copied from previous logic
        soup = BeautifulSoup(html, 'html.parser')
        movies = []
        today_date = datetime.now().strftime('%d.%m.%Y')

        items = soup.select('.event-left-side')
        if not items:
            link_elements = soup.select('h3 a')[:30]
            items = []
            for link in link_elements:
                items.append(link)

        for item in items:
            try:
                if hasattr(item, 'select_one'):
                    title_elem = item.select_one('h3 a')
                    if not title_elem and item.name == 'a':
                        title_elem = item
                else:
                    title_elem = item

                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get('href')

                full_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                if city_slug not in full_url and '/kino/' not in full_url:
                     full_url = f"{full_url}/{city_slug}"

                if any(m.title == title for m in movies):
                    continue

                details = await self._fetch_movie_details(full_url, today_date)

                if details and details['times']:
                    movies.append(Movie(
                        title=title,
                        genre=details.get('genre', 'Film'),
                        time=details['times'],
                        posterUrl=details.get('posterUrl', ''),
                        rating=details.get('rating', 'N/A'),
                        link=full_url
                    ))
            except Exception as e:
                logger.warning(f"Error parsing movie item: {e}")
                continue
        return movies

    def _fetch_movie_details(self, url: str, target_date: str) -> Optional[Dict]:
        try:
            logger.debug(f"Fetching details from {url}")
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code != 200:
                logger.warning(f"Status {response.status_code} for {url}")
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            poster_url = ""
            og_image = soup.find('meta', property='og:image')
            if og_image:
                poster_url = og_image.get('content')
            
            genre = "Film" 
            times = []
            
            today_formats = [ target_date, "Dzisiaj", "Dziś" ]
            
            date_blocks = soup.select('.event-date')
            if not date_blocks:
                 potential_spans = soup.select('.table-important-text')
                 date_blocks = []
                 for s in potential_spans:
                     if s.parent: date_blocks.append(s.parent)
                     else: date_blocks.append(s)

            logger.debug(f"Found {len(date_blocks)} potential date blocks")
            
            for block in date_blocks:
                date_text = block.get_text(separator=' ', strip=True)
                if any(fmt in date_text for fmt in today_formats):
                    found_times = re.findall(r'godz\.\s*(\d{2}:\d{2})', date_text)
                    if not found_times:
                        found_times = re.findall(r'(?<!\d)(\d{2}:\d{2})(?!\d)', date_text)
                    if found_times:
                        times.extend(found_times)
            
            times = sorted(list(set(times)))
            
            return {
                'posterUrl': poster_url,
                'genre': genre,
                'times': times,
                'rating': 'N/A'
            }
            
        except Exception as e:
            logger.error(f"Error fetching details for {url}: {e}")
            return None
