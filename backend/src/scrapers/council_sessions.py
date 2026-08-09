"""
Nagrania sesji Rady Gminy — wykrywanie, że jest co przepisać.

Gmina wrzuca nagrania obrad do galerii `gminarybno.pl/nagrania_wideo.html`,
a samo wideo trzyma na YouTube (iframe na podstronie). Ten scraper robi jedno:
zwraca listę sesji z adresem nagrania, żeby `scheduler/council_job.py` wiedział,
czy pojawiło się coś nowego. Transkrypcję i skrót robią osobne moduły.

**Dlaczego YouTube, skoro gmina ma też kanał na transmisjaobrad.info.**
Tamten serwis ma nagrań więcej (sesje nadzwyczajne z 15 i 25 czerwca 2026,
których w galerii gminy nie ma) i numeruje je inaczej — ale odtwarza je przez
własnego JS-owego playera bez publicznego adresu strumienia. YouTube da się
pobrać `yt-dlp`, więc źródłem jest galeria gminy, ze świadomością, że kilka
sesji nadzwyczajnych przez to ominiemy. Gdyby to zaczęło przeszkadzać,
drugie źródło jest do dopisania tutaj, a nie w pipelinie.

Rytm: ~1 sesja w miesiącu, z przerwą wakacyjną (ostatnia XXIII z 24.06.2026).
Job może chodzić raz na dobę i przez większość dni nie znajdzie nic nowego —
to normalny stan, nie awaria.

Test: `cd backend && python -m scripts.test_council_sessions [--live]`
"""
import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.utils.logger import setup_logger

logger = setup_logger("CouncilSessions")

GALLERY_URL = "https://gminarybno.pl/nagrania_wideo.html"

# Ten sam zestaw co w scraperach BIP — serwis gminy też odrzuca botowe User-Agenty.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

# Tytuł w galerii: „XXIII Sesja Rady Gminy Rybno z dnia 24.06.2026 r."
# Data bywa też w slugu (`...z-dnia-24062026-r,7556.html`) — czytamy z tytułu,
# bo slug gubi kropki i przy jednocyfrowym dniu robi się dwuznaczny.
_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")

# Numer sesji rzymski na początku tytułu. Sam w sobie nie identyfikuje nagrania
# (numeracja gminy różni się od tej na transmisjaobrad.info), więc służy tylko
# do etykiety — tożsamość niesie `page_id`.
_ROMAN_RE = re.compile(r"^([IVXLCDM]+)\s+[Ss]esja", re.UNICODE)

# Identyfikator podstrony: `...,7556.html`. Stabilny i unikalny — to on trafia
# do bazy jako `external_id`, nie URL (slug potrafi się zmienić przy korekcie
# literówki w tytule).
_PAGE_ID_RE = re.compile(r",(\d+)\.html")

_YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{11})"
)

# Galeria zawiera też nagrania niebędące obradami (spotkania konsultacyjne,
# imprezy). Skrót obrad ma inny prompt i inną wartość, więc typ rozstrzygamy tu.
_SESSION_RE = re.compile(r"sesja\s+rady\s+gminy", re.IGNORECASE)


@dataclass
class CouncilRecording:
    """Jedno nagranie z galerii gminy."""

    page_id: str
    title: str
    page_url: str
    youtube_id: Optional[str] = None
    session_date: Optional[date] = None
    session_number: Optional[str] = None

    @property
    def is_session(self) -> bool:
        """Czy to obrady rady, a nie spotkanie konsultacyjne albo festyn."""
        return bool(_SESSION_RE.search(self.title))

    @property
    def video_url(self) -> Optional[str]:
        if not self.youtube_id:
            return None
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    def watch_url_at(self, seconds: float) -> Optional[str]:
        """Link do konkretnej sekundy nagrania — pod każdym punktem skrótu."""
        if not self.youtube_id:
            return None
        return f"{self.video_url}&t={int(max(seconds, 0))}s"


def _parse_date(title: str) -> Optional[date]:
    match = _DATE_RE.search(title)
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        logger.warning("Niepoprawna data w tytule nagrania: %r", title)
        return None


def parse_gallery(html: str, base_url: str = GALLERY_URL) -> List[CouncilRecording]:
    """Lista nagrań ze strony galerii. Bez sieci — testowalne na zapisanym HTML."""
    soup = BeautifulSoup(html, "html.parser")
    found: dict = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "nagrania_wideo/" not in href:
            continue
        page_match = _PAGE_ID_RE.search(href)
        if not page_match:
            continue
        page_id = page_match.group(1)
        # Ten sam wpis występuje dwa razy (miniatura + podpis); tytuł jest
        # pełny w atrybucie `title`, tekst linku bywa ucięty.
        title = (anchor.get("title") or anchor.get_text() or "").strip()
        if page_id in found and len(title) <= len(found[page_id].title):
            continue
        roman = _ROMAN_RE.match(title)
        found[page_id] = CouncilRecording(
            page_id=page_id,
            title=re.sub(r"\s+", " ", title),
            page_url=urljoin(base_url, href),
            session_date=_parse_date(title),
            session_number=roman.group(1) if roman else None,
        )

    recordings = sorted(
        found.values(),
        key=lambda r: (r.session_date or date.min, int(r.page_id)),
        reverse=True,
    )
    logger.info("Galeria: %d nagrań, w tym %d sesji rady",
                len(recordings), sum(1 for r in recordings if r.is_session))
    return recordings


def extract_youtube_id(html: str) -> Optional[str]:
    """Identyfikator nagrania z podstrony (iframe YouTube)."""
    match = _YOUTUBE_RE.search(html)
    return match.group(1) if match else None


async def fetch_recordings(limit: int = 12, sessions_only: bool = True) -> List[CouncilRecording]:
    """
    Galeria + adresy nagrań. Podstrony pobieramy tylko dla `limit` najnowszych
    pozycji — galeria ma kilkaset wpisów wstecz, a interesuje nas świeżość.
    """
    async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True) as client:
        response = await client.get(GALLERY_URL)
        response.raise_for_status()
        recordings = parse_gallery(response.text)

        if sessions_only:
            recordings = [r for r in recordings if r.is_session]
        recordings = recordings[:limit]

        for recording in recordings:
            try:
                page = await client.get(recording.page_url)
                page.raise_for_status()
                recording.youtube_id = extract_youtube_id(page.text)
                if not recording.youtube_id:
                    logger.warning("Nagranie bez iframe YouTube: %s", recording.page_url)
            except httpx.HTTPError as exc:
                logger.warning("Nie udało się otworzyć %s: %s", recording.page_url, exc)

    return recordings


async def latest_session() -> Optional[CouncilRecording]:
    """Najnowsza sesja rady z dostępnym nagraniem."""
    for recording in await fetch_recordings(limit=6):
        if recording.youtube_id:
            return recording
    return None
