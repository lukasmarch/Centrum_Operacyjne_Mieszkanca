"""
Scraper aktów prawnych gminy — uchwały Rady i zarządzenia Wójta (etap 4, 2026-08-24)

**To INNY moduł BIP niż wiedza stała.** `bip_knowledge` chodzi po działach
(`/105/Podatki_i_oplaty/`), ten po rejestrze aktów (`/akty/14/`). Rejestr ma
własną paginację, własną tabelę metadanych i inną strukturę strony
szczegółowej — dlatego osobny plik, a nie parametr w tamtym.

**Struktura, rozpoznana 24.08:**

* lista: `/akty/14/typ/` (strona 1), dalej `/akty/14/{strona}/typ/`;
  filtry rodzaju: `/typ/16/` = uchwały Rady, `/typ/17/` = zarządzenia Wójta.
  Bierzemy listę BEZ filtra — jeden przebieg zamiast dwóch, a rodzaj i tak
  stoi w kolumnie „Grupa tematyczna";
* tabela: Lp | Data podjęcia | Grupa tematyczna | Tytuł aktu | Nr aktu | Status.
  Komórki niosą etykietę w treści („Data podjęcia 2026-06-24") — to układ
  responsywny, nie błąd parsowania. Etykietę trzeba obciąć;
* szczegóły: `/akty/14/{bip_id}/{slug}/` — data wejścia w życie i link do PDF;
* **treść aktu jest WYŁĄCZNIE w PDF-ie** (`/system/pobierz.php?plik=…&id=…`).
  Na szczęście z warstwą tekstową: uchwała XXIII/178/2026 to 1766 znaków
  z pliku 1,5 MB. Eksport „Pobierz dane XML" jest ślepy — zwraca stronę główną.

**Lista jest posortowana kolejnością WPROWADZENIA do BIP, nie datą podjęcia
— i to nie jest drobiazg.** Z grubsza wygląda na malejącą po dacie, ale wśród
aktów z kwietnia 2025 (strona 23) siedzi zarządzenie z 2 listopada 2023:
wprowadzono je do rejestru z opóźnieniem. Pierwsza wersja przerywała skan na
pierwszym akcie starszym niż próg i przez ten jeden wpis kończyła na 229
aktach zamiast ~440.

Dlatego przerywamy dopiero po `EMPTY_PAGES_TO_STOP` stronach POD RZĄD, na
których nie ma ani jednego aktu w zakresie. Pojedynczy odstający wpis nic
wtedy nie psuje, a akty spoza zakresu i tak są pomijane po dacie.

⚠️ Serwer gminy jest mały. Między żądaniami jest odstęp, a PDF-y pobieramy
tylko dla aktów, których jeszcze nie mamy (`bip_id`) — ponowny przebieg
kosztuje kilkanaście żądań na listę, nie kilkaset na pliki.
"""
import asyncio
import hashlib
import io
import logging
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
import pdfplumber
from bs4 import BeautifulSoup

from src.utils.logger import setup_logger

logger = setup_logger("LegalActsScraper")

# Skany urzędowe mają połamane profile kolorów; pdfminer krzyczy o tym raz na
# stronę. Przy kilkuset plikach to setki linii przykrywających realne błędy.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

BIP_BASE = "https://bip.gminarybno.pl"
ACTS_PATH = "/akty/14"

# Ten sam zestaw co w `bip_knowledge` — serwer odrzuca botowe User-Agenty (403).
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

# Zakres decyzją Łukasza (22.08). Akt sprzed dekady odpowiada na pytania,
# których nikt nie zadaje, a rozcieńcza wyniki wyszukiwarki.
DEFAULT_SINCE = date(2024, 1, 1)

# Bezpiecznik na wypadek, gdyby warunek daty przestał przerywać pętlę.
# 60 stron = 600 aktów, czyli grubo ponad zakres 2024–2026 (~440).
MAX_PAGES = 60

# Ile stron POD RZĄD bez aktu w zakresie kończy skan. Dwie, bo lista nie jest
# ułożona ściśle po dacie (patrz docstring modułu) — jedna strona bez trafienia
# może być przypadkiem, dwie oznaczają, że zeszliśmy poniżej progu.
EMPTY_PAGES_TO_STOP = 2

# Ile znaków treści zapisujemy. Uchwała budżetowa z załącznikami tabelarycznymi
# potrafi mieć kilkadziesiąt stron; chunker i tak potnie to na kawałki.
MAX_CONTENT_CHARS = 40_000

# Odstęp między żądaniami. Serwer gminy obsługuje kilka osób naraz, a my w jednym
# przebiegu robimy kilkaset żądań — to nie jest miejsce na oszczędzanie sekund.
REQUEST_DELAY_S = 0.4

_LABELS = ("Lp", "Data podjęcia", "Grupa tematyczna", "Tytuł aktu",
           "Nr aktu prawnego", "Status")


def _strip_label(text: str) -> str:
    """Komórki niosą etykietę w treści („Data podjęcia 2026-06-24") — to układ
    responsywny BIP, nie błąd parsowania."""
    out = (text or "").strip()
    for label in _LABELS:
        if out.startswith(label):
            out = out[len(label):].strip()
            if out.startswith(":"):
                out = out[1:].strip()
            break
    return out


def _parse_date(text: str) -> Optional[date]:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _bip_id(href: str) -> Optional[int]:
    """`/akty/14/2878/UCHWALA…/` → 2878. Jedyny stabilny identyfikator aktu:
    tytuł bywa poprawiany, a numer aktu potrafi się powtórzyć między kadencjami.

    ⚠️ Negatywne spojrzenie w przód na `typ/` nie jest ozdobą: adres paginacji
    ma ten sam kształt (`/akty/14/2/typ/16/`) i bez tego dawał „akt nr 2".
    Dziś parser bierze pierwszy link w wierszu, więc błąd nie wychodził —
    ale każda zmiana układu tabeli wpuściłaby stronę listy do bazy jako akt.
    """
    m = re.search(r"/akty/14/(\d+)/(?!typ(?:/|$))", href or "")
    return int(m.group(1)) if m else None


class LegalActsScraper:
    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            headers=BIP_HEADERS, timeout=self.timeout, follow_redirects=True
        )
        return self

    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()

    async def _get(self, url: str) -> Optional[httpx.Response]:
        try:
            resp = await self._client.get(url)
            if resp.status_code != 200:
                logger.warning(f"{url} → HTTP {resp.status_code}")
                return None
            return resp
        except Exception as e:
            logger.warning(f"{url} → {e}")
            return None

    def _list_url(self, page: int) -> str:
        return (
            f"{BIP_BASE}{ACTS_PATH}/typ/" if page == 1
            else f"{BIP_BASE}{ACTS_PATH}/{page}/typ/"
        )

    async def list_acts(self, since: date = DEFAULT_SINCE) -> list[dict]:
        """Metadane aktów z listy, od najnowszego do progu `since`.

        Nie wchodzi na strony szczegółowe i nie pobiera PDF-ów — to osobny,
        drogi krok, który robimy tylko dla aktów jeszcze nieznanych bazie.
        """
        found: list[dict] = []
        seen_ids: set[int] = set()
        empty_pages = 0

        for page in range(1, MAX_PAGES + 1):
            resp = await self._get(self._list_url(page))
            if resp is None:
                # Pojedyncza strona potrafi nie odpowiedzieć; przerwanie całego
                # przebiegu przez jeden timeout byłoby przesadą.
                logger.warning(f"strona {page} nie odpowiedziała — pomijam")
                await asyncio.sleep(REQUEST_DELAY_S)
                continue

            rows = self._parse_list(resp.text)
            if not rows:
                logger.info(f"strona {page}: brak wierszy — koniec listy")
                break

            hits = 0
            for row in rows:
                if row["adopted_at"] and row["adopted_at"] < since:
                    continue  # akt spoza zakresu — pomijamy, ale NIE przerywamy
                if row["bip_id"] in seen_ids:
                    # Paginacja BIP potrafi powtórzyć pozycję na styku stron.
                    continue
                seen_ids.add(row["bip_id"])
                found.append(row)
                hits += 1

            empty_pages = 0 if hits else empty_pages + 1
            logger.info(
                f"strona {page}: {len(rows)} poz., w zakresie {hits}, "
                f"narastająco {len(found)}"
                + (f" [bez trafień: {empty_pages}]" if empty_pages else "")
            )
            if empty_pages >= EMPTY_PAGES_TO_STOP:
                logger.info(f"Koniec zakresu — {empty_pages} strony pod rząd bez trafień")
                break
            await asyncio.sleep(REQUEST_DELAY_S)

        return found

    def _parse_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        out = []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) < 6:
                continue
            link = tr.find("a", href=True)
            bip_id = _bip_id(link["href"]) if link else None
            if bip_id is None:
                continue
            out.append({
                "bip_id": bip_id,
                "url": urljoin(BIP_BASE, link["href"]),
                "adopted_at": _parse_date(_strip_label(cells[1].get_text(" ", strip=True))),
                "act_group": _strip_label(cells[2].get_text(" ", strip=True))[:120],
                "title": _strip_label(cells[3].get_text(" ", strip=True)),
                "act_number": _strip_label(cells[4].get_text(" ", strip=True))[:60] or None,
                "status": _strip_label(cells[5].get_text(" ", strip=True))[:60] or None,
            })
        return out

    async def fetch_details(self, act: dict) -> dict:
        """Uzupełnia akt o datę wejścia w życie, pełny tytuł i treść z PDF-u."""
        resp = await self._get(act["url"])
        if resp is None:
            return act

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)

        effective = None
        m = re.search(r"Data wejścia w życie:\s*\n\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            effective = _parse_date(m.group(1))
        act["effective_from"] = effective

        # Pełny tytuł ze strony szczegółowej — lista go ucina.
        m = re.search(r"Tytuł aktu:\s*\n(.+)", text)
        if m and len(m.group(1).strip()) > len(act.get("title") or ""):
            act["title"] = m.group(1).strip()

        pdf_url = self._find_pdf(soup)
        act["pdf_url"] = pdf_url
        act["content"] = await self._extract_pdf(pdf_url) if pdf_url else None
        return act

    @staticmethod
    def _find_pdf(soup: BeautifulSoup) -> Optional[str]:
        """Załącznik z treścią aktu. BIP serwuje pliki przez `pobierz.php`,
        więc rozszerzenie NIE stoi w ścieżce — szukamy po nazwie parametru."""
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "pobierz.php" in href and re.search(r"plik=.*\.pdf", href, re.I):
                return urljoin(BIP_BASE, href)
        return None

    async def _extract_pdf(self, pdf_url: str) -> Optional[str]:
        resp = await self._get(pdf_url)
        if resp is None:
            return None
        try:
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                pages = [(p.extract_text() or "") for p in pdf.pages]
            text = "\n".join(pages).strip()
            if not text:
                # Skan bez warstwy tekstowej. Nie jest to awaria — metadane
                # aktu i tak zostają w bazie i odpowiadają na pytanie „jakie
                # są najnowsze uchwały".
                logger.info(f"PDF bez warstwy tekstowej: {pdf_url[:80]}")
                return None
            return text[:MAX_CONTENT_CHARS]
        except Exception as e:
            logger.warning(f"Nie odczytałem PDF {pdf_url[:80]}: {e}")
            return None


def content_hash(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
