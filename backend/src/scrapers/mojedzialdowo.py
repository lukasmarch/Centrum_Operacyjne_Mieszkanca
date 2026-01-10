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

        Struktura strony:
        - Artykuły w listach aktualności (główna strona)
        - Tytuł: <h2>, <h3> lub <a> z klasą title
        - Obrazek: <img> wewnątrz article/div
        - URL: względny link typu /artykul/[id]/[slug] lub /wiadomosci/[slug]
        - Content: może być dostępny snippet w <p class="excerpt">
        """
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        # Strategia 1: Szukamy article tags (HTML5 semantic)
        article_containers = soup.find_all('article')

        # Strategia 2: Divs z klasami zawierającymi 'article', 'post', 'news'
        if not article_containers:
            article_containers = soup.find_all('div', class_=re.compile(r'article|post|news|item'))

        # Strategia 3: Linki do artykułów w main/content div
        if not article_containers:
            main_content = soup.find(['main', 'div'], class_=re.compile(r'content|main|posts'))
            if main_content:
                article_links = main_content.find_all('a', href=re.compile(r'/artykul|/wiadomosc|/news'))
                article_containers = [link.parent for link in article_links if link.parent]

        seen_urls = set()

        for container in article_containers:
            try:
                # Znajdź link do artykułu
                link = container.find('a', href=re.compile(r'/artykul|/wiadomosc|/news|/\d+/'))
                if not link:
                    # Fallback: dowolny link wewnątrz kontenera
                    link = container.find('a', href=True)
                    if not link:
                        continue

                href = link.get('href')
                if not href or href in seen_urls:
                    continue

                # Ignoruj linki do kategorii, tagów, komentarzy, social media
                if any(x in href.lower() for x in ['/kategoria/', '/tag/', '/komentarz', '/autor/', '#',
                                                     'facebook.', 'twitter.', 'instagram.',
                                                     'javascript:', 'mailto:', 'share.php']):
                    continue

                # Tylko linki z własnej domeny
                if href.startswith('http') and 'mojedzialdowo.pl' not in href.lower():
                    continue

                # Buduj pełny URL
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = f"https://mojedzialdowo.pl{href}"
                else:
                    full_url = f"https://mojedzialdowo.pl/{href}"

                # Deduplikacja
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Tytuł - próbuj różne warianty
                title = None

                # 1. Z atrybutu title/alt linku
                title = link.get('title') or link.get('alt')

                # 2. Z nagłówka wewnątrz linku lub kontenera
                if not title:
                    title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'h5'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)

                # 3. Z klasy entry-title lub post-title
                if not title:
                    title_elem = container.find(class_=re.compile(r'title|headline'))
                    if title_elem:
                        title = title_elem.get_text(strip=True)

                # 4. Z tekstu linku (fallback)
                if not title:
                    title = link.get_text(strip=True)

                if not title or len(title) < 5:
                    self.logger.warning(f"Tytuł za krótki lub brak dla URL: {full_url}")
                    continue

                # Obrazek
                image_url = None
                img = container.find('img')
                if img:
                    img_src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if img_src:
                        if img_src.startswith('http'):
                            image_url = img_src
                        elif img_src.startswith('/'):
                            image_url = f"https://mojedzialdowo.pl{img_src}"
                        else:
                            image_url = f"https://mojedzialdowo.pl/{img_src}"

                # Content/excerpt - jeśli dostępny na stronie listy
                content = None
                excerpt_elem = container.find(['p', 'div'], class_=re.compile(r'excerpt|summary|description|content'))
                if excerpt_elem:
                    content = excerpt_elem.get_text(strip=True)
                    # Ogranicz długość excerpta
                    if content and len(content) > 500:
                        content = content[:500] + "..."

                # External ID z URL
                external_id = None

                # Wariant 1: /artykul/[ID]/slug
                id_match = re.search(r'/artykul/(\d+)/', href)
                if id_match:
                    external_id = id_match.group(1)
                else:
                    # Wariant 2: /wiadomosc/[ID]-slug lub /-[ID]-/
                    id_match = re.search(r'/(?:wiadomosc|news)?/?(\d+)[-/]', href)
                    if id_match:
                        external_id = id_match.group(1)
                    else:
                        # Wariant 3: ?p=[ID] (WordPress style)
                        id_match = re.search(r'[?&]p=(\d+)', href)
                        if id_match:
                            external_id = id_match.group(1)

                # Jeśli nadal brak external_id, użyj hash URL
                if not external_id:
                    external_id = f"mojedzialdowo_{hash(full_url) & 0x7FFFFFFF}"

                article_data = {
                    'title': title,
                    'url': full_url,
                    'image_url': image_url,
                    'external_id': external_id,
                }

                # Dodaj content tylko jeśli nie jest pusty
                if content:
                    article_data['content'] = content

                articles.append(article_data)
                self.logger.debug(f"Znaleziono artykuł: {title[:50]}...")

            except (AttributeError, KeyError, TypeError) as e:
                self.logger.warning(f"Parse error dla kontenera: {e}")
                continue

        self.logger.info(f"Znaleziono {len(articles)} artykułów na mojedzialdowo.pl")
        return articles
