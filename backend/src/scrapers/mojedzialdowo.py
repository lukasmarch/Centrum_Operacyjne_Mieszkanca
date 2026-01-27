from datetime import datetime
import re
from typing import List, Dict
from bs4 import BeautifulSoup
import asyncio

from src.scrapers.base import BaseScraper

class MojeDzialdowoScraper(BaseScraper):
    """Scraper dla mojedzialdowo.pl - portal informacyjny Działdowa"""

    async def parse(self, html: str, url: str) -> List[Dict]:
        """
        Parse HTML z mojedzialdowo.pl do artykułów.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Nowa struktura: ul.news-list > li > a
        news_lists = soup.find_all('ul', class_='news-list')

        seen_urls = set()
        max_articles = 50  # Limit to prevent excessive deep scraping
        basic_articles = []  # Collect basic data first

        # Phase 1: Collect basic article data (fast)
        for news_list in news_lists:
            for link in news_list.find_all('a'):
                # Stop if we've reached the limit
                if len(seen_urls) >= max_articles:
                    self.logger.info(f"Reached limit of {max_articles} articles, stopping")
                    break

                try:
                    href = link.get('href')
                    if not href or href in seen_urls:
                        continue

                    # Filtrowanie linków
                    if any(x in href.lower() for x in ['facebook.', 'twitter.', 'javascript:', 'mailto:']):
                        continue

                    # Buduj pełny URL
                    if href.startswith('http'):
                        full_url = href
                    elif href.startswith('/'):
                        full_url = f"https://mojedzialdowo.pl{href}"
                    else:
                        full_url = f"https://mojedzialdowo.pl/{href}"

                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    # Tytuł
                    title = link.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    # External ID
                    external_id = None
                    id_match = re.search(r'-(\d+)$', href)
                    if id_match:
                        external_id = id_match.group(1)
                    else:
                        external_id = f"mojedzialdowo_{hash(full_url) & 0x7FFFFFFF}"

                    basic_articles.append({
                        'title': title,
                        'url': full_url,
                        'external_id': external_id,
                    })

                except Exception as e:
                    self.logger.warning(f"Error parsing link: {e}")
                    continue

        # Phase 2: Fetch details in parallel (fast with asyncio.gather)
        self.logger.info(f"Fetching details for {len(basic_articles)} articles in parallel...")

        async def fetch_article_details(article_data):
            """Helper function to fetch and parse article details"""
            try:
                self.logger.info(f"Fetching details for: {article_data['url']}")
                detail_html = await self.fetch(article_data['url'])
                detail_data = self._parse_detail(detail_html)
                article_data.update(detail_data)
                return article_data
            except Exception as e:
                self.logger.error(f"Error fetching details for {article_data['url']}: {e}")
                return article_data  # Return basic data even if detail fetch fails

        # Use asyncio.gather to fetch all details in parallel
        articles = await asyncio.gather(*[fetch_article_details(article) for article in basic_articles])

        self.logger.info(f"Znaleziono {len(articles)} artykułów na mojedzialdowo.pl")
        return articles

    def _parse_detail(self, html: str) -> Dict:
        """Parse detail page"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {}

        # Content
        content_div = soup.find('div', itemprop='articleBody')
        if content_div:
            text = content_div.get_text(separator='\n', strip=True)
            if text:
                data['content'] = text

        # Image (try to find main image in detail if not in list)
        if 'image_url' not in data:
            # Look for video container or main image
            img = soup.find('img', class_='responsive-image') # Generic fallback
            # Better specific check?
            pass

        # Date
        # Format: <div class="c-light-grey text-2"> 04.01.2026 </div>
        date_div = soup.find('div', class_='text-2')
        if date_div:
            date_text = date_div.get_text(strip=True)
            # Match DD.MM.YYYY
            match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_text)
            if match:
                day, month, year = match.groups()
                data['published_at'] = datetime(int(year), int(month), int(day))

        return data
