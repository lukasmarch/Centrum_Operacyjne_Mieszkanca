from typing import List, Dict
from bs4 import BeautifulSoup
from datetime import datetime
import re

from src.scrapers.base import BaseScraper

class KlikajInfoScraper(BaseScraper):
    """Scraper dla klikajinfo.pl - lokalne media"""

    async def parse(self, html: str, url: str) -> List[Dict]:
        """Parse HTML do artykułów"""
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        # Znajdź wszystkie linki do artykułów
        article_links = soup.find_all('a', href=re.compile(r'^/artykul/\d+,'))

        seen_urls = set()

        for link in article_links:
            try:
                href = link.get('href')
                if not href or href in seen_urls:
                    continue

                seen_urls.add(href)
                full_url = f"https://klikajinfo.pl{href}"

                # Tytuł z atrybutu title lub z h3
                title = link.get('title')
                if not title:
                    title_elem = link.find(['h1', 'h2', 'h3'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)

                if not title:
                    continue

                # Obrazek
                img = link.find('img')
                image_url = None
                if img:
                    image_url = img.get('src')
                    if image_url and not image_url.startswith('http'):
                        image_url = f"https://static2.klikajinfo.pl{image_url}"

                # External ID z URL
                external_id_match = re.search(r'/artykul/(\d+),', href)
                external_id = external_id_match.group(1) if external_id_match else None

                article_data = {
                    'title': title,
                    'url': full_url,
                    'image_url': image_url,
                    'external_id': external_id,
                }

                articles.append(article_data)

            except (AttributeError, KeyError) as e:
                self.logger.warning(f"Parse error dla linku: {e}")
                continue

        self.logger.info(f"Znaleziono {len(articles)} artykułów")
        return articles
