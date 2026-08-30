"""
Pomiar tego, co dzieje się NA STRONIE — `POST /api/events`.

Po co, skoro jest log Caddy: front to SPA bez react-routera. Nawigacja idzie przez
`history.pushState` w `frontend/App.tsx`, więc serwer widzi WYŁĄCZNIE pierwsze
żądanie HTML. Log nie powie, na którą sekcję ktoś wszedł, ile ich obejrzał ani gdzie
się zatrzymał — a do tego przewija się po 168 h (`roll_keep_for` w `Caddyfile`).

Trzy decyzje, które trzeba znać przed zmianą tego pliku:

  * **Zamknięta lista nazw zdarzeń** (`ALLOWED_EVENTS`). Endpoint jest publiczny
    i bez uwierzytelnienia — bez białej listy to otwarty zapis do naszej bazy.
    Nowe zdarzenie dodaje się TUTAJ, nie we froncie.
  * **IP i User-Agent nie trafiają do bazy.** Z nagłówka liczymy wyłącznie
    `device` (mobile/desktop) i zapominamy resztę. Dzięki temu tabela nie zawiera
    danych osobowych, a pomiar nie wymaga banera zgody.
  * **Cisza przy błędzie.** Odpowiedź to zawsze 204, także gdy wsad jest do
    wyrzucenia. Pomiar nie ma prawa popsuć strony ani zasypać konsoli
    przeglądarki czerwienią — a przeglądarka i tak nie czyta odpowiedzi,
    bo wysyła przez `navigator.sendBeacon`.

RODO: `session_id` i `user_id` → NULL po 90 dniach, wiersz kasowany po 180
(`scheduler/retention_job.py`).
"""
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from src.auth.dependencies import get_optional_user
from src.database.connection import async_session
from src.database.schema import SiteEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["analytics"])

# Zamknięta lista. Nazwa spoza niej jest po cichu wyrzucana.
ALLOWED_EVENTS = {
    "view",                 # wejście do sekcji (także pierwsze, po wejściu na stronę)
    "register_open",        # otwarty formularz rejestracji
    "register_done",        # konto założone (dopisywane po stronie serwera w auth/routes.py)
    "push_prompt",          # pokazana prośba o zgodę na powiadomienia
    "push_granted",
    "push_denied",
    "assistant_question",   # pytanie wysłane do agenta (bez treści — ta jest w chat_messages)
    "session_stamp_click",  # klik w znacznik czasu w skrócie sesji Rady
    "paywall_hit",          # zablokowana funkcja płatna
}

MAX_BATCH = 20

# Limit na IP, licznik w pamięci procesu. Świadomie nie w bazie: to zabezpieczenie
# przed przypadkową pętlą we froncie, nie przed wyspecjalizowanym napastnikiem,
# a zapis do bazy przy każdym sprawdzeniu kosztowałby więcej niż samo zdarzenie.
RATE_LIMIT_PER_MIN = 60
_hits: dict = defaultdict(list)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    window = _hits[ip] = [t for t in _hits[ip] if now - t < 60]
    if len(window) >= RATE_LIMIT_PER_MIN:
        return True
    window.append(now)
    # Bez tego słownik rośnie w nieskończoność przez cały czas życia procesu.
    if len(_hits) > 5000:
        for k in [k for k, v in _hits.items() if not v]:
            del _hits[k]
    return False


def _device(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    mobile = ("android", "iphone", "ipad", "ipod", "mobile", "opera mini")
    return "mobile" if any(m in ua for m in mobile) else "desktop"


def _host(referrer: Optional[str]) -> Optional[str]:
    """Z pełnego adresu odsyłającego zostaje sam host — reszta bywa danymi osobowymi."""
    if not referrer:
        return None
    try:
        return (urlparse(referrer).hostname or None)
    except ValueError:
        return None


class EventIn(BaseModel):
    event: str = Field(max_length=40)
    session_id: Optional[str] = Field(default=None, max_length=36)
    section: Optional[str] = Field(default=None, max_length=40)
    path: Optional[str] = Field(default=None, max_length=200)
    referrer: Optional[str] = Field(default=None, max_length=500)
    utm_source: Optional[str] = Field(default=None, max_length=60)
    utm_medium: Optional[str] = Field(default=None, max_length=60)
    utm_campaign: Optional[str] = Field(default=None, max_length=100)
    utm_content: Optional[str] = Field(default=None, max_length=100)
    meta: Optional[dict] = None


class EventBatch(BaseModel):
    events: List[EventIn] = Field(default_factory=list)


@router.post("", status_code=204)
async def collect(
    batch: EventBatch,
    request: Request,
    user=Depends(get_optional_user),
):
    """
    Przyjmij wsad zdarzeń z przeglądarki.

    Zawsze 204 — także gdy wsad jest pusty, za duży albo cały do wyrzucenia.
    Przeglądarka wysyła to przez `sendBeacon` i odpowiedzi nie czyta.
    """
    ip = (request.client.host if request.client else "?")
    if _rate_limited(ip):
        return Response(status_code=204)

    rows = []
    device = _device(request.headers.get("user-agent", ""))
    user_id = getattr(user, "id", None)
    now = datetime.utcnow()

    for e in batch.events[:MAX_BATCH]:
        if e.event not in ALLOWED_EVENTS:
            continue
        # `register_done` dopisuje serwer przy rejestracji — z przeglądarki
        # przyszłoby też od kogoś, kto konta nie założył.
        if e.event == "register_done":
            continue
        rows.append(SiteEvent(
            occurred_at=now,
            session_id=e.session_id,
            user_id=user_id,
            event=e.event,
            section=e.section,
            path=e.path,
            referrer_host=_host(e.referrer),
            utm_source=e.utm_source,
            utm_medium=e.utm_medium,
            utm_campaign=e.utm_campaign,
            utm_content=e.utm_content,
            device=device,
            meta=e.meta or None,
        ))

    if not rows:
        return Response(status_code=204)

    try:
        async with async_session() as session:
            session.add_all(rows)
            await session.commit()
    except Exception as exc:
        # Pomiar nie może przewrócić żądania. Zdarzenie przepada, strona działa.
        logger.warning("Nie zapisano zdarzeń pomiaru (%d szt.): %s", len(rows), exc)

    return Response(status_code=204)
