"""
Nagrania sesji Rady Gminy — wykrywanie, że jest co przepisać.

**Źródłem jest kanał YouTube gminy (RSS), od 26.10.2026.** Do 22.10 nagrania
wisiały w galerii `gminarybno.pl/nagrania_wideo.html` (podstrona z iframe
YouTube). Nowa strona gminy galerii nie ma — Rada Gminy odsyła już tylko do
kanału `@gminarybno5603`. Kanał wystawia publiczny RSS
(`/feeds/videos.xml?channel_id=…`, ~15 ostatnich filmów, odpowiada także
z serwera, mimo że sam YouTube blokuje serwerowi pobieranie nagrań).
Jedno żądanie zamiast galerii i sześciu podstron.

Tożsamość nagrania niesie `youtube_id`. `page_id` ma postać `yt:{id}` — ten
sam prefiks, którego używa `scripts/run_council_session` dla nagrań spoza
galerii; sesje sprzed 26.10 mają w `external_id` numer podstrony galerii, więc
job porównuje po `youtube_id`, nie po `external_id`.

**Dlaczego YouTube, skoro gmina ma też kanał na transmisjaobrad.info.**
Tamten serwis ma nagrań więcej (sesje nadzwyczajne z 15 i 25 czerwca 2026)
i numeruje je inaczej — ale odtwarza je przez własnego JS-owego playera bez
publicznego adresu strumienia. YouTube da się pobrać `yt-dlp`.

Rytm: ~1 sesja w miesiącu, z przerwą wakacyjną. Kiedy job w ogóle pyta,
rozstrzyga kalendarz (`scheduler/council_job.session_window_open`).

Test: `cd backend && python -m scripts.test_council_sessions [--live]`
"""
import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional
from xml.etree import ElementTree

import httpx

from src.scrapers.polite import BIP_HEADERS
from src.utils.logger import setup_logger

logger = setup_logger("CouncilSessions")

# Kanał „Gmina Rybno” (@gminarybno5603) — identyfikator z 26.10.2026.
CHANNEL_ID = "UCz9APkxyUnB6PNNi5IRtVlA"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"

_ATOM = "{http://www.w3.org/2005/Atom}"
_YT = "{http://www.youtube.com/xml/schemas/2015}"

# Tytuł w galerii: „XXIII Sesja Rady Gminy Rybno z dnia 24.06.2026 r."
# Data bywa też w slugu (`...z-dnia-24062026-r,7556.html`) — czytamy z tytułu,
# bo slug gubi kropki i przy jednocyfrowym dniu robi się dwuznaczny.
_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")

# Numer sesji rzymski na początku tytułu. Sam w sobie nie identyfikuje nagrania
# (numeracja gminy różni się od tej na transmisjaobrad.info), więc służy tylko
# do etykiety — tożsamość niesie `youtube_id`.
_ROMAN_RE = re.compile(r"^([IVXLCDM]+)\s+[Ss]esja", re.UNICODE)

# Kanał zawiera też nagrania niebędące obradami (spotkania konsultacyjne,
# imprezy). Skrót obrad ma inny prompt i inną wartość, więc typ rozstrzygamy tu.
_SESSION_RE = re.compile(r"sesja\s+rady\s+gminy", re.IGNORECASE)


@dataclass
class CouncilRecording:
    """Jedno nagranie z kanału gminy."""

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


def parse_feed(xml_text: str) -> List[CouncilRecording]:
    """Nagrania z kanału RSS YouTube, od najnowszego. Bez sieci — testowalne."""
    root = ElementTree.fromstring(xml_text)
    recordings: List[CouncilRecording] = []

    for entry in root.findall(f"{_ATOM}entry"):
        video_id = (entry.findtext(f"{_YT}videoId") or "").strip()
        title = re.sub(r"\s+", " ", (entry.findtext(f"{_ATOM}title") or "").strip())
        if not video_id or not title:
            continue
        roman = _ROMAN_RE.match(title)
        recordings.append(CouncilRecording(
            page_id=f"yt:{video_id}",
            title=title,
            page_url=f"https://www.youtube.com/watch?v={video_id}",
            youtube_id=video_id,
            session_date=_parse_date(title),
            session_number=roman.group(1) if roman else None,
        ))

    # Kanał podaje kolejność publikacji; sesja nadrabiana później nie może
    # wyprzedzić świeższych obrad.
    recordings.sort(key=lambda r: r.session_date or date.min, reverse=True)
    logger.info("Kanał YouTube: %d nagrań, w tym %d sesji rady",
                len(recordings), sum(1 for r in recordings if r.is_session))
    return recordings


async def fetch_recordings(limit: int = 12, sessions_only: bool = True) -> List[CouncilRecording]:
    """Najnowsze nagrania z kanału gminy — jedno żądanie do RSS YouTube."""
    async with httpx.AsyncClient(headers=BIP_HEADERS, timeout=30.0, follow_redirects=True) as client:
        response = await client.get(FEED_URL)
        response.raise_for_status()
    recordings = parse_feed(response.text)
    if sessions_only:
        recordings = [r for r in recordings if r.is_session]
    return recordings[:limit]


async def latest_session() -> Optional[CouncilRecording]:
    """Najnowsza sesja rady z dostępnym nagraniem."""
    recordings = await fetch_recordings(limit=1)
    return recordings[0] if recordings else None
