from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

from src.scrapers.base import BaseScraper


class GminaRybnoScraper(BaseScraper):
    """Scraper dla gminarybno.pl - oficjalny portal Gminy Rybno

    **Nowa strona od 22.10.2026.** Gmina przeniosła portal na nowy system:
    lista to `/aktualnosci/` (kafle `article.news-card`, data `p.news-meta`
    w formacie DD.MM.RRRR), wpis to `/artykul/{slug}` z treścią w
    `div.article-body`. Strona ma `<base href="/">`, więc adresy względne
    liczymy od korzenia. Stary układ (`aktualnosci.html`, `…,7605.html`)
    odpowiada 404.

    Na liście są też kafle z kalendarza gminy („Wydarzenie w kalendarzu”,
    bez daty publikacji) — pomijamy je: to zapowiedzi, nie wiadomości.

    **Szczegóły tylko z okna świeżości.** Job i tak odrzuca wpisy starsze niż
    `MAX_AGE_DAYS` (`filter_recent_articles`), a stary scraper pobierał przy
    każdym przebiegu stronę KAŻDEGO wpisu z listy — 13 żądań w ~5 s.
    """

    BASE_URL = "https://gminarybno.pl"
    LIST_URL = "https://gminarybno.pl/aktualnosci/"
    # Adres listy zapisany w `sources.url` sprzed przebudowy strony — scraper
    # sam go podmienia, żeby źródło nie wymagało ręcznej zmiany w bazie.
    LEGACY_LIST_URLS = {"https://gminarybno.pl/aktualnosci.html"}
    MAX_AGE_DAYS = 2

    _DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
    _BG_IMAGE_RE = re.compile(r"url\(['\"]?([^'\")]+)")

    async def fetch(self, url: str) -> str:
        if url in self.LEGACY_LIST_URLS:
            url = self.LIST_URL
        return await super().fetch(url)

    def _build_url(self, href: str) -> str:
        if href.startswith('http'):
            return href
        return f"{self.BASE_URL}/{href.lstrip('/')}"

    def _parse_date(self, text: str) -> Optional[datetime]:
        m = self._DATE_RE.search(text or '')
        if not m:
            return None
        day, month, year = (int(g) for g in m.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    @staticmethod
    def _external_id(href: str) -> str:
        # Slug kończy się identyfikatorem nadanym przez system („…-40”,
        # „…-b99614”). Prefiks, bo `external_id` jest unikalny w całej tabeli,
        # a stare wpisy tego źródła mają gołe liczby („7605”).
        slug = href.rstrip('/').rsplit('/', 1)[-1]
        return f"gminarybno:{slug}"[:255]

    def parse_listing(self, html: str) -> List[Dict]:
        """Wpisy z listy, bez sieci — testowalne na zapisanym HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        seen = set()

        for card in soup.select('article.news-card'):
            meta = card.find('p', class_='news-meta')
            published_at = self._parse_date(meta.get_text(strip=True)) if meta else None
            if not published_at:
                continue  # kafel z kalendarza gminy — to nie jest wiadomość

            link = card.select_one('h3 a[href], h2 a[href]')
            if not link or 'artykul/' not in link['href']:
                continue
            url = self._build_url(link['href'])
            if url in seen:
                continue
            seen.add(url)

            title = link.get_text(" ", strip=True)
            if len(title) < 3:
                continue

            image_url = None
            cover = card.find('a', class_='news-image')
            if cover and cover.get('style'):
                m = self._BG_IMAGE_RE.search(cover['style'])
                if m:
                    image_url = self._build_url(m.group(1))

            articles.append({
                'title': title,
                'url': url,
                'image_url': image_url,
                'external_id': self._external_id(link['href']),
                'published_at': published_at,
            })
        return articles

    async def parse(self, html: str, url: str) -> List[Dict]:
        articles = self.parse_listing(html)
        cutoff = datetime.utcnow() - timedelta(days=self.MAX_AGE_DAYS)
        fresh = [a for a in articles if a['published_at'] >= cutoff]

        for article in fresh:
            try:
                self.logger.info(f"Fetching details for: {article['url']}")
                detail_html = await self.fetch(article['url'])
                detail = self._parse_detail(detail_html)
                # Data pochodzi z listingu — nie nadpisujemy
                detail.pop('published_at', None)
                article.update(detail)
            except Exception as e:
                self.logger.error(f"Error fetching details for {article['url']}: {e}")

        self.logger.info(
            f"gminarybno.pl: {len(articles)} wpisów na liście, "
            f"{len(fresh)} w oknie {self.MAX_AGE_DAYS} dni (pobrane szczegóły)"
        )
        return fresh

    def _parse_detail(self, html: str) -> Dict:
        """Tytuł, treść i pierwsze zdjęcie ze strony wpisu."""
        soup = BeautifulSoup(html, 'html.parser')
        data: Dict = {}

        shell = soup.find('article', class_='article-layout') or soup
        h1 = shell.find('h1')
        if h1 and h1.get_text(strip=True):
            data['title'] = h1.get_text(" ", strip=True)

        body = shell.find('div', class_='article-body')
        if body:
            for tag in body(['script', 'style']):
                tag.decompose()
            text = body.get_text(separator='\n', strip=True)
            if text:
                data['content'] = text

        img = shell.select_one('.article-photo-grid img[src]')
        if img:
            data['image_url'] = self._build_url(img['src'])

        return data
