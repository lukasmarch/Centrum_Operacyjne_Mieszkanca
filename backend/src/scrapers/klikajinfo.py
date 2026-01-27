from typing import List, Dict
from bs4 import BeautifulSoup
from datetime import datetime
import re
import asyncio

from src.scrapers.base import BaseScraper

class KlikajInfoScraper(BaseScraper):
    """Scraper dla klikajinfo.pl - lokalne media"""

    async def parse(self, html: str, url: str) -> List[Dict]:
        """Parse HTML do artykułów"""
        soup = BeautifulSoup(html, 'html.parser')

        # Znajdź wszystkie linki do artykułów
        # Szukamy linków typu /artykul/[id],[slug]
        article_links = soup.find_all('a', href=re.compile(r'/artykul/\d+,'))

        seen_urls = set()
        max_articles = 50  # Limit to prevent excessive deep scraping
        basic_articles = []  # Collect basic data first

        # Phase 1: Collect basic article data (fast)
        for link in article_links:
            # Stop if we've reached the limit
            if len(seen_urls) >= max_articles:
                self.logger.info(f"Reached limit of {max_articles} articles, stopping")
                break
            try:
                href = link.get('href')
                if not href:
                    continue

                # Normalizacja URL (dodanie https://www.klikajinfo.pl jeśli trzeba)
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = f"https://www.klikajinfo.pl{href}"

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Tytuł
                title = link.get('title')
                if not title:
                    title_elem = link.find(['h1', 'h2', 'h3', 'h4'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)

                if not title:
                    # Fallback
                    title = link.get_text(strip=True)

                if not title or len(title) < 5:
                    continue

                # Obrazek
                image_url = None
                img = link.find('img')
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        if src.startswith('http'):
                            image_url = src
                        else:
                            image_url = f"https://static2.klikajinfo.pl{src}"

                # External ID
                external_id_match = re.search(r'/artykul/(\d+),', href)
                external_id = external_id_match.group(1) if external_id_match else None
                if not external_id:
                     external_id = f"klikajinfo_{hash(full_url) & 0x7FFFFFFF}"

                basic_articles.append({
                    'title': title,
                    'url': full_url,
                    'image_url': image_url,
                    'external_id': external_id,
                })

            except Exception as e:
                self.logger.warning(f"Parse error dla linku: {e}")
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

        self.logger.info(f"Znaleziono {len(articles)} artykułów")
        return articles

    def _parse_detail(self, html: str) -> Dict:
        soup = BeautifulSoup(html, 'html.parser')
        data = {}

        # Content - usually in .article-single or similar
        # Based on CSS: .article-single .text-title implies existence of .article-single
        content_div = soup.find('div', class_='article-single') or soup.find('div', class_='article-content')
        
        if content_div:
            # Remove junk
            for tag in content_div(['script', 'style', 'div.ads', 'div.social-share']):
                tag.decompose()
            
            text = content_div.get_text(separator='\n', strip=True)
            if text:
                data['content'] = text
        
        # Date
        # CSS mentions: .article-footer .article-date {display:none !important;} 
        # This implies it exists in HTML but is hidden. Perfect for scraping!
        date_elem = soup.find(class_='article-date')
        if not date_elem:
            # Try searching meta tags
            meta_date = soup.find('meta', {'property': 'article:published_time'})
            if meta_date:
                # ISO format likely
                try:
                    data['published_at'] = datetime.fromisoformat(meta_date['content'].replace('Z', '+00:00'))
                    return data # Done
                except:
                    pass

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            # Try parsing polish date formats e.g. "12 stycznia 2026" or "2026-01-12"
            # For simplicity, look for patterns
            import locale
            # locale is tricky in containers, stick to regex/simple mapping
            
            # Map polish months
            months = {
                'stycznia': '01', 'lutego': '02', 'marca': '03', 'kwietnia': '04',
                'maja': '05', 'czerwca': '06', 'lipca': '07', 'sierpnia': '08',
                'września': '09', 'października': '10', 'listopada': '11', 'grudnia': '12'
            }
            
            lower_text = date_text.lower()
            for pol, num in months.items():
                lower_text = lower_text.replace(pol, num)
            
            # Look for DD.MM.YYYY or DD MM YYYY
            match = re.search(r'(\d{1,2})[\s\.]+(\d{2})[\s\.]+(\d{4})', lower_text)
            if match:
                day, month, year = match.groups()
                data['published_at'] = datetime(int(year), int(month), int(day))

        return data
