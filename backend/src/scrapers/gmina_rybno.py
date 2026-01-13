from typing import List, Dict
from bs4 import BeautifulSoup
from datetime import datetime
import re

from src.scrapers.base import BaseScraper

class GminaRybnoScraper(BaseScraper):
    """Scraper dla gminarybno.pl - oficjalny portal Gminy Rybno"""

    async def parse(self, html: str, url: str) -> List[Dict]:
        """
        Parse HTML z gminarybno.pl do artykułów.

        Struktura strony:
        - Artykuły w <div class="aktualnosci-lista"> lub podobnych kontenerach
        - Tytuł: <h2> lub <h3> w linku <a>
        - Obrazek: <img> wewnątrz kontenera artykułu
        - URL: względny link typu /aktualnosc/[id]/[slug]
        """
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        # Szukamy kontenerów z artykułami
        # Struktura może być: div.aktualnosc-item, article, lub bezpośrednie linki
        article_containers = soup.find_all(['article', 'div'], class_=re.compile(r'aktualn|news|post'))

        # Jeśli nie ma kontenerów, szukamy bezpośrednio linków do aktualności
        if not article_containers:
            article_links = soup.find_all('a', href=re.compile(r'/aktualnosc|/news|/wiadomosc'))
            article_containers = [link.parent for link in article_links if link.parent]

        seen_urls = set()

        for container in article_containers:
            try:
                # Znajdź link do artykułu
                link = container.find('a', href=re.compile(r'/aktualnosc|/news|/wiadomosc'))
                if not link:
                    # Spróbuj znaleźć dowolny link
                    link = container.find('a', href=True)
                    if not link:
                        continue

                href = link.get('href')
                if not href or href in seen_urls:
                    continue

                # Ignoruj linki do social media, js, anchors, external
                if any(x in href.lower() for x in ['facebook.', 'twitter.', 'instagram.',
                                                     'javascript:', '#', 'mailto:', 'nasza-klasa.',
                                                     'wykop.', 'share.php', 'shout=']):
                    continue

                # Tylko linki z własnej domeny
                if href.startswith('http') and 'gminarybno.pl' not in href.lower():
                    continue

                # Buduj pełny URL
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = f"https://gminarybno.pl{href}"
                else:
                    full_url = f"https://gminarybno.pl/{href}"

                # Deduplikacja
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Tytuł - próbuj różne warianty
                title = None

                # 1. Z atrybutu title linku
                title = link.get('title')

                # 2. Z nagłówka wewnątrz linku
                if not title:
                    title_elem = link.find(['h1', 'h2', 'h3', 'h4'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)

                # 3. Z nagłówka w kontenerze
                if not title:
                    title_elem = container.find(['h1', 'h2', 'h3', 'h4'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)

                # 4. Z tekstu linku
                if not title:
                    title = link.get_text(strip=True)

                # Ignoruj linki generyczne (nawigacja)
                if title and title.lower() in ['aktualności', 'aktualnosci', 'strona główna', 'home',
                                                 'dodaj do facebooka', 'udostępnij', 'share']:
                    continue

                if not title or len(title) < 5:
                    self.logger.warning(f"Brak tytułu dla URL: {full_url}")
                    continue

                # Obrazek
                image_url = None
                img = container.find('img')
                if img:
                    img_src = img.get('src') or img.get('data-src')
                    if img_src:
                        if img_src.startswith('http'):
                            image_url = img_src
                        elif img_src.startswith('/'):
                            image_url = f"https://gminarybno.pl{img_src}"
                        else:
                            image_url = f"https://gminarybno.pl/{img_src}"

                # External ID z URL - próbuj wyciągnąć ID
                # Format: /aktualnosc/[ID]/slug lub /aktualnosc-[ID]-slug
                external_id = None

                # Wariant 1: /aktualnosc/[ID]/slug
                id_match = re.search(r'/aktualnosc(?:sc)?/(\d+)/', href)
                if id_match:
                    external_id = id_match.group(1)
                else:
                    # Wariant 2: /aktualnosc-[ID]-slug
                    id_match = re.search(r'/aktualnosc(?:sc)?-(\d+)[-/]', href)
                    if id_match:
                        external_id = id_match.group(1)
                    else:
                        # Wariant 3: dowolne ID w URL
                        id_match = re.search(r'/(\d+)/', href)
                        if id_match:
                            external_id = id_match.group(1)

                # Jeśli nadal brak external_id, użyj hash URL
                if not external_id:
                    external_id = f"gminarybno_{hash(full_url) & 0x7FFFFFFF}"

                article_data = {
                    'title': title,
                    'url': full_url,
                    'image_url': image_url,
                    'external_id': external_id,
                }
                
                # Deep Scraping: Fetch detail page to get content and date
                try:
                    self.logger.info(f"Fetching details for: {full_url}")
                    detail_html = await self.fetch(full_url)
                    detail_data = self._parse_detail(detail_html)
                    article_data.update(detail_data)
                except Exception as e:
                    self.logger.error(f"Error fetching details for {full_url}: {e}")

                articles.append(article_data)
                self.logger.debug(f"Znaleziono artykuł: {title[:50]}...")

            except (AttributeError, KeyError, TypeError) as e:
                self.logger.warning(f"Parse error dla kontenera: {e}")
                continue

        self.logger.info(f"Znaleziono {len(articles)} artykułów na gminarybno.pl")
        return articles

    def _parse_detail(self, html: str) -> Dict:
        """Parse detail page for content and date"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {}

        # Content - usually in #main or .entry-content
        content_div = soup.find('div', id='main') or soup.find('div', class_='entry-content')
        if content_div:
            # Remove scripts, styles, ads
            for tag in content_div(['script', 'style', 'div.ads', 'div.social-links', 'div.box-footer']):
                tag.decompose()
            
            text = content_div.get_text(separator='\n', strip=True)
            if text:
                data['content'] = text

        # Date - try to find patterns
        # 1. Look for specific date structures
        date_elem = soup.find('span', class_='date') or soup.find('div', class_='date')
        if date_elem:
            date_str = date_elem.get_text(strip=True)
            # Try parsing known formats
            try:
                # Example: 2024-05-12 or 12.05.2024
                for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
                    try:
                        data['published_at'] = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
        
        # Fallback date search in text
        if 'published_at' not in data:
            # Search for YYYY-MM-DD or DD.MM.YYYY
            text_content = soup.get_text()
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})|(\d{2}\.\d{2}\.\d{4})', text_content)
            if date_match:
                date_str = date_match.group(0)
                try:
                    # Try parsing known formats
                    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
                        try:
                            data['published_at'] = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

        return data
