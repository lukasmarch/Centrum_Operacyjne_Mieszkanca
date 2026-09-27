"""
Odczyt pisma ze zdjęcia — dla ogłoszeń sołtysów.

Sołtys robi to, co robi na Facebooku: zdjęcie pisma i „wyślij". Model czyta
obraz i zwraca STRUKTURĘ (przedruk, podsumowanie, termin, wykryte dane
osobowe), a kod sprawdza to, co da się sprawdzić kodem — ta sama zasada co
`ground_categorization` i `event_extractor.ground_event`:

  * termin musi mieć ślad w przedruku; gdy model go nie ma albo zmyślił,
    kod czyta datę sam (`time_span.parse_date_span`);
  * numery, które na pewno są danymi osobowymi (PESEL, dowód osobisty),
    wycina regex — niezależnie od tego, czy model o nich pamiętał.

Wynik NIE idzie od razu na stronę: każde ogłoszenie przechodzi moderację,
a redakcja widzi obok przedruku oryginalne zdjęcie i listę wykrytych danych.
"""
from __future__ import annotations

import io
import os
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent, ModelRetry

from src.ai.article_processor import SourceText, _event_date_grounded
from src.config import settings
from src.services.time_span import parse_date_span, to_utc
from src.utils.logger import setup_logger

logger = setup_logger("ScanReader")

# gpt-4o, nie mini: przedruk pisma urzędowego jest tekstem, który publikujemy
# jako „oryginał" — pomyłka w dacie zebrania albo kwocie funduszu sołeckiego
# kosztuje więcej niż różnica w cenie (~$0,01 za stronę).
SCAN_MODEL = "openai:gpt-4o"

# Dłuższy bok zdjęcia po zmniejszeniu. Pismo A4 czyta się dobrze przy 2000 px,
# a zdjęcie z telefonu (4000+ px) to kilka razy więcej tokenów bez zysku.
MAX_IMAGE_SIDE = 2000

PERSONAL_DATA_MARK = "[dane osobowe]"

SCAN_PROMPT = """Czytasz zdjęcie pisma lub ogłoszenia, które sołtys z gminy Rybno \
(powiat działdowski) chce opublikować dla mieszkańców. Twoja praca ma dwie części.

1. PRZEDRUK (`transcript`): przepisz treść pisma dokładnie, słowo w słowo, \
z zachowaniem akapitów. Nie poprawiaj stylu, nie skracaj, nie dopisuj niczego, \
czego nie ma na zdjęciu, i NICZEGO NIE USUWAJ. Pomiń pieczęcie, podpisy \
odręczne i numery stron. Fragment nieczytelny oznacz [nieczytelne] i wpisz \
go do `illegible`.

2. DANE OSÓB PRYWATNYCH (`private_data`): wypisz KAŻDY fragment przedruku, \
który jest daną osoby prywatnej — dokładnie tak, jak stoi w przedruku, znak \
w znak (wytniemy go automatycznie). Osobny wpis na każdy fragment:
   - imię i nazwisko osoby prywatnej w tej formie, w jakiej pada \
(np. „Anny Kowalskiej", „Jan Kowalski") — mieszkańca, wnioskodawcy, osoby z listy
   - jej adres (np. „Żabiny 12", „ul. Leśna 4"), telefon, e-mail
   - numer PESEL, dowodu, rachunku prywatnego
   NIE wypisuj danych publicznych i urzędowych: wójta, sołtysa, radnych, \
pracowników urzędu podpisanych z funkcją, nazw i adresów instytucji, telefonów \
urzędów, rachunku gminy, nazw miejscowości.

3. OPIS dla mieszkańców (bez danych osób prywatnych):
   - `title`: krótki, rzeczowy tytuł (bez wykrzykników i emoji), do 90 znaków
   - `summary`: 1–3 zdania — co, kiedy, gdzie, kogo dotyczy. Wyłącznie fakty z pisma
   - `doc_type`: rodzaj pisma, np. „zawiadomienie o zebraniu wiejskim", \
„obwieszczenie", „komunikat", „zaproszenie"
   - `event_start` / `event_end`: termin zdarzenia, którego pismo dotyczy, \
w formacie RRRR-MM-DDTHH:MM (czas lokalny). Tylko jeśli data STOI w piśmie. \
Bez godziny w piśmie → godzina 00:00. Brak terminu → null
   - `event_place`: miejsce zdarzenia z pisma albo null

Jeśli na zdjęciu nie ma pisma ani ogłoszenia (np. krajobraz, zdjęcie osoby), \
ustaw `is_document` = false i zostaw pozostałe pola puste."""


class ScanReading(BaseModel):
    is_document: bool = True
    title: str = Field(default="", max_length=200)
    summary: str = ""
    transcript: str = ""
    doc_type: Optional[str] = None
    event_start: Optional[str] = None
    event_end: Optional[str] = None
    event_place: Optional[str] = None
    private_data: list["PrivateFragment"] = Field(default_factory=list)
    illegible: list[str] = Field(default_factory=list)


class PrivateFragment(BaseModel):
    text: str = Field(description="fragment dokładnie tak, jak stoi w przedruku")
    kind: str = Field(description="np. imię i nazwisko, adres, PESEL, telefon")


ScanReading.model_rebuild()


class ScanResult(BaseModel):
    """Odczyt po kontroli kodem — to zapisujemy w `solectwo_posts`."""
    is_document: bool
    title: str
    summary: str
    transcript: str
    doc_type: Optional[str]
    event_at: Optional[datetime]
    event_until: Optional[datetime]
    personal_data: list[str]
    illegible: list[str]


# Numery, które są danymi osobowymi bez względu na kontekst. Model ma je
# zastępować sam; regex jest siatką na wypadek, gdy zapomni.
_PESEL_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_ID_CARD_RE = re.compile(r"\b[A-Z]{3}\s?\d{6}\b")


def _exact_pattern(needle: str) -> re.Pattern:
    """Znak w znak. Odstępy dowolne (łamanie wiersza w przedruku), granice
    słowa po obu stronach — „Żabiny 12" nie może zjeść początku „Żabiny 120"."""
    body = r"\s+".join(re.escape(part) for part in needle.split())
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def _stem_pattern(needle: str) -> re.Pattern:
    """Po rdzeniach — druga próba, gdy model podał formę podstawową.

    Pomiar 27.09.2026: w dwóch przebiegach na trzy model wskazał „Anna
    Kowalska", a w piśmie stało „Anny Kowalskiej". Każde słowo traci do trzech
    liter końcówki (zostaje ≥ 3), liczby muszą się zgadzać dokładnie. Kolejność
    słów i ich sąsiedztwo zostają — dopasowanie dotyczy całej frazy, nie
    pojedynczego „Anna" gdziekolwiek w tekście.
    """
    parts = []
    for word in needle.split():
        if word.isdigit() or len(word) <= 3:
            parts.append(re.escape(word))
        else:
            parts.append(re.escape(word[:max(3, len(word) - 3)]) + r"\w*")
    body = r"[\s,.]+".join(parts)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def redact_fragments(
    texts: list[str], fragments: list["PrivateFragment"],
) -> tuple[list[str], list[str], list[str]]:
    """Wytnij fragmenty wskazane przez model — KOD wycina, nie model.

    Pomiar 27.09.2026 (`test_solectwa --live`): przy poleceniu „zastąp dane
    znacznikiem" model wpisał do raportu „imię i nazwisko, adres", a w przedruku
    zostawił „Anny Kowalskiej" i „Żabiny 12". Deklaracja wykonania nie jest
    wykonaniem — więc model tylko WSKAZUJE, a zastępuje kod i sprawdza wynik.

    Zwraca (teksty po wycięciu, rodzaje wyciętych danych, fragmenty, których
    nie znaleziono — te idą do redakcji jako ostrzeżenie).
    """
    kinds: list[str] = []
    missing: list[str] = []
    # Najdłuższe najpierw: „Anny Kowalskiej" przed „Kowalskiej"
    for fragment in sorted(fragments, key=lambda f: len(f.text or ""), reverse=True):
        needle = (fragment.text or "").strip()
        if len(needle) < 3:
            continue
        hit = False
        for pattern in (_exact_pattern(needle), _stem_pattern(needle)):
            for i, text in enumerate(texts):
                if pattern.search(text):
                    texts[i] = pattern.sub(PERSONAL_DATA_MARK, text)
                    hit = True
            if hit:
                break
        if hit:
            kinds.append(fragment.kind or "dane osobowe")
        else:
            missing.append(needle)
    return texts, kinds, missing


def redact(text: str) -> tuple[str, list[str]]:
    """Wytnij numery PESEL i dowodów. Zwraca (tekst, lista tego, co wycięto)."""
    found: list[str] = []
    if _PESEL_RE.search(text):
        found.append("numer PESEL (wycięty automatycznie)")
        text = _PESEL_RE.sub(PERSONAL_DATA_MARK, text)
    if _ID_CARD_RE.search(text):
        found.append("numer dowodu osobistego (wycięty automatycznie)")
        text = _ID_CARD_RE.sub(PERSONAL_DATA_MARK, text)
    return text, found


def _parse_local(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None


def ground_term(
    reading: ScanReading, now: datetime,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Termin w UTC — od modelu, jeśli ma ślad w przedruku, inaczej z tekstu.

    Kolejność „model, potem kod" jak w kategoryzacji: model rozumie „w najbliższą
    sobotę", kod nie. Ale datę bez pokrycia w tekście odrzucamy, a wtedy
    `parse_date_span` czyta ją z przedruku sam.
    """
    source = SourceText(title=reading.title, body=reading.transcript)
    start = _parse_local(reading.event_start)
    if start and _event_date_grounded(reading.event_start, source):
        end = _parse_local(reading.event_end)
        if end and end <= start:
            end = None
        return to_utc(start), (to_utc(end) if end else None)
    if start:
        logger.info(f"Termin {reading.event_start} bez śladu w przedruku — odrzucony")
    return parse_date_span(reading.transcript, now)


def shrink(image_bytes: bytes) -> tuple[bytes, str]:
    """Zdjęcie z telefonu → JPEG o dłuższym boku ≤ MAX_IMAGE_SIDE, z poprawną
    orientacją (EXIF) i bez metadanych (GPS z telefonu nie ma po co wychodzić
    poza serwer)."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
    return out.getvalue(), "image/jpeg"


def require_description(reading: ScanReading) -> ScanReading:
    """Pismo bez tytułu i podsumowania nie nadaje się do moderacji.

    27.09.2026, pierwsza wysyłka przez formularz: przedruk, termin i dane
    osobowe przyszły poprawnie, a `title` i `summary` — puste. Pola mają
    wartości domyślne (bo nie-pismo zostawia je puste), więc schemat tego
    nie łapał. Jedna prośba o uzupełnienie kosztuje mniej niż redakcja
    pisząca tytuł ręcznie.
    """
    if reading.is_document and (not reading.title.strip() or not reading.summary.strip()):
        raise ModelRetry("Pismo rozpoznane, ale `title` albo `summary` jest puste — uzupełnij oba pola.")
    return reading


class ScanReader:
    def __init__(self):
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        self.agent = Agent(
            SCAN_MODEL, output_type=ScanReading, system_prompt=SCAN_PROMPT, output_retries=2,
        )
        self.agent.output_validator(require_description)

    async def read(
        self,
        images: list[bytes],
        note: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> tuple[ScanResult, int, int]:
        """Odczytaj strony pisma. Zwraca (wynik, tokeny wejścia, tokeny wyjścia)."""
        now = now or datetime.utcnow()
        prompt: list = [
            f"Pismo ma {len(images)} "
            f"{'stronę' if len(images) == 1 else 'strony' if len(images) < 5 else 'stron'}, "
            "w kolejności jak niżej."
        ]
        if note:
            # Zdanie od sołtysa to KONTEKST, nie treść pisma — nie trafia do przedruku
            prompt.append(f"Dopisek sołtysa (kontekst, NIE przepisuj go do przedruku): {note}")
        for data in images:
            prompt.append(BinaryContent(data=data, media_type="image/jpeg"))

        result = await self.agent.run(prompt)
        reading: ScanReading = result.output
        usage = result.usage()

        (transcript, summary, title), kinds, missing = redact_fragments(
            [reading.transcript or "", reading.summary or "", reading.title or ""],
            reading.private_data,
        )
        transcript, found = redact(transcript)
        summary, found_summary = redact(summary)
        if missing:
            # Model wskazał coś, czego w przedruku nie ma — redakcja ma to zobaczyć
            kinds.append(
                "⚠️ nie znaleziono w przedruku, sprawdź ręcznie: " + "; ".join(missing)
            )
        event_at, event_until = ground_term(reading, now) if reading.is_document else (None, None)

        return ScanResult(
            is_document=reading.is_document,
            title=title.strip()[:200],
            summary=summary.strip(),
            transcript=transcript.strip(),
            doc_type=(reading.doc_type or None),
            event_at=event_at,
            event_until=event_until,
            personal_data=list(dict.fromkeys(kinds + found + found_summary)),
            illegible=reading.illegible,
        ), (usage.request_tokens or 0), (usage.response_tokens or 0)
