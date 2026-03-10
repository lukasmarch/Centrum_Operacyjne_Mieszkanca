from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from datetime import datetime
import re

from src.scrapers.base import BaseScraper


class GminaRybnoScraper(BaseScraper):
    """Scraper dla gminarybno.pl - oficjalny portal Gminy Rybno"""

    BASE_URL = "https://gminarybno.pl"

    def _build_url(self, href: str) -> str:
        if href.startswith('http'):
            return href
        return f"{self.BASE_URL}{href}" if href.startswith('/') else f"{self.BASE_URL}/{href}"

    def _parse_date(self, container) -> Optional[datetime]:
        """Pobiera datę z <p class="meta">Opublikowano YYYY-MM-DD HH:MM:SS.</p>"""
        meta = container.find('p', class_='meta')
        if not meta:
            return None
        m = re.search(r'(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}', meta.get_text(strip=True))
        if m:
            try:
                return datetime.strptime(m.group(1), '%Y-%m-%d')
            except ValueError:
                pass
        return None

    def _parse_external_id(self, href: str, full_url: str) -> str:
        # Format: /aktualnosci/slug,ID.html → wyciągnij ID po przecinku
        m = re.search(r',(\d+)\.html$', href)
        if m:
            return m.group(1)
        # Fallback: dowolny numer w URL
        m = re.search(r'/(\d+)/', href)
        if m:
            return m.group(1)
        return f"gminarybno_{hash(full_url) & 0x7FFFFFFF}"

    async def parse(self, html: str, url: str) -> List[Dict]:
        articles = []
        soup = BeautifulSoup(html, 'html.parser')
        seen_urls = set()

        containers = soup.find_all(['article', 'div'], class_=re.compile(r'aktualn|news|post'))
        if not containers:
            containers = [
                link.parent
                for link in soup.find_all('a', href=re.compile(r'/aktualnosc|/news|/wiadomosc'))
                if link.parent
            ]

        for container in containers:
            try:
                # Data musi być na listingu — brak = artykuł stały z sidebaru, pomijamy
                published_at = self._parse_date(container)
                if not published_at:
                    continue

                link = container.find('a', href=re.compile(r'/aktualnosc|/news|/wiadomosc')) \
                    or container.find('a', href=True)
                if not link:
                    continue

                href = link.get('href', '')
                if not href:
                    continue

                if any(x in href.lower() for x in ['facebook.', 'twitter.', 'instagram.',
                                                     'javascript:', '#', 'mailto:']):
                    continue

                if href.startswith('http') and self.BASE_URL not in href:
                    continue

                full_url = self._build_url(href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Tytuł
                title = (
                    link.get('title')
                    or (h := link.find(['h1', 'h2', 'h3', 'h4'])) and h.get_text(strip=True)
                    or (h := container.find(['h1', 'h2', 'h3', 'h4'])) and h.get_text(strip=True)
                    or link.get_text(strip=True)
                )
                if not title or len(title) < 5:
                    continue
                if title.lower() in ['aktualności', 'aktualnosci', 'strona główna', 'home']:
                    continue

                # Obrazek z listingu
                image_url = None
                img = container.find('img')
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        image_url = self._build_url(src)

                article_data = {
                    'title': title,
                    'url': full_url,
                    'image_url': image_url,
                    'external_id': self._parse_external_id(href, full_url),
                    'published_at': published_at,
                }

                # Deep scraping: content + lepszy obrazek ze strony detalu
                try:
                    self.logger.info(f"Fetching details for: {full_url}")
                    detail_html = await self.fetch(full_url)
                    article_data.update(self._parse_detail(detail_html))
                    # Data pochodzi z listingu — nie nadpisujemy
                    article_data['published_at'] = published_at
                except Exception as e:
                    self.logger.error(f"Error fetching details for {full_url}: {e}")

                articles.append(article_data)

            except Exception as e:
                self.logger.warning(f"Parse error: {e}")
                continue

        self.logger.info(f"Znaleziono {len(articles)} artykułów na gminarybno.pl")
        return articles

    def _parse_detail(self, html: str) -> Dict:
        """Pobiera content i główny obrazek ze strony detalu."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {}

        content_div = soup.find('div', id='main') or soup.find('div', class_='entry-content')
        if content_div:
            for tag in content_div(['script', 'style']):
                tag.decompose()
            text = content_div.get_text(separator='\n', strip=True)
            if text:
                data['content'] = text

            img = content_div.find('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src and not any(x in src for x in ['logo', 'icon', 'sprite', 'button']):
                    data['image_url'] = self._build_url(src)

        return data
