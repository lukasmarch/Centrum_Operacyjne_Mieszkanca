"""
RSS Feed Scraper - Uniwersalny scraper dla kanałów RSS

Obsługuje standardowe formaty RSS 2.0 i Atom.
"""
import feedparser
from datetime import datetime
from typing import List, Dict, Optional
from src.scrapers.base import BaseScraper
from src.database.schema import Source
from src.utils.logger import setup_logger

logger = setup_logger("RSSFeedScraper")


class RSSFeedScraper(BaseScraper):
    """
    Uniwersalny scraper dla kanałów RSS/Atom.

    Używa biblioteki feedparser do parsowania standardowych formatów RSS.
    Automatycznie ekstrahuje: tytuł, link, opis, autora, datę publikacji, obrazy.
    """

    def __init__(self, source_id: int, config: Optional[Dict] = None):
        super().__init__(source_id, config)
        self.logger = logger

    async def parse(self, html: str, url: str) -> List[Dict]:
        """
        Not used for RSS scraping (we use feedparser directly).
        Implemented to satisfy ABC requirement.
        """
        raise NotImplementedError("RSS scraper uses feedparser, not HTML parsing")

    async def scrape_feed(self, url: str) -> List[Dict]:
        """
        Scrape artykułów z kanału RSS

        Args:
            url: URL kanału RSS

        Returns:
            Lista słowników z artykułami
        """
        self.logger.info(f"Scraping RSS feed: {url}")

        try:
            # Pobierz i sparsuj feed
            feed = await self._fetch_feed(url)

            if not feed:
                self.logger.error("Failed to fetch RSS feed")
                return []

            # feedparser jest tolerancyjny - sprawdź czy są entries mimo błędów
            if feed.bozo:
                error = getattr(feed, 'bozo_exception', 'Unknown error')
                self.logger.warning(f"RSS feed has parsing errors (but may still work): {error}")

            # Sprawdź czy są jakieś wpisy
            if not feed.entries:
                self.logger.error("No entries found in RSS feed")
                return []

            self.logger.info(f"Feed title: {feed.feed.get('title', 'Unknown')}")
            self.logger.info(f"Found {len(feed.entries)} entries")

            # Parsuj wpisy
            articles = []
            for entry in feed.entries:
                article = self._parse_entry(entry)
                if article:
                    articles.append(article)

            self.logger.info(f"Successfully parsed {len(articles)} articles")
            return articles

        except Exception as e:
            self.logger.error(f"RSS scraping failed: {e}")
            return []

    async def _fetch_feed(self, url: str) -> feedparser.FeedParserDict:
        """
        Pobierz i sparsuj RSS feed

        Args:
            url: URL kanału RSS

        Returns:
            Sparsowany feed
        """
        import asyncio
        import httpx

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }

        # Pobierz raw content przez httpx - feedparser.parse(url) ma problemy
        # z niektórymi feedami (encoding, chunked transfer, invalid tokens)
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                raw_content = response.content
        except Exception as e:
            self.logger.error(f"Failed to fetch RSS feed via httpx: {e}")
            raw_content = None

        if not raw_content:
            return feedparser.FeedParserDict()

        # Parsuj raw content (nie URL) - unika problemów z parsowaniem on-the-fly
        def parse_raw():
            return feedparser.parse(raw_content)

        try:
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, parse_raw)
            return feed
        except Exception as e:
            self.logger.error(f"Failed to parse RSS feed: {e}")
            return feedparser.FeedParserDict()

    def _parse_entry(self, entry: feedparser.FeedParserDict) -> Optional[Dict]:
        """
        Parsuj pojedynczy wpis RSS do formatu Article

        Args:
            entry: Wpis z feedparser

        Returns:
            Słownik z danymi artykułu lub None
        """
        try:
            # Wymagane pola
            title = entry.get('title', '').strip()
            link = entry.get('link', '').strip()

            if not title or not link:
                self.logger.warning("Entry missing title or link, skipping")
                return None

            # Opcjonalne pola
            summary = self._extract_summary(entry)
            author = entry.get('author', None)
            published_at = self._parse_date(entry)
            image_url = self._extract_image(entry)

            # External ID z link (używamy URL jako unique identifier)
            external_id = self._generate_external_id(link)

            article = {
                'title': title,
                'url': link,
                'summary': summary,
                'author': author,
                'published_at': published_at,
                'image_url': image_url,
                'external_id': external_id,
                'content': entry.get('content', [{}])[0].get('value', None) if entry.get('content') else None
            }

            return article

        except Exception as e:
            self.logger.error(f"Failed to parse entry: {e}")
            return None

    def _extract_summary(self, entry: feedparser.FeedParserDict) -> Optional[str]:
        """Ekstrahuj opis/streszczenie artykułu"""
        # RSS 2.0 używa 'summary' lub 'description'
        # Atom używa 'summary'
        summary = entry.get('summary', entry.get('description', '')).strip()

        if not summary and entry.get('content'):
            # Jeśli nie ma summary, weź fragment content
            summary = entry.content[0].get('value', '')[:500]

        # Usuń HTML tags (feedparser czasem zostawia)
        if summary:
            import re
            summary = re.sub(r'<[^>]+>', '', summary).strip()
            # Ogranicz długość
            if len(summary) > 1000:
                summary = summary[:997] + '...'

        return summary if summary else None

    def _parse_date(self, entry: feedparser.FeedParserDict) -> Optional[datetime]:
        """
        Parsuj datę publikacji

        Próbuje różnych pól w kolejności:
        - published_parsed (RSS 2.0)
        - updated_parsed (Atom)
        - created_parsed
        """
        # feedparser zwraca już sparsowane daty w time.struct_time
        date_tuple = (
            entry.get('published_parsed') or
            entry.get('updated_parsed') or
            entry.get('created_parsed')
        )

        if date_tuple:
            try:
                # Konwertuj time.struct_time na datetime
                import time
                timestamp = time.mktime(date_tuple)
                return datetime.fromtimestamp(timestamp)
            except Exception as e:
                self.logger.warning(f"Failed to parse date: {e}")

        return None

    def _extract_image(self, entry: feedparser.FeedParserDict) -> Optional[str]:
        """
        Ekstrahuj URL obrazka z wpisu

        Sprawdza:
        - media:thumbnail
        - media:content
        - enclosure (type="image/*")
        - <img> w content
        """
        # 1. Media thumbnail (najpopularniejsze)
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url')

        # 2. Media content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('medium') == 'image' or 'image' in media.get('type', ''):
                    return media.get('url')

        # 3. Enclosures (RSS)
        if entry.get('enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    return enclosure.get('href')

        # 4. Szukaj <img> w content/summary
        content = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
        if content:
            import re
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
            if img_match:
                return img_match.group(1)

        return None

    def _generate_external_id(self, url: str) -> str:
        """
        Generuj unique ID z URL

        Używamy hash URL jako external_id dla deduplikacji
        """
        import hashlib
        return f"rss_{hashlib.md5(url.encode()).hexdigest()}"
