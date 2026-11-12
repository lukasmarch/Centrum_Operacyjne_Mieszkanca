"""
BIP Gminy Rybno Scraper (Sprint 5D)

Scrapuje Biuletyn Informacji Publicznej Gminy Rybno:
  https://bip.gminarybno.pl/112/  – aktualności (1420+ pozycji)

Strategia 3-poziomowa (RAG-aware):
  Poziom 1: HTML scraper headlines → tytuł, data, link, excerpt
  Poziom 2: PDF extraction via pdfplumber (lub Firecrawl fallback)
  Poziom 3: (RAG faza) Embeddings z content → pgvector

System: SYSTEMDOBIP.PL (E-LINE), brak RSS
URL pattern news: https://bip.gminarybno.pl/112/{id}/{slug}/
"""
import asyncio
import io
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.polite import BIP_HEADERS, HostBlocked, transport as polite_transport
from src.utils.logger import setup_logger

logger = setup_logger("BipRybnoScraper")

BIP_BASE_URL = "https://bip.gminarybno.pl"
BIP_NEWS_URL = f"{BIP_BASE_URL}/112/"

# 6.11.2026 BIP odpowiadał po ~35 s, a domyślne 30 s liczyło to jako awarię.
# JEDNA próba (12.11.2026, trzecia blokada): wiszący serwer nie zyskuje na
# ponawianiu, a dla jego zabezpieczeń powtórka to „nietypowa aktywność”.
# Brak odpowiedzi kończy przebieg — `polite` zamyka host na godzinę.
BIP_TIMEOUT_S = 60
BIP_MAX_RETRIES = 1

# Wpisy z listy z datą sprzed okna świeżości. Nie trafiają do bazy, więc
# `_known_ids` ich nie widzi i bez tej pamięci każdy przebieg pobierał je
# od nowa (3772 i 3769: 3 żądania zamiast 1, 2–5.11.2026). Data publikacji się
# nie zmienia, więc wpis raz za stary zostaje za stary. Restart procesu kosztuje
# jedno ponowne pobranie — nie ma tu czego utrwalać w bazie.
_TOO_OLD_IDS: Set[str] = set()



class BipRybnoScraper(BaseScraper):
    """
    Scraper dla BIP Gminy Rybno.

    Config (Source.scraping_config):
        news_url: URL listy aktualności (domyślnie /112/)
        download_pdfs: bool – czy pobierać PDF i wyciągać tekst (domyślnie True)
        (Firecrawl i paginacja usunięte 12.11.2026 — patrz `scrape_bip`.)
    """

    def __init__(self, source_id: int, config: Optional[Dict] = None):
        super().__init__(source_id, config)
        self.timeout = self.config.get("timeout", BIP_TIMEOUT_S)
        self.max_retries = BIP_MAX_RETRIES  # bez nadpisywania z configu źródła
        self.news_url = self.config.get("news_url", BIP_NEWS_URL)
        self.download_pdfs = self.config.get("download_pdfs", True)
        self.pdf_extraction = "pdfplumber"  # jedyna droga: przez nasz transport
        # Firecrawl pobiera plik z WŁASNYCH serwerów: inny adres IP, inny
        # User-Agent, poza naszym tempem i limitami — dla dostawcy BIP to obcy
        # bot. Wyłączone na stałe (12.11.2026); skan bez tekstu to skan bez tekstu.
        self.firecrawl_fallback = False
        self.cutoff_days = self.config.get("cutoff_days", 2)

    async def __aenter__(self):
        """Nadpisuje base – nagłówki i tempo z `polite` (uczciwy UA, ≥ 1,5 s między żądaniami)."""
        self.client = httpx.AsyncClient(
            headers=BIP_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
            transport=polite_transport(),
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    # ==================== Listing Page Parser ====================

    async def parse(self, html: str, url: str) -> List[Dict]:
        """
        Parse strony z listingiem aktualności BIP (/112/).
        Struktura: każdy artykuł w <div class="information"><p class="phx ph3"><a href="...">
        Daty nie są na listingu – pobierane ze strony szczegółów.
        """
        soup = BeautifulSoup(html, "lxml")
        articles = []

        # BIP Rybno: artykuły w <div class="information"> z linkiem /112/{id}/
        info_divs = soup.find_all("div", class_="information")
        self.logger.info(f"Found {len(info_divs)} div.information on: {url}")

        for div in info_divs:
            try:
                article_data = self._parse_listing_item(div, url)
                if article_data:
                    articles.append(article_data)
            except Exception as e:
                self.logger.error(f"Error parsing item: {e}")
                continue

        return articles

    def _parse_listing_item(self, div, base_url: str) -> Optional[Dict]:
        """Parse <div class='information'> – pojedynczy artykuł na liście."""
        link_el = div.find("a", href=re.compile(r"/112/\d+/"))
        if not link_el:
            return None

        href = link_el.get("href", "")
        if not href:
            return None

        # Pomijaj linki archiwum (/112/1/archiwum/)
        if "/archiwum/" in href or re.search(r"/112/1/", href):
            return None

        article_url = href if href.startswith("http") else urljoin(BIP_BASE_URL, href)

        # ID z URL: /112/3624/slug/ → "bip_3624"
        match = re.search(r"/112/(\d+)/", href)
        if not match:
            return None
        external_id = f"bip_{match.group(1)}"

        # Tekst linku ma prawdziwy tytuł; atrybut title="Przejdź do szczegółów..." - ignoruj
        title = link_el.get_text(strip=True)
        if not title or len(title) < 3 or title.lower().startswith("przejdź"):
            # Fallback: zdekoduj tytuł ze slugu URL
            slug = href.rstrip("/").split("/")[-1]
            title = slug.replace("_", " ").replace("%2C", ",").replace("%28", "(").replace("%29", ")")[:200]
        if not title or len(title) < 3:
            return None

        return {
            "title": title,
            "url": article_url,
            "external_id": external_id,
            "published_at": None,   # Pobierane w scrape_detail()
            "summary": None,
            "content": None,
        }

    # ==================== Detail Page Parser ====================

    async def scrape_detail(self, url: str) -> Dict:
        """
        Pobierz stronę szczegółów artykułu BIP.
        Wyciąga: datę publikacji (div.information-parameters), treść, linki PDF.
        """
        try:
            html = await self.fetch(url)
            soup = BeautifulSoup(html, "lxml")

            # Data publikacji – "Informacja ogłoszona dnia 2026-02-17 11:17:43 przez..."
            published_at = None
            params_div = soup.find("div", class_="information-parameters")
            if params_div:
                params_text = params_div.get_text(" ", strip=True)
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", params_text)
                if date_match:
                    try:
                        published_at = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    except ValueError:
                        pass

            # Treść artykułu – div.information (główny kontener treści)
            # Na stronie szczegółów info_div zawiera pełny tekst
            content_text = None
            info_div = soup.find("div", class_="information")
            if info_div:
                # Usuń navigation i parametry
                for tag in info_div.find_all(["nav", "script", "style"]):
                    tag.decompose()
                content_text = info_div.get_text("\n", strip=True)
                if len(content_text) < 20:
                    content_text = None

            # Linki do PDF – BIP używa /system/pobierz.php lub bezpośrednich .pdf
            pdf_links = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if ".pdf" in href.lower() or "pobierz.php" in href.lower():
                    pdf_url = href if href.startswith("http") else urljoin(BIP_BASE_URL, href)
                    pdf_links.append(pdf_url)

            return {
                "published_at": published_at,
                "content": content_text[:1000] if content_text else None,  # limit 1000 znaków (RAG będzie czytał PDF)
                "pdf_url": pdf_links[0] if pdf_links else None,
                "all_pdf_urls": pdf_links,
            }
        except HostBlocked:
            # Host zamknięty — kolejne wpisy dostałyby to samo bez sieci; przerwij przebieg.
            raise
        except Exception as e:
            self.logger.error(f"Error scraping detail {url}: {e}")
            return {"published_at": None, "content": None, "pdf_url": None, "all_pdf_urls": []}

    # ==================== PDF Extraction ====================

    async def extract_pdf_text(self, pdf_url: str) -> Optional[str]:
        """
        Wyciągnij tekst z PDF.
        Próbuje pdfplumber lokalnie, fallback do Firecrawl jeśli konfiguracja na to pozwala.
        """
        # Próba 1: pdfplumber (lokalny, bezpłatny)
        if self.pdf_extraction == "pdfplumber":
            text = await self._extract_with_pdfplumber(pdf_url)
            if text:
                return text

        # Próba 2: Firecrawl fallback
        if self.firecrawl_fallback:
            try:
                from src.integrations.firecrawl_client import firecrawl_client
                if firecrawl_client._is_configured():
                    self.logger.info(f"Using Firecrawl fallback for PDF: {pdf_url}")
                    return await firecrawl_client.extract_pdf_text(pdf_url)
            except Exception as e:
                self.logger.error(f"Firecrawl PDF fallback failed: {e}")

        return None

    async def _extract_with_pdfplumber(self, pdf_url: str) -> Optional[str]:
        """Pobierz PDF i wyciągnij tekst via pdfplumber."""
        try:
            import pdfplumber

            # Pobierz PDF jako bytes — klient jest już otwarty przez `async with self`
            # w scrape_bip(); `async with self.client` zamykałby go po pierwszym PDF
            response = await self.client.get(pdf_url)
            response.raise_for_status()
            pdf_bytes = response.content

            # Wyciągnij tekst
            text_parts = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            if text_parts:
                full_text = "\n\n".join(text_parts)
                self.logger.info(f"pdfplumber extracted {len(full_text)} chars from {pdf_url}")
                return full_text[:20000]  # Limit do 20k znaków
            else:
                self.logger.warning(f"pdfplumber: no text in PDF (may be scanned): {pdf_url}")
                return None

        except ImportError:
            self.logger.error("pdfplumber not installed – run: pip install pdfplumber")
            return None
        except Exception as e:
            self.logger.error(f"pdfplumber error for {pdf_url}: {e}")
            return None

    # ==================== Main Scraping Loop ====================

    async def _known_ids(self, session, external_ids: List[str]) -> set:
        """external_id wpisów z listy, które JUŻ są w bazie — bez względu na wiek.

        Do 12.11.2026 pomijane były tylko wpisy starsze niż okno świeżości, więc
        wpis z dziś był pobierany (strona + PDF) przy każdym przebiegu przez dwie
        doby — do 4 razy. Ogłoszenie BIP nie zmienia się po publikacji, a gdyby
        urząd je poprawił, nowa wersja dostaje zwykle nowy wpis.
        """
        from sqlalchemy import select
        from src.database.schema import Article

        if not external_ids:
            return set()
        rows = await session.execute(
            select(Article.external_id).where(
                Article.source_id == self.source_id,
                Article.external_id.in_(external_ids),
            )
        )
        return {r[0] for r in rows.all()}

    async def scrape_bip(self, session) -> List[int]:
        """
        Jeden przebieg: JEDNA strona listy `/112/` + szczegóły (i PDF) wyłącznie
        nowych wpisów z okna świeżości.

        Ile żądań: 1 (lista) + 2 na każdy nowy wpis. Typowo 1–3.
        ⚠️ Bez paginacji: do 12.11.2026 kod po każdym nowym wpisie pytał też
        o `?start=10`, który BIP ignoruje (zwraca tę samą stronę) — czyste
        marnotrawstwo żądań. Przy dwóch przebiegach dziennie (6:00, 13:00)
        dziesięć pozycji listy z naddatkiem pokrywa okno dwóch dni.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.cutoff_days)
        url = self.news_url

        async with self:
            self.logger.info(f"Scraping BIP: {url}")
            # Błąd strony listy = źródło nie odpowiada; idzie wyżej (audyt F-019:
            # pusty wynik nie może udawać „brak aktualności”).
            html = await self.fetch(url)
            articles = await self.parse(html, url)
            if not articles:
                self.logger.info("Lista BIP pusta — nic do zrobienia")
                return []

            known = await self._known_ids(session, [a["external_id"] for a in articles])
            fresh_articles = []
            for article in articles:
                if article["external_id"] in known or article["external_id"] in _TOO_OLD_IDS:
                    continue
                detail = await self.scrape_detail(article["url"])

                if detail.get("published_at"):
                    article["published_at"] = detail["published_at"]

                # Filtr daty: pomijaj artykuły starsze niż okno świeżości
                if article.get("published_at") and article["published_at"] < cutoff_date:
                    self.logger.debug(
                        f"Skipping old article ({article['published_at'].date()}): {article['title'][:60]}"
                    )
                    _TOO_OLD_IDS.add(article["external_id"])
                    continue

                if detail.get("content"):
                    article["content"] = detail["content"]

                # PDF — pełna treść dokumentu dla RAG (flaga download_pdfs w config źródła)
                if self.download_pdfs and detail.get("pdf_url"):
                    pdf_text = await self.extract_pdf_text(detail["pdf_url"])
                    if pdf_text:
                        article["content"] = pdf_text

                fresh_articles.append(article)

            if not fresh_articles:
                self.logger.info(f"Brak nowych wpisów BIP (znane: {len(known)})")
                return []

            saved_ids = await self.save_to_db(fresh_articles, session)
            self.logger.info(f"BIP: zapisano {len(saved_ids)} nowych wpisów")
            return saved_ids
