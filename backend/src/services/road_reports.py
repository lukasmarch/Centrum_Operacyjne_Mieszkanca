"""
Zgłoszenia drogowe: kto decyduje, co trafia na pasek „Drogi” (2026-10-29).

**Skąd to.** Do 29.10 o pasku decydował model: Gemini czytał nasz materiał,
dokładał wyniki Google i sam wpisywał status, minuty i opis. Kod mógł tylko
zawetować. Pięć napraw od lipca (Hartowiec 29.07, konar 7.09, Syla 27.10,
ZDW 28.10, Syla 29.10) dokładało bramkę, żadna nie zmieniła tego, KTO decyduje:
- 28.10 Google podał listę utrudnień ZDW Olsztyn, która nie jest sprzątana —
  „DW 538 Rybno, zamknięcie 02.06–31.12.2025” wisi tam nadal;
- 29.10 ten sam remont z posta Syli z 22.10 („trwają prace”, bez terminu) stał
  żółty na DWÓCH trasach, z „+10 min”, których nie podało żadne źródło.

**Teraz model jest wyszukiwaczem kandydatów, a werdykt liczy kod.** Każde
utrudnienie, które przeszło bramki odpowiedzi modelu, dostaje wynik:

    zaufanie do źródła × świeżość (+ potwierdzenie z niezależnego źródła)

- `>= AUTO_SCORE` → pasek od razu (`auto`)
- `>= REVIEW_SCORE` → Telegram z przyciskami „Akceptuj / Usuń” (`pending`);
  bez decyzji NIE pokazujemy — mieszkaniec nie widzi niepotwierdzonego
- niżej → nigdzie

Wynik z Google bez oparcia w naszym feedzie ma zaufanie 0,4, więc nigdy nie
wchodzi na pasek sam — najwyżej trafia do redakcji.

**Czas to drugi weryfikator.** „Trwają prace” bez terminu nikt potem nie
odwołuje („remont zakończony” nie pojawia się w żadnym źródle — sprawdzone
29.10), więc wiarygodność takiego wpisu SPADA z wiekiem: po dwóch dniach
redakcja jest pytana, czy prace trwają, po pięciu wpis znika bez pytania.
Termin podany wprost w treści („od 3 do 20 listopada”) trzyma pełny wynik
do końca zakresu (bramkę terminu pilnuje `road_context._is_fresh_enough`).

Zatwierdzenie trwa `APPROVAL_HOURS` — potem wpis, jeśli model wciąż go zgłasza,
wraca do redakcji. „Usuń” wycisza ten sam klucz na `REJECT_DAYS`.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.schema import RoadReport
from src.services.alert_policy import _flat, places_in

# ------------------------------------------------------------------ trasy

# Kolejność = kolejność na stronie ruchu. Nazwy jak dotąd w `traffic_cache`
# („Rybno-Działdowo”) — front rozpoznaje trasę po rdzeniu nazwy celu.
ROUTES: tuple[tuple[str, str], ...] = (
    ("dzialdow", "Rybno-Działdowo"),
    ("lubaw", "Rybno-Lubawa"),
    ("ilaw", "Rybno-Iława"),
    ("olsztyn", "Rybno-Olsztyn"),
)
CALM_NOTE = "Ruch płynny, brak potwierdzonych utrudnień."


def canonical_route(name: Optional[str]) -> Optional[str]:
    """„Rybno -> Działdowo”, „Rybno–Działdowo (DW538)” → „Rybno-Działdowo”."""
    flat = _flat(name or "")
    for stem, canonical in ROUTES:
        if stem in flat:
            return canonical
    return None


# ------------------------------------------------------------------ wynik

# Zaufanie do nadawcy. Urząd, powiat, policja i spółka gminna ogłaszają
# roboty i zamknięcia z urzędu; profile lokalne przekazują dalej, często
# bez terminu; media regionalne piszą o całym regionie.
OFFICIAL_SOURCES: frozenset[str] = frozenset({
    "Gmina Rybno",
    "BIP Gminy Rybno",
    "Facebook - Rybno",
    "Facebook - ZakladGospodarkiKomunalnej",
    "Powiat Działdowski (RSS)",
    "KPP Działdowo (RSS)",
    "RybnoLive - Sołectwa",
})
REGIONAL_SOURCES: frozenset[str] = frozenset({
    "Facebook - Panorama Regionu",
    "Moje Działdowo",
    "Facebook - Gmina Działdowo",
})
TRUST_OFFICIAL = 1.0
TRUST_LOCAL = 0.8      # Syla, profile sołectw — główne źródło wiadomości o gminie
TRUST_REGIONAL = 0.6
TRUST_SEARCH = 0.4     # wynik Google bez oparcia w naszym feedzie

AUTO_SCORE = 0.8
REVIEW_SCORE = 0.35
CONFIRMATION_BONUS = 0.3

APPROVAL_HOURS = 72
REJECT_DAYS = 14
# Ile próśb o decyzję na jeden przebieg (6 przebiegów na dobę). Więcej nie
# przeczyta nikt, a nierozstrzygnięte i tak nie trafiają na pasek.
MAX_NOTIFY_PER_RUN = 3


def source_trust(source_name: Optional[str], origin: str) -> float:
    if origin == "search":
        return TRUST_SEARCH
    if source_name in OFFICIAL_SOURCES:
        return TRUST_OFFICIAL
    if source_name in REGIONAL_SOURCES:
        return TRUST_REGIONAL
    return TRUST_LOCAL


def freshness(kind: str, age_hours: float, has_term: bool) -> float:
    """
    Ile wpis jest wart z wiekiem. Termin z treści trzyma pełną wartość —
    to, czy termin jeszcze trwa, rozstrzygnęła bramka materiału.

    Zdarzenie chwilowe (konar, kolizja): pierwsza doba pełna, potem pół —
    a po dwóch dniach bramka materiału i tak je wycina.
    Roboty bez terminu: 2 dni pełne, do 4 dni 0,6 (Syla 0,48 → redakcja),
    potem 0,35 (Syla 0,28 → nigdzie; urząd 0,35 → jeszcze redakcja).
    """
    if has_term:
        return 1.0
    if kind == "incident":
        return 1.0 if age_hours <= 24 else 0.5
    days = age_hours / 24
    if days <= 2:
        return 1.0
    if days <= 4:
        return 0.6
    return 0.35


# ------------------------------------------------------------------ kandydaci

# Numer drogi WYŁĄCZNIE z oznaczeniem („DW 538”, „nr 541”, „1255N”). Goła liczba
# czterocyfrowa to najczęściej rok — „2026” połączyłby każde dwa opisy z datą.
_ROAD_NUMBER_RE = re.compile(
    r"\b(?:dw|dk|nr|s)\s?(\d{1,4})\b|\b(\d{3,4})\s?n\b"
)
# Nazwa gminy pada w prawie każdym opisie — nie odróżnia zdarzeń od siebie.
_GENERIC_PLACES = frozenset({"Rybno"})


def note_tokens(note: Optional[str]) -> frozenset[str]:
    """Numery dróg i wsie z opisu — tożsamość zdarzenia, gdy nie ma artykułu."""
    flat = _flat(note or "")
    numbers = {f"#{a or b}" for a, b in _ROAD_NUMBER_RE.findall(flat)}
    places = {p for p in places_in(note) if p not in _GENERIC_PLACES}
    return frozenset(numbers | places)


@dataclass
class Candidate:
    """Jedno utrudnienie z odpowiedzi modelu, po bramkach `traffic_service`."""
    route: str
    note: str
    origin: str                          # feed | search
    kind: str = "works"                  # works | incident
    article_id: Optional[int] = None
    source_name: Optional[str] = None
    published_at: Optional[datetime] = None
    has_term: bool = False
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        if self.article_id is not None:
            return f"{self.route}|a{self.article_id}"
        tokens = ",".join(sorted(note_tokens(self.note))) or _flat(self.note)[:80]
        return f"{self.route}|w:{tokens}"[:200]


def drop_multi_route(candidates: List[Candidate]) -> tuple[List[Candidate], List[Candidate]]:
    """
    Jedno zdarzenie = jedna trasa. Ten sam artykuł albo ten sam zestaw dróg
    i wsi przy dwóch trasach znaczy, że model nie wie, na której leży — wtedy
    nie ma go na żadnej. Reguła stała w prompcie od 7.09 i 29.10 model ją
    złamał (remont DW538 przy Działdowie i Lubawie); teraz pilnuje jej kod.
    """
    def identity(c: Candidate) -> str:
        if c.article_id is not None:
            return f"a{c.article_id}"
        return ",".join(sorted(note_tokens(c.note))) or _flat(c.note)

    routes: Dict[str, set] = {}
    for c in candidates:
        routes.setdefault(identity(c), set()).add(c.route)
    kept = [c for c in candidates if len(routes[identity(c)]) == 1]
    dropped = [c for c in candidates if len(routes[identity(c)]) > 1]
    return kept, dropped


def score_candidates(candidates: List[Candidate], now: datetime) -> List[Candidate]:
    """
    Wynik każdego kandydata. Wynik z Google, który dotyczy tej samej drogi albo
    wsi co wpis z feedu na tej samej trasie, nie jest osobnym zgłoszeniem —
    jest POTWIERDZENIEM tamtego (+`CONFIRMATION_BONUS`) i znika z listy.
    Tak samo dwa wpisy z feedu od RÓŻNYCH nadawców.
    """
    for c in candidates:
        trust = source_trust(c.source_name, c.origin)
        if c.origin == "search" or c.published_at is None:
            fresh, age_txt = 1.0, "wiek nieznany"
        else:
            age_h = max(0.0, (now - c.published_at).total_seconds() / 3600)
            fresh = freshness(c.kind, age_h, c.has_term)
            age_txt = "z terminem w treści" if c.has_term else f"{age_h / 24:.1f} dnia"
        c.score = round(trust * fresh, 2)
        c.reasons = [f"źródło {trust:.1f}", f"świeżość {fresh:.2f} ({age_txt})"]

    merged: List[Candidate] = []
    feed = [c for c in candidates if c.origin == "feed"]
    for c in candidates:
        tokens = note_tokens(c.note)
        confirming = [
            other for other in feed
            if other is not c and other.route == c.route
            and other.source_name != c.source_name
            and tokens & note_tokens(other.note)
        ]
        if c.origin == "search" and confirming:
            continue  # wchłonięty przez wpis z feedu
        if c.origin == "feed":
            confirmations = [
                other for other in candidates
                if other is not c and other.route == c.route
                and (other.origin == "search" or other.source_name != c.source_name)
                and tokens & note_tokens(other.note)
            ]
            if confirmations:
                c.score = round(min(1.0, c.score + CONFIRMATION_BONUS), 2)
                c.reasons.append("potwierdzone niezależnym źródłem")
        merged.append(c)
    return merged


def verdict(score: float) -> Optional[str]:
    if score >= AUTO_SCORE:
        return "auto"
    if score >= REVIEW_SCORE:
        return "pending"
    return None


# ------------------------------------------------------------------ baza

def is_visible(report: RoadReport, now: datetime) -> bool:
    if report.status == "auto":
        return True
    if report.status == "approved":
        return bool(report.approved_until and report.approved_until > now)
    return False


async def sync_reports(
    session: AsyncSession,
    candidates: Iterable[Candidate],
    now: datetime,
) -> List[RoadReport]:
    """
    Zapisuje wynik przebiegu. Zwraca zgłoszenia, które czekają na powiadomienie.

    - zgłoszenie odrzucone w ostatnich `REJECT_DAYS` dniach → cisza;
    - zatwierdzone i wciąż ważne → zostaje zatwierdzone, odświeża się tylko `last_seen_at`;
    - `auto`/`pending`, których model już nie zgłasza → `expired`.
      Zatwierdzone zostają do `approved_until` — redakcja potwierdziła, że trwa.
    """
    rows = (await session.execute(
        select(RoadReport).where(RoadReport.status.in_(("auto", "pending", "approved", "rejected")))
    )).scalars().all()
    by_key: Dict[str, RoadReport] = {}
    for row in rows:
        by_key.setdefault(row.report_key, row)
        if row.id > by_key[row.report_key].id:
            by_key[row.report_key] = row

    seen: set[int] = set()
    to_notify: List[RoadReport] = []
    for c in candidates:
        decision = verdict(c.score)
        existing = by_key.get(c.key)
        if existing is not None:
            if existing.status == "rejected":
                if existing.decided_at and existing.decided_at > now - timedelta(days=REJECT_DAYS):
                    continue
            elif existing.status == "approved" and is_visible(existing, now):
                existing.last_seen_at = now
                existing.note = c.note
                seen.add(existing.id)
                continue
        if decision is None:
            continue

        row = existing if existing is not None and existing.status in ("auto", "pending") else None
        if row is None:
            row = RoadReport(
                report_key=c.key, route=c.route, note=c.note, origin=c.origin,
                kind=c.kind, article_id=c.article_id, source_name=c.source_name,
                source_published_at=c.published_at, score=c.score, status=decision,
                first_seen_at=now, last_seen_at=now,
            )
            session.add(row)
        row.note = c.note
        row.score = c.score
        row.score_reason = "; ".join(c.reasons)[:300]
        row.last_seen_at = now
        if decision == "pending" and row.status != "pending":
            row.notified_at = None
        row.status = decision
        if decision == "pending" and not row.review_token:
            row.review_token = secrets.token_urlsafe(24)
        await session.flush()
        seen.add(row.id)
        if decision == "pending" and row.notified_at is None:
            to_notify.append(row)

    for row in rows:
        if row.id in seen:
            continue
        if row.status in ("auto", "pending"):
            row.status = "expired"
            row.review_token = None
        elif row.status == "approved" and not is_visible(row, now):
            row.status = "expired"

    return to_notify[:MAX_NOTIFY_PER_RUN]


async def visible_roads(session: AsyncSession, now: datetime) -> List[dict]:
    """
    Cztery trasy w kształcie `traffic_cache.data["roads"]`. Bez minut i czasów
    przejazdu (decyzja 29.10): Google Search nie zna ruchu, liczby były typowe
    albo zmyślone, a „+10 min” bez źródła czytało się jak pomiar.
    """
    rows = (await session.execute(
        select(RoadReport).where(RoadReport.status.in_(("auto", "approved")))
    )).scalars().all()
    best: Dict[str, RoadReport] = {}
    for row in rows:
        if not is_visible(row, now):
            continue
        if row.route not in best or row.score > best[row.route].score:
            best[row.route] = row

    roads = []
    for i, (_stem, route) in enumerate(ROUTES):
        row = best.get(route)
        roads.append({
            "id": str(i),
            "name": route,
            "status": "Utrudnienia" if row else "Płynnie",
            "delayMinutes": 0,
            "travelTime": "",
            "description": row.note if row else CALM_NOTE,
        })
    return roads


def apply_decision(row: RoadReport, action: str, now: datetime) -> None:
    """Akceptuj → pasek na `APPROVAL_HOURS`; Usuń → cisza na `REJECT_DAYS`."""
    row.decided_at = now
    if action == "approve":
        row.status = "approved"
        row.approved_until = now + timedelta(hours=APPROVAL_HOURS)
    else:
        row.status = "rejected"
    # Token jednorazowy, jak w akceptacji skrótów sesji
    row.review_token = None


# ------------------------------------------------------------------ redakcja

def review_url(row: RoadReport, action: str) -> str:
    from src.config import settings
    return f"{settings.API_URL}/api/roads/review/{row.review_token}?d={action}"


def notify_pending(row: RoadReport) -> bool:
    """
    Telegram: utrudnienie czeka na decyzję. Dwa przyciski-linki „Akceptuj”
    i „Usuń” — każdy otwiera stronę z jednym przyciskiem potwierdzenia (POST).
    Kliknięcie w czacie niczego jeszcze nie zmienia, z tego samego powodu co
    przy skrótach sesji: podglądy i skanery odwiedzają linki same.
    """
    from src.services.admin_telegram import send_admin_telegram
    from src.services.time_span import to_local

    if row.origin == "search":
        source = "wyłącznie wynik z Google (brak w naszym feedzie)"
    else:
        when = f", {to_local(row.source_published_at):%d.%m %H:%M}" if row.source_published_at else ""
        source = f"{row.source_name or 'feed'}{when}"
    lines = [
        "🚧 Drogi — utrudnienie do decyzji",
        "",
        f"Trasa: {row.route.replace('Rybno-', 'Rybno → ')}",
        f"„{row.note}”",
        "",
        f"Źródło: {source}",
        f"Wiarygodność {row.score:.2f} ({row.score_reason or '—'})",
        "",
        f"Bez decyzji NIE pokazujemy. Akceptacja = pasek na {APPROVAL_HOURS} h, "
        f"„Usuń” = cisza na {REJECT_DAYS} dni.",
    ]
    return send_admin_telegram(
        "\n".join(lines),
        buttons=[("✅ Akceptuj", review_url(row, "approve")), ("🗑 Usuń", review_url(row, "reject"))],
    )


async def refresh_current_cache(session: AsyncSession, now: datetime) -> None:
    """
    Po decyzji redakcji pasek ma się zmienić od razu, nie po następnym przebiegu.
    Podmienia trasy w najnowszym wpisie `traffic_cache`; `fetched_at` zostaje —
    to czas ODCZYTU źródeł, a decyzja nowego odczytu nie robi.
    """
    from src.database.schema import TrafficCache

    entry = (await session.execute(
        select(TrafficCache).order_by(TrafficCache.fetched_at.desc()).limit(1)
    )).scalars().first()
    if entry is None:
        return
    data = dict(entry.data or {})
    data["roads"] = await visible_roads(session, now)
    entry.data = data
