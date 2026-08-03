"""
BIP Gminy Rybno — wiedza stała (2026-08-03)

Druga połowa BIP-u. `bip_rybno.py` czyta strumień: dział /112/, ostatnie dwa dni,
treść ucięta do 1000 znaków, bo obwieszczenie i tak za tydzień będzie nieaktualne.
Ten scraper czyta rzeczy, które się nie starzeją — statut, procedury załatwiania
spraw, stawki podatków, programy środowiskowe (usuwanie azbestu, Czyste Powietrze),
fundusz sołecki. Stąd trzy różnice, wszystkie celowe:

  1. BEZ cutoff dat. Statut z 2016 r. obowiązuje tak samo jak wczorajszy.
  2. BEZ limitu treści. Odpowiedź na „ile dostanę na wymianę dachu z eternitu"
     jest w PDF-ie regulaminu, a nie w tytule.
  3. WSZYSTKIE załączniki, nie pierwszy. Scraper aktualności bierze `pdf_links[0]`
     i gubi resztę — a przy programie dotacyjnym pierwszy plik to zwykle
     ogłoszenie, konkrety siedzą we wniosku i regulaminie.

Zakres jest jawną listą działów (`DEFAULT_SECTIONS`), nie pełzaniem po drzewie.
BIP zawiera dużo materiału bez wartości dla mieszkańca (wybory z 2024,
oświadczenia majątkowe, rejestry zmian); wciągnięcie wszystkiego rozcieńczyłoby
retrieval i utopiło odpowiedź w szumie.

Struktura BIP (SYSTEMDOBIP.PL): dział `/{id}/Nazwa/` zawiera listę artykułów
`/{id}/{nr}/Slug/`. Część działów ma też własną treść wprost na stronie działu
(np. /125/ Statut, /147/ Jednostki pomocnicze) — bierzemy jedno i drugie.
"""
import asyncio
import hashlib
import io
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.utils.logger import setup_logger

logger = setup_logger("BipKnowledgeScraper")

# Skany urzędowe mają połamane profile kolorów i pdfminer krzyczy o tym raz na
# stronę („Cannot set gray non-stroke color"). Przy kilkuset stronach PDF-ów
# w jednym przebiegu to setki linii, które przykrywają realne błędy w logu.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

BIP_BASE_URL = "https://bip.gminarybno.pl"

# Ten sam zestaw nagłówków co w bip_rybno — serwer BIP odrzuca botowe User-Agenty (403).
BIP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Działy wiedzy stałej: (id działu, nazwa dla człowieka i dla nagłówka chunku).
# Nazwy są tu wpisane, a nie brane ze strony, bo trafiają do promptu agenta —
# „Ochrona środowiska" niesie sens, „/74/" nie niesie żadnego.
DEFAULT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("125", "Statut Gminy"),
    ("147", "Jednostki pomocnicze (sołectwa)"),
    ("2", "Jednostki organizacyjne"),
    ("19", "Urząd Gminy — dane podstawowe"),
    ("10040", "Rada Gminy"),
    ("10042", "Wójt Gminy"),
    ("105", "Podatki i opłaty"),
    ("74", "Ochrona środowiska"),
    ("222", "Informacje o środowisku"),
    ("218", "Ocena jakości wody"),
    ("223", "Gospodarka odpadami"),
    ("220", "Rolnictwo i łowiectwo"),
    ("248", "Fundusz sołecki"),
    ("249", "Bezpłatne porady prawne"),
    ("76", "Strategie, raporty, opracowania"),
    ("190", "Współpraca z organizacjami pozarządowymi"),
    ("10008", "Ponowne wykorzystanie informacji publicznej"),
)

# Ile znaków treści zapisujemy na dokument. Regulamin dotacji potrafi mieć
# kilkanaście stron; chunker i tak potnie to na kawałki po ~1800 znaków.
MAX_CONTENT_CHARS = 40_000
MAX_PDF_PER_DOC = 5          # regulamin + wniosek + załączniki, dalej to już archiwum
MAX_DOCS_PER_SECTION = 40

# Poniżej tego progu wpis nie niesie odpowiedzi na żadne pytanie — to sam tytuł
# powtórzony ze strony działu albo zajawka odsyłająca do skanu bez warstwy
# tekstowej. W przebiegu 3.08.2026 takich pustych wpisów po 31-73 znaki było
# kilkanaście; w RAG konkurowałyby o miejsce z treścią, która coś mówi.
MIN_CONTENT_CHARS = 150

# Elementy nawigacji SYSTEMDOBIP obecne na każdej podstronie — w treści dokumentu
# są czystym szumem, a trafiłyby do embeddingu i rozmyły podobieństwo.
_BOILERPLATE = re.compile(
    r"(Rejestr zmian|Pobierz dane XML|Drukuj informację|Szybki przeskok do bloku"
    r"|Artykuł był wyświetlony|Podmiot udostępniający informację"
    r"|Osoba, która (wytworzyła|wytworzyla|zmieniła|odpowiada)"
    r"|Data (wprowadzenia|udostępnienia|ostatniej zmiany|wytworzenia)"
    r"|Wprowadził informację do BIP|Zobacz pełną listę zmian"
    r"|Wszelkie prawa do programu|Akapit nr \d+ - brak tytułu)",
    re.I,
)


class BipKnowledgeScraper:
    """Pobiera stałe działy BIP. Nie dziedziczy po BaseScraper: nie zapisuje
    do `articles` i nie ma nic wspólnego z cyklem newsowym."""

    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        sections = config.get("sections")
        self.sections: tuple[tuple[str, str], ...] = (
            tuple((str(s["id"]), s["name"]) for s in sections) if sections else DEFAULT_SECTIONS
        )
        self.download_pdfs = config.get("download_pdfs", True)
        self.max_docs_per_section = config.get("max_docs_per_section", MAX_DOCS_PER_SECTION)
        self.timeout = config.get("timeout", 45)
        self.delay = config.get("delay", 0.4)
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers=BIP_HEADERS, timeout=self.timeout, follow_redirects=True
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    # ==================== Pobieranie ====================

    async def _fetch(self, url: str, attempts: int = 3) -> Optional[str]:
        """Pobiera stronę, ponawiając przy błędzie.

        Bez ponawiania jedno nieudane żądanie gubi CAŁY dział po cichu:
        `scrape_section` dostaje None i zwraca pustą listę, a job melduje sukces.
        Tak przepadły sołectwa w przebiegu 3.08.2026 — dział, który w izolacji
        pobiera się bez problemu. BIP przy ~150 żądaniach pod rząd potrafi
        zerwać połączenie.
        """
        for attempt in range(1, attempts + 1):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt == attempts:
                    logger.warning(f"Nie udało się pobrać {url} ({attempts} prób): {e}")
                    return None
                await asyncio.sleep(self.delay * 2 * attempt)
        return None

    def _section_links(self, html: str, section_id: str) -> List[str]:
        """Linki do artykułów w obrębie działu: /{section_id}/{nr}/{slug}/."""
        links: list[str] = []
        seen: set[str] = set()
        pattern = re.compile(rf"^(?:https?://bip\.gminarybno\.pl)?/{section_id}/(\d+)/")

        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = pattern.match(href)
            if not match:
                continue
            # /{sekcja}/1/archiwum/ to nie dokument, tylko wejście do archiwum;
            # /rejestr/ i /drukuj/ to widoki tej samej treści
            if match.group(1) == "1" or re.search(r"/(rejestr|drukuj)/?$", href):
                continue
            url = href if href.startswith("http") else urljoin(BIP_BASE_URL, href)
            url = url.replace("http://bip.", "https://bip.")
            if url in seen:
                continue
            seen.add(url)
            links.append(url)
        return links

    def _parse_document(self, html: str) -> Dict:
        """Tytuł, treść i linki do załączników ze strony dokumentu."""
        soup = BeautifulSoup(html, "lxml")

        info = soup.find("div", class_="information")
        content = ""
        if info:
            for tag in info.find_all(["nav", "script", "style"]):
                tag.decompose()
            lines = [
                line.strip()
                for line in info.get_text("\n", strip=True).split("\n")
                if line.strip() and not _BOILERPLATE.search(line)
            ]
            content = "\n".join(lines)

        # Tytuł to pierwsza linia treści, nie <h1>. W SYSTEMDOBIP <h1> na każdej
        # podstronie brzmi „Biuletyn Informacji Publicznej", więc wszystkie
        # dokumenty nazywałyby się tak samo — a tytuł idzie do nagłówka chunku
        # i do chipa źródła w UI.
        title = lines[0] if info and lines else ""
        if len(title) < 4 or "biuletyn informacji publicznej" in title.lower():
            heading = soup.find("h2")
            title = heading.get_text(" ", strip=True) if heading else ""

        document_date = None
        params = soup.find("div", class_="information-parameters")
        if params:
            match = re.search(r"(\d{4}-\d{2}-\d{2})", params.get_text(" ", strip=True))
            if match:
                try:
                    document_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                except ValueError:
                    pass

        pdf_urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower() or "pobierz.php" in href.lower():
                url = href if href.startswith("http") else urljoin(BIP_BASE_URL, href)
                if url not in pdf_urls:
                    pdf_urls.append(url)

        return {
            "title": title,
            "content": content,
            "document_date": document_date,
            "pdf_urls": pdf_urls[:MAX_PDF_PER_DOC],
        }

    async def _extract_pdf(self, pdf_url: str) -> Optional[str]:
        """Tekst z PDF-a przez pdfplumber. Skany bez warstwy tekstowej zwracają
        pustkę — nie robimy OCR, bo to osobny koszt i osobna decyzja."""
        try:
            import pdfplumber

            response = await self.client.get(pdf_url)
            response.raise_for_status()

            parts: list[str] = []
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        parts.append(page_text)
            if not parts:
                logger.info(f"PDF bez warstwy tekstowej (skan?): {pdf_url}")
                return None
            return "\n\n".join(parts)
        except Exception as e:
            logger.warning(f"Błąd odczytu PDF {pdf_url}: {e}")
            return None

    @staticmethod
    def _pdf_label(pdf_url: str) -> str:
        """Nazwa pliku z linku — w treści zaznacza, z którego załącznika pochodzi
        fragment ('OBWIESZCZENIE_-_konsultacje.pdf')."""
        match = re.search(r"plik=([^&]+)", pdf_url)
        if match:
            return match.group(1)
        return urlparse(pdf_url).path.rsplit("/", 1)[-1] or "załącznik.pdf"

    async def scrape_document(self, url: str, section_id: str, section_name: str) -> Optional[Dict]:
        """Jeden dokument: treść strony + tekst ze wszystkich załączników."""
        html = await self._fetch(url)
        if not html:
            return None

        parsed = self._parse_document(html)
        parts = [parsed["content"]] if parsed["content"] else []

        pdf_count = 0
        if self.download_pdfs:
            for pdf_url in parsed["pdf_urls"]:
                text = await self._extract_pdf(pdf_url)
                await asyncio.sleep(self.delay)
                if text:
                    # Załącznik NIE nadpisuje treści strony (tak robi scraper
                    # aktualności i gubi kontekst) — dokłada się do niej.
                    parts.append(f"[Załącznik: {self._pdf_label(pdf_url)}]\n{text}")
                    pdf_count += 1

        content = "\n\n".join(p for p in parts if p).strip()[:MAX_CONTENT_CHARS]
        if len(content) < MIN_CONTENT_CHARS:
            logger.debug(f"Pomijam wpis bez treści ({len(content)} zn.): {url}")
            return None

        return {
            "section_id": section_id,
            "section_name": section_name,
            "url": url,
            "title": (parsed["title"] or section_name)[:500],
            "content": content,
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "pdf_count": pdf_count,
            "document_date": parsed["document_date"],
        }

    async def scrape_section(self, section_id: str, section_name: str) -> List[Dict]:
        """Dział: własna treść strony działu + wszystkie jego artykuły."""
        section_url = f"{BIP_BASE_URL}/{section_id}/"
        html = await self._fetch(section_url)
        if not html:
            return []

        documents: list[Dict] = []

        # Część działów trzyma treść wprost na swojej stronie (Statut, Sołectwa),
        # inne są samą listą odnośników — sprawdzamy jedno i drugie.
        own = await self.scrape_document(section_url, section_id, section_name)
        if own:
            documents.append(own)

        links = self._section_links(html, section_id)[: self.max_docs_per_section]
        logger.info(f"[{section_id}] {section_name}: {len(links)} artykułów")

        for link in links:
            await asyncio.sleep(self.delay)
            doc = await self.scrape_document(link, section_id, section_name)
            if doc:
                documents.append(doc)

        return documents

    async def scrape_all(self) -> List[Dict]:
        """Wszystkie skonfigurowane działy. Błąd jednego nie przerywa reszty."""
        all_documents: list[Dict] = []
        async with self:
            for section_id, section_name in self.sections:
                try:
                    docs = await self.scrape_section(section_id, section_name)
                    all_documents.extend(docs)
                    logger.info(f"[{section_id}] {section_name}: zebrano {len(docs)} dokumentów")
                except Exception as e:
                    logger.error(f"Dział {section_id} ({section_name}) nie powiódł się: {e}")
                await asyncio.sleep(self.delay)
        return all_documents
