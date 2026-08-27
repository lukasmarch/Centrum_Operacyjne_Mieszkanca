"""
Transkrypcja sesji Rady Gminy — nagranie obrad → tekst ze znacznikami czasu.

Sesja trwa od kilkunastu minut (nadzwyczajna) do trzech godzin. Nikt tego nie
ogląda, więc obrady rady gminy są formalnie jawne i faktycznie niedostępne.
Transkrypt jest warstwą pośrednią: sam w sobie nieczytelny (trzy godziny mowy
to ~100 tys. znaków), ale to z niego `ai/council_summary.py` robi skrót,
a znaczniki czasu pozwalają podlinkować każdy punkt do minuty w nagraniu.

**Znacznik czasu jest tu funkcją bezpieczeństwa, nie ozdobą.** Skrót obrad
przypisuje wypowiedzi imiennie radnym i wójtowi. Jedyne, co odróżnia skrót od
pomówienia, to możliwość sprawdzenia w dwie sekundy, co naprawdę padło — stąd
`Segment.start` wędruje przez cały pipeline aż do linku `?t=` pod każdym punktem.

Dlaczego whisper-1, a nie nowsze modele transkrypcji: tylko on zwraca
`verbose_json` z segmentami. Nowsze dają czystszy tekst bez znaczników czasu,
czyli dokładnie bez tego, po co to robimy.

Pobieranie audio z YouTube jest z natury kruche (patrz `_YTDLP_ARGS`), dlatego
siedzi w osobnej funkcji — gdy YouTube znów zmieni zasady, psuje się jedno miejsce.

Test: `cd backend && python -m scripts.test_council_transcript`
"""
import asyncio
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from openai import AsyncOpenAI

from src.config import settings
from src.services.gmina_facts import SOLECTWA
from src.utils.logger import setup_logger

logger = setup_logger("CouncilTranscript")

# whisper-1 przyjmuje pliki do 25 MB. Przy 64 kbps mono to ~52 minuty, ale
# chunki tnę na 15 minut: krótszy plik to krótszy retry po błędzie sieci,
# a przy okazji mieszczą się w limicie nawet gdyby ktoś podał audio lepszej
# jakości. Granica wypada w losowym miejscu zdania — leczy to `prompt`
# z ogonem poprzedniego fragmentu (patrz `_whisper_prompt`).
CHUNK_SECONDS = 15 * 60

# Ile chunków leci równolegle. Sesja 3 h to 12 kawałków; szeregowo ~6 minut,
# równolegle ~1,5. Powyżej trójki OpenAI zaczyna zwracać 429 na tym koncie.
MAX_PARALLEL_CHUNKS = 3

# Whisper przyjmuje prompt do ~224 tokenów i traktuje go jako kontekst, nie
# polecenie. Wchodzą tu nazwy własne, których model nie zna: bez tego
# „Koszelewki" wychodzą jako „Koszelewski", a nazwisko wójta jako „Węgorzewski".
# Chunki lecą równolegle, więc każdy dostaje ten sam słownik i nic poza nim —
# doklejanie ogona poprzedniego fragmentu wymusiłoby przebieg szeregowy, a styk
# wypada w środku zdania raz na 15 minut i tak czy tak ginie w skrócie.
_GLOSSARY_PLACES = ", ".join(SOLECTWA[:12])
_GLOSSARY = (
    f"Sesja Rady Gminy Rybno. Wójt Tomasz Węgrzynowski, przewodniczący Piotr "
    f"Kornatowski, wiceprzewodniczący Grzegorz Januszewski. Miejscowości: "
    f"{_GLOSSARY_PLACES}. Uchwała, sołectwo, absolutorium, wotum zaufania, "
    f"fundusz sołecki, wieloletnia prognoza finansowa."
)

# yt-dlp na YouTube, stan na 6.08.2026. Klienty web/tv/mweb zwracają „The page
# needs to be reloaded" (YouTube wymusza SABR), ios żąda PO Tokena — zostaje
# android_vr. Gdy pobieranie przestanie działać, zacznij od tego ustawienia.
_YTDLP_ARGS = ("--extractor-args", "youtube:player_client=android_vr")

# Ostatnia deska ratunku. Ścieżka 106 kbps sypie 403 przy natywnym pobieraniu,
# a przez downloader ffmpeg schodzi — tyle że dławiona do ~20 kB/s, czyli
# godzina na nagranie, które natywnie idzie 25 sekund. Dlatego ffmpeg jest
# fallbackiem po błędzie, a nie ustawieniem domyślnym.
_YTDLP_FALLBACK_ARGS = ("--downloader", "ffmpeg")

# Audio mowy. 16 kHz mono to natywne wejście Whispera — wyższe parametry
# powiększają plik i nic nie wnoszą.
_AUDIO_ARGS = ("-ac", "1", "-ar", "16000", "-b:a", "64k")

# Najgorsza jakość, która wystarcza. YouTube dławi transfer do ~20 kB/s, więc
# o czasie pobierania decyduje wyłącznie rozmiar: dla sesji XXIII ścieżka 48 kbps
# waży 29 MB wobec 65 MB dla 106 kbps, a po konwersji do 16 kHz mono obie dają
# Whisperowi to samo. Przy trzygodzinnej sesji to różnica kwadransa.
_AUDIO_FORMAT = "bestaudio[abr<=64]/bestaudio"


class TranscriptionError(RuntimeError):
    """Nagranie nie dało się pobrać albo przepisać."""


@dataclass
class Segment:
    """Kawałek wypowiedzi ze znacznikiem czasu liczonym od początku nagrania."""

    start: float
    end: float
    text: str

    @property
    def stamp(self) -> str:
        """`01:23:45` — postać, w jakiej znacznik trafia do promptu i do UI."""
        total = int(self.start)
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


@dataclass
class Transcript:
    """Cała sesja: segmenty ze znacznikami + metryki do rachunku kosztów."""

    segments: List[Segment] = field(default_factory=list)
    duration_s: float = 0.0
    source_url: Optional[str] = None
    # Leniwie liczony indeks wyszukiwania (patrz `_search_index`). Poza
    # `asdict()` i porównaniami — to pamięć podręczna, nie dane transkryptu.
    _index_cache: Optional[Tuple] = field(default=None, repr=False, compare=False)

    @property
    def text(self) -> str:
        """Sam tekst, bez znaczników — do wyszukiwania i weryfikacji cytatów."""
        return " ".join(s.text for s in self.segments).strip()

    def stamped_text(self, every_s: int = 60) -> str:
        """
        Transkrypt dla modelu: `[00:12:00] ...`. Znacznik co `every_s`, a nie
        przy każdym segmencie — Whisper tnie mowę co kilka sekund, więc znacznik
        w każdej linii potroiłby liczbę tokenów i utopił treść w cyfrach.
        """
        out: list[str] = []
        next_stamp = 0.0
        for seg in self.segments:
            if seg.start >= next_stamp:
                out.append(f"\n[{seg.stamp}] ")
                next_stamp = seg.start + every_s
            out.append(seg.text.strip())
        return " ".join(out).strip()

    def _search_index(self) -> tuple:
        """
        Znormalizowany tekst całej sesji + mapa: gdzie w nim zaczyna się każdy segment.
        Liczony raz i trzymany, bo weryfikacja cytatów woła `locate` dla każdego punktu.
        """
        if self._index_cache is None:
            offsets: list = []
            parts: list = []
            position = 0
            for seg in self.segments:
                flat = normalize_quote(seg.text)
                if not flat:
                    continue
                offsets.append((position, seg))
                parts.append(flat)
                position += len(flat) + 1  # +1 za spację łączącą segmenty
            self._index_cache = (" ".join(parts), offsets)
        return self._index_cache

    def _segment_at(self, position: int) -> Optional[Segment]:
        """Segment, w którym wypada dany offset w sklejonym tekście sesji."""
        _, offsets = self._search_index()
        match = offsets[0][1] if offsets else None
        for start, segment in offsets:
            if start > position:
                break
            match = segment
        return match

    def locate(self, phrase: str, near_s: Optional[float] = None) -> Optional[Segment]:
        """
        Segment, w którym zaczyna się fraza — albo None, gdy w nagraniu jej nie ma.

        Szuka w tekście CAŁEJ sesji, nie segment po segmencie. Whisper tnie mowę
        co kilka sekund w losowym miejscu, więc zdanie „Za przyjęciem uchwały
        głosowało dwunastu radnych. Nikt nie był przeciw." potrafi leżeć w dwóch
        segmentach — przy szukaniu po jednym wychodziło, że to zmyślony cytat.
        Na pilotażowej sesji XXIII taki fałszywy alarm dotknął 3 z 4 cytatów.

        **`near_s` rozstrzyga, które trafienie jest tym właściwym.** Formuły
        z obrad powtarzają się dosłownie: „Za podjęciem uchwały głosowało 12
        radnych" pada przy każdym głosowaniu. Branie pierwszego trafienia
        przypinało punkt do cudzej sprawy — 9.08.2026 dwa różne punkty sesji XXIII
        dostały ten sam znacznik 00:57:35, a punkt o działce w Koszelewach
        (realnie ~01:00:19) wskazywał głosowanie nad dotacją konserwatorską.
        Skoro znacznik ma być dowodem („kliknij i posłuchaj"), musi trafiać
        w tę sprawę, o której mowa.
        """
        needle = normalize_quote(phrase)
        if not needle:
            return None
        haystack, _ = self._search_index()

        positions: List[int] = []
        at = haystack.find(needle)
        while at >= 0:
            positions.append(at)
            at = haystack.find(needle, at + 1)
        if not positions:
            return None

        candidates = [self._segment_at(p) for p in positions]
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            return None
        if near_s is None or len(candidates) == 1:
            return candidates[0]
        return min(candidates, key=lambda seg: abs(seg.start - near_s))

    def window(self, center_s: float, before_s: float = 300, after_s: float = 300) -> str:
        """
        Fragment nagrania wokół podanej sekundy — materiał do sprawdzenia,
        czy opis punktu ma pokrycie w obradach.

        Okno jest szerokie i niesymetrycznie użyteczne z premedytacją: znacznik
        punktu bywa przesunięty na miejsce cytatu (`verify_against_transcript`
        prostuje go do sekundy, w której padły cytowane słowa), a cytatem jest
        zwykle ogłoszenie wyniku głosowania — czyli KONIEC sprawy. Sama dyskusja,
        w której padają fakty z opisu, leży wtedy przed znacznikiem.
        """
        start, end = center_s - before_s, center_s + after_s
        return " ".join(
            seg.text.strip() for seg in self.segments
            if seg.end >= start and seg.start <= end
        ).strip()

    @property
    def whisper_cost_usd(self) -> float:
        """whisper-1: $0,006 za minutę, naliczane co sekundę."""
        return round(self.duration_s / 60 * 0.006, 4)


def normalize_quote(text: str) -> str:
    """
    Tekst do porównywania cytatów: bez interpunkcji, wielkości liter i podwójnych
    spacji. Whisper stawia przecinki na wyczucie, więc cytat różniący się samą
    interpunkcją to wciąż ten sam cytat — a różniący się słowem to już nie.
    """
    lowered = (text or "").lower().replace(" ", " ")
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _run(cmd: Sequence[str], what: str) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-500:]
        raise TranscriptionError(f"{what} nie powiodło się: {tail}")
    return result


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise TranscriptionError(
            f"Brak `{name}` w PATH. Wymagane: yt-dlp (pip) i ffmpeg (brew install ffmpeg)."
        )
    return path


def probe_duration(audio_path: Path) -> float:
    """Długość pliku w sekundach — podstawa rachunku kosztów i podziału na chunki."""
    result = _run(
        [
            _tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(audio_path),
        ],
        "Odczyt długości audio",
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def video_metadata(video_url: str) -> dict:
    """
    Tytuł, długość, data publikacji i stan transmisji — bez pobierania strumienia.

    **`--ignore-no-formats-error` jest tu konieczne, nie kosmetyczne.** Gmina
    wystawia w galerii adres YouTube ZANIM sesja się zacznie: 26.08.2026 wpis
    „XXIV Sesja … z dnia 27.08.2026" prowadził do zaplanowanej transmisji, którą
    yt-dlp kwitował błędem („This live event will begin in 17 hours") i kończył
    kodem ≠ 0. Dla `council_job` wyglądało to jak awaria nagrania — sesja szła
    w `error` i traciła próbę, choć jedyną winą było to, że obrady jeszcze nie
    trwały. Z tą flagą brak ścieżek audio jest ostrzeżeniem, a `live_status`
    wraca normalnie i wołający ma czym odróżnić „jeszcze nie ma czego pobierać"
    od „nagranie zepsute".

    `live_status`: `is_upcoming` (zapowiedź), `is_live` (trwa), `post_live`
    (skończyła się, VOD dopiero się przetwarza), `was_live`, `not_live`.
    `release_at` niesie zapowiedzianą godzinę startu (UTC) — dla zapowiedzi
    jest to jedyna informacja o tym, kiedy wracać.
    """
    result = _run(
        [
            _tool("yt-dlp"), *_YTDLP_ARGS[:2], "--skip-download",
            "--ignore-no-formats-error",
            "--print", "%(title)s\t%(duration)s\t%(upload_date)s\t%(live_status)s\t%(release_timestamp)s",
            video_url,
        ],
        "Odczyt metadanych nagrania",
    )
    line = [ln for ln in result.stdout.splitlines() if "\t" in ln]
    if not line:
        raise TranscriptionError(f"Nagranie bez metadanych: {video_url}")
    parts = (line[-1].split("\t") + ["", "", "", "", ""])[:5]
    title, duration, upload_date, live_status, release_ts = parts

    def _number(raw: str) -> Optional[float]:
        raw = raw.strip()
        return float(raw) if raw not in ("", "NA", "None") else None

    release_epoch = _number(release_ts)
    return {
        "title": title.strip(),
        "duration_s": _number(duration) or 0.0,
        "upload_date": upload_date.strip(),
        "live_status": live_status.strip() or "not_live",
        "blocked": _access_blocked(result.stderr or ""),
        "release_at": (
            datetime.fromtimestamp(release_epoch, tz=timezone.utc)
            if release_epoch else None
        ),
    }


# Stany, w których nagrania nie ma jeszcze czego pobierać. `post_live` NIE jest
# na tej liście świadomie: transmisja się skończyła, VOD bywa gotowy w kilka
# minut, a cała wartość skrótu leży w tym, że powstaje tego samego dnia.
LIVE_NOT_READY = ("is_upcoming", "is_live")

# Czym YouTube kwituje odmowę dostępu. Zdanie przychodzi z krzywym apostrofem
# (U+2019), więc dopasowanie idzie po fragmencie bez niego.
_BLOCKED_MARKERS = ("Sign in to confirm", "not a bot", "age-restricted", "Private video")


def _access_blocked(stderr: str) -> bool:
    """Czy YouTube odmówił dostępu temu adresowi IP, zamiast zwrócić nagranie."""
    return any(marker in stderr for marker in _BLOCKED_MARKERS)


def not_ready_reason(meta: dict) -> Optional[str]:
    """
    Czemu nagrania nie da się jeszcze przepisać — albo None, gdy da się.

    ⚠️ **Brak długości to osobny przypadek i nie wolno go mylić z awarią.**
    27.08.2026 job wypalił próbę na sesji XXIV, bo z IP serwera YouTube nie
    oddaje ani metadanych, ani ścieżek („Sign in to confirm you're not a bot" —
    Hetzner jest oflagowany jako datacenter). `live_status` wracał wtedy jako
    `NA`, czyli poza `LIVE_NOT_READY`, więc bramka przepuszczała blokadę jak
    gotowe nagranie i dopiero `download_audio` się wywracał — po podbiciu próby.
    Nagranie gotowe do pobrania ZAWSZE ma długość; jej brak znaczy, że yt-dlp
    nie dostał ścieżek, a to nigdy nie jest wina nagrania.
    """
    status = meta.get("live_status")
    if status == "is_live":
        return "transmisja trwa — wracamy po zakończeniu obrad"
    if status == "is_upcoming":
        when = meta.get("release_at")
        stamp = when.astimezone().strftime("%d.%m.%Y %H:%M") if when else "termin nieznany"
        return f"transmisja zapowiedziana na {stamp} — jeszcze się nie zaczęła"
    if not meta.get("duration_s"):
        if meta.get("blocked"):
            return (
                "YouTube nie wpuszcza tego adresu IP (bot-check) — nagrania nie ma "
                "jak pobrać z serwera; potrzebne proxy"
            )
        return "nagranie bez ścieżek audio — VOD jeszcze się przetwarza"
    return None


def download_audio(video_url: str, dest_dir: Path, name: str = "session") -> Path:
    """
    Nagranie → jeden plik mp3 16 kHz mono. Zwraca ścieżkę; plik potrafi mieć
    kilkadziesiąt MB, więc wołający sprząta katalog po sobie.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{name}.mp3"
    if target.exists():
        logger.info("Audio już pobrane: %s", target)
        return target

    def attempt(extra: Sequence[str], what: str) -> None:
        _run(
            [
                _tool("yt-dlp"), *_YTDLP_ARGS, *extra, "-f", _AUDIO_FORMAT,
                "-x", "--audio-format", "mp3",
                "--postprocessor-args", f"ExtractAudio:{' '.join(_AUDIO_ARGS)}",
                "-o", str(dest_dir / f"{name}.%(ext)s"), video_url,
            ],
            what,
        )

    logger.info("Pobieram audio: %s", video_url)
    try:
        attempt((), "Pobranie audio")
    except TranscriptionError as exc:
        logger.warning("Pobieranie natywne nie wyszło (%s) — próbuję przez ffmpeg", exc)
        for leftover in dest_dir.glob(f"{name}.*.part"):
            leftover.unlink(missing_ok=True)
        attempt(_YTDLP_FALLBACK_ARGS, "Pobranie audio (fallback ffmpeg)")
    if not target.exists():
        raise TranscriptionError(f"yt-dlp nie zostawił pliku {target}")
    logger.info("Audio gotowe: %s (%.1f MB)", target, target.stat().st_size / 1e6)
    return target


def split_audio(audio_path: Path, chunk_s: int = CHUNK_SECONDS) -> list[tuple[Path, float]]:
    """
    Dzieli audio na kawałki mieszczące się w limicie Whispera.
    Zwraca pary (plik, przesunięcie w sekundach) — przesunięcie jest tym, co
    zamienia lokalny znacznik chunka na znacznik całej sesji.
    """
    duration = probe_duration(audio_path)
    if duration <= chunk_s:
        return [(audio_path, 0.0)]

    parts: list[tuple[Path, float]] = []
    count = math.ceil(duration / chunk_s)
    logger.info("Dzielę %.0f min na %d części", duration / 60, count)
    for index in range(count):
        offset = index * chunk_s
        part = audio_path.with_name(f"{audio_path.stem}_part{index:02d}.mp3")
        if not part.exists():
            _run(
                [
                    _tool("ffmpeg"), "-v", "error", "-y",
                    "-ss", str(offset), "-t", str(chunk_s),
                    "-i", str(audio_path), "-c", "copy", str(part),
                ],
                f"Podział audio (część {index + 1})",
            )
        parts.append((part, float(offset)))
    return parts


async def _transcribe_chunk(client: AsyncOpenAI, part: Path, offset: float) -> list[Segment]:
    with part.open("rb") as handle:
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=handle,
            response_format="verbose_json",
            language="pl",
            prompt=_GLOSSARY,
        )
    segments = getattr(response, "segments", None) or []
    if not segments:
        # Fragment bez mowy (cisza przed otwarciem obrad) — nie jest błędem.
        text = (getattr(response, "text", "") or "").strip()
        return [Segment(offset, offset, text)] if text else []
    return [
        Segment(
            start=offset + float(seg.start),
            end=offset + float(seg.end),
            text=(seg.text or "").strip(),
        )
        for seg in segments
        if (seg.text or "").strip()
    ]


async def transcribe_audio(audio_path: Path, source_url: Optional[str] = None) -> Transcript:
    """
    Plik audio → transkrypt ze znacznikami czasu liczonymi od początku sesji.
    """
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    parts = split_audio(audio_path)
    duration = probe_duration(audio_path)
    semaphore = asyncio.Semaphore(MAX_PARALLEL_CHUNKS)

    async def worker(index: int, part: Path, offset: float) -> list[Segment]:
        async with semaphore:
            logger.info("Transkrybuję część %d/%d (od %.0f min)", index + 1, len(parts), offset / 60)
            return await _transcribe_chunk(client, part, offset)

    results = await asyncio.gather(
        *(worker(i, part, offset) for i, (part, offset) in enumerate(parts))
    )

    segments = [seg for chunk in results for seg in chunk]
    segments.sort(key=lambda s: s.start)
    transcript = Transcript(segments=segments, duration_s=duration, source_url=source_url)
    logger.info(
        "Transkrypt gotowy: %d segmentów, %d znaków, koszt whisper ~$%.3f",
        len(segments), len(transcript.text), transcript.whisper_cost_usd,
    )
    return transcript


async def transcribe_session(video_url: str, work_dir: Path, name: str = "session") -> Transcript:
    """Pełna droga: URL nagrania → transkrypt. Audio zostaje w `work_dir`."""
    audio = download_audio(video_url, work_dir, name=name)
    return await transcribe_audio(audio, source_url=video_url)
