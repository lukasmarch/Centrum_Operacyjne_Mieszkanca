from datetime import datetime
import re
from typing import List, Dict
from bs4 import BeautifulSoup
from datetime import datetime
import re

from src.scrapers.base import BaseScraper

class MojeDzialdowoScraper(BaseScraper):
    """Scraper dla mojedzialdowo.pl - portal informacyjny Działdowa"""

    async def parse(self, html: str, url: str) -> List[Dict]:
        """
        Parse HTML z mojedzialdowo.pl do artykułów.
        """
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        # Nowa struktura: ul.news-list > li > a
        news_lists = soup.find_all('ul', class_='news-list')
        
        seen_urls = set()

        for news_list in news_lists:
            for link in news_list.find_all('a'):
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

                    article_data = {
                        'title': title,
                        'url': full_url,
                        'external_id': external_id,
                    }

                    # Deep Scraping
                    try:
                        self.logger.info(f"Fetching details for: {full_url}")
                        detail_html = await self.fetch(full_url)
                        detail_data = self._parse_detail(detail_html)
                        article_data.update(detail_data)
                    except Exception as e:
                        self.logger.error(f"Error fetching details for {full_url}: {e}")

                    articles.append(article_data)

                except Exception as e:
                    self.logger.warning(f"Error parsing link: {e}")
                    continue

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

        # Image - extract main article image from detail page
        content_div = soup.find('div', itemprop='articleBody') or soup.find('div', class_=re.compile(r'article|content|tresc'))
        if content_div:
            img = content_div.find('img')
            if not img:
                img = soup.find('img', class_=re.compile(r'responsive|article|main|featured'))
            if img:
                img_src = img.get('src') or img.get('data-src')
                if img_src and not any(skip in img_src for skip in ['logo', 'icon', 'sprite', 'reklama']):
                    if img_src.startswith('http'):
                        data['image_url'] = img_src
                    elif img_src.startswith('/'):
                        data['image_url'] = f"https://mojedzialdowo.pl{img_src}"
                    else:
                        data['image_url'] = f"https://mojedzialdowo.pl/{img_src}"

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
