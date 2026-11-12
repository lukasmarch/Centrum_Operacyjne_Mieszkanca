"""Grzeczność wobec serwerów gminy: wyłącznik, tempo, limity, stop po odmowie.

Historia: dostawca BIP (E-LINE) blokował adres serwera trzy razy (24.08,
21.10, ok. 6–10.11.2026 — „wykrycie nietypowej aktywności”). Po drugiej
blokadzie (25.10) reguły tempa trafiły w jedno miejsce, ale stan żył w PAMIĘCI
procesu: każdy deploy zerował karencję po odmowie, logi żądań ginęły razem
z kontenerem, a liczba żądań nie miała sufitu (1.11 poszło ~425 w dwóch
seriach). Od 12.11.2026 stan jest w BAZIE i przeżywa restart.

Wszystko dzieje się w transporcie httpx (`transport()`), nie w hakach: hak nie
widzi timeoutu ani zerwanego połączenia, a to właśnie wtedy kod ponawiał
żądania do przeciążonego serwera (6.11). Każdy klient pytający `*.gminarybno.pl`
MUSI być zbudowany z `transport=polite.transport()`.

Reguły dla hostów `*.gminarybno.pl` (stan per host, tempo wspólne dla domeny):
1. **Wyłącznik** (`polite_hosts.hold`): host wstrzymany ręcznie nie dostaje
   ŻADNEGO żądania, także próbnego. Włącza i wyłącza człowiek:
   `python -m scripts.bip_access --release` / `--hold "powód"`.
2. **Tempo**: ≥ `MIN_INTERVAL_S` między żądaniami na całą domenę, bezpiecznie
   dla wątków (scheduler odpala joby przez `asyncio.run` w osobnych pętlach).
3. **Limity**: najwyżej `HOURLY_LIMIT` żądań na godzinę i `DAILY_LIMIT` na dobę
   (okna kroczące, liczone z dziennika w bazie). Po wyczerpaniu: `BudgetExhausted`.
4. **Odmowa** (2× 403 pod rząd albo 429) eskaluje: 12 h → 3 doby → wyłącznik.
   Pamięć eskalacji: `REFUSAL_MEMORY` od ostatniej odmowy.
5. **Brak odpowiedzi** (timeout, zerwane połączenie, 5xx): host zamknięty na
   `UNAVAILABLE_COOLDOWN`. Bez ponawiania — przeciążonemu serwerowi nie pomaga
   druga próba, a nasz przebieg kończy się na pierwszym niepowodzeniu.
6. **Dziennik**: każde WYSŁANE żądanie = wiersz w `polite_requests` (90 dni,
   `retention_job`). Z niego liczą się limity i z niego odpowiadamy dostawcy.
7. **Przedstawienie się**: `RYBNOLIVE_UA`, podstawiany niezależnie od klienta.

⚠️ Stan nieczytelny (baza nie odpowiada) = żądanie NIE wychodzi. Wolimy
przegapić przebieg niż wysłać ruch, którego nie umiemy policzyć.
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import httpx

from src.utils.logger import setup_logger

logger = setup_logger("PoliteHttp")

# Deklaracja z pism do dostawcy (9.10, 25.10, 12.11.2026) — ma być prawdą.
RYBNOLIVE_UA = "RybnoLive/1.0 (+https://rybnolive.pl; biuro@lumargo.pl)"

POLITE_DOMAIN = "gminarybno.pl"

# Dostawca prosi o ≥ 1 s; 1,5 s zostawia zapas na jitter i czas odpowiedzi.
MIN_INTERVAL_S = 1.5

# Sufity wolumenu (pismo z 12.11.2026). Typowa doba to ~5 żądań, niedziela
# z wiedzą stałą i aktami do ~100 — sufit ma być daleko nad normą, a blisko
# tego, co dostawca uzna jeszcze za zwykłego czytelnika.
HOURLY_LIMIT = 60
DAILY_LIMIT = 150

# Eskalacja po odmowie: pierwsza 12 h, druga 3 doby, trzecia = wyłącznik.
REFUSAL_COOLDOWNS = (timedelta(hours=12), timedelta(days=3))
REFUSAL_MEMORY = timedelta(days=30)
REFUSALS_IN_ROW = 2  # pojedyncze 403 zdarza się na jednym pliku PDF

# Serwer nie odpowiada — godzina przerwy wystarcza, by przebieg się skończył
# (aktualności chodzą 6:00 i 13:00), a nie blokuje następnego terminu.
UNAVAILABLE_COOLDOWN = timedelta(hours=1)

# Nagłówki zwykłego, uczciwego klienta.
BIP_HEADERS = {
    "User-Agent": RYBNOLIVE_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9",
}


class HostBlocked(Exception):
    """Żądanie NIE zostało wysłane: host zamknięty (odmowa, brak odpowiedzi)."""


class HostHeld(HostBlocked):
    """Host wstrzymany ręcznie (wyłącznik) — stan zamierzony, nie awaria."""


class BudgetExhausted(HostBlocked):
    """Wyczerpany limit godzinowy albo dobowy — reszta pracy w następnym przebiegu."""


# --------------------------------------------------------------------------- stan

@dataclass(frozen=True)
class HostState:
    hold: bool = False
    hold_reason: Optional[str] = None
    blocked_until: Optional[datetime] = None
    block_reason: Optional[str] = None
    refusal_level: int = 0
    last_refusal_at: Optional[datetime] = None


def _now() -> datetime:
    """Naiwny UTC jak w całym projekcie. Funkcja, żeby test mógł przesunąć zegar."""
    return datetime.utcnow()


class MemoryStore:
    """Stan w pamięci — dla testów (CI nie ma tabel polite_*)."""

    def __init__(self) -> None:
        self.states: Dict[str, HostState] = {}
        self.requests: List[Tuple[datetime, str, str, str, Optional[int], str]] = []

    def state(self, host: str) -> HostState:
        return self.states.get(host, HostState())

    def save(self, host: str, state: HostState) -> None:
        self.states[host] = state

    def count_since(self, host: str, since: datetime) -> int:
        return sum(1 for r in self.requests if r[1] == host and r[0] >= since)

    def log(self, host: str, method: str, path: str, status: Optional[int],
            outcome: str, duration_ms: int) -> None:
        self.requests.append((_now(), host, method, path, status, outcome))


class DbStore:
    """Stan w PostgreSQL (`polite_hosts`, `polite_requests`), silnik synchroniczny
    jak `scheduler/job_runs` — transport działa w pętlach różnych jobów."""

    def __init__(self) -> None:
        self._engine = None

    def _conn(self):
        if self._engine is None:
            from sqlalchemy import create_engine
            from src.config import settings
            url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
            self._engine = create_engine(url, pool_size=1, max_overflow=2, pool_pre_ping=True)
        return self._engine.begin()

    def state(self, host: str) -> HostState:
        from sqlalchemy import text
        with self._conn() as conn:
            row = conn.execute(text(
                "SELECT hold, hold_reason, blocked_until, block_reason, refusal_level, "
                "last_refusal_at FROM polite_hosts WHERE host = :h"
            ), {"h": host}).first()
        if row is None:
            return HostState()
        return HostState(bool(row[0]), row[1], row[2], row[3], int(row[4] or 0), row[5])

    def save(self, host: str, state: HostState) -> None:
        from sqlalchemy import text
        with self._conn() as conn:
            conn.execute(text("""
                INSERT INTO polite_hosts (host, hold, hold_reason, blocked_until, block_reason,
                                          refusal_level, last_refusal_at, updated_at)
                VALUES (:h, :hold, :hr, :bu, :br, :lvl, :lra, :now)
                ON CONFLICT (host) DO UPDATE SET
                    hold = EXCLUDED.hold, hold_reason = EXCLUDED.hold_reason,
                    blocked_until = EXCLUDED.blocked_until, block_reason = EXCLUDED.block_reason,
                    refusal_level = EXCLUDED.refusal_level,
                    last_refusal_at = EXCLUDED.last_refusal_at, updated_at = EXCLUDED.updated_at
            """), {
                "h": host, "hold": state.hold, "hr": (state.hold_reason or "")[:300] or None,
                "bu": state.blocked_until, "br": (state.block_reason or "")[:300] or None,
                "lvl": state.refusal_level, "lra": state.last_refusal_at, "now": _now(),
            })

    def count_since(self, host: str, since: datetime) -> int:
        from sqlalchemy import text
        with self._conn() as conn:
            return int(conn.execute(text(
                "SELECT count(*) FROM polite_requests WHERE host = :h AND at >= :s"
            ), {"h": host, "s": since}).scalar() or 0)

    def log(self, host: str, method: str, path: str, status: Optional[int],
            outcome: str, duration_ms: int) -> None:
        from sqlalchemy import text
        with self._conn() as conn:
            conn.execute(text(
                "INSERT INTO polite_requests (at, host, method, path, status, outcome, duration_ms) "
                "VALUES (:at, :h, :m, :p, :s, :o, :d)"
            ), {"at": _now(), "h": host, "m": method[:8], "p": path[:500], "s": status,
                "o": outcome, "d": duration_ms})


_store = None


def get_store():
    global _store
    if _store is None:
        _store = DbStore()
    return _store


def set_store(store) -> None:
    global _store
    _store = store


# --------------------------------------------------------------------------- tempo

_lock = threading.Lock()
_next_slot: float = 0.0
_refusals_in_row: Dict[str, int] = {}


def _is_polite(host: str) -> bool:
    return host == POLITE_DOMAIN or host.endswith("." + POLITE_DOMAIN)


def polite_url(url: str) -> bool:
    """Czy adres podlega tym regułom (scrapery: bez ponawiania dla takich adresów)."""
    try:
        return _is_polite(httpx.URL(url).host)
    except Exception:  # noqa: BLE001
        return False


def _reserve_slot() -> float:
    """Ile sekund czekać, żeby zachować odstęp od poprzedniego żądania."""
    global _next_slot
    with _lock:
        now = time.monotonic()
        slot = max(now, _next_slot)
        _next_slot = slot + MIN_INTERVAL_S
        return slot - now


def reset(store=None) -> None:
    """Tylko dla testów: czysty stan w pamięci."""
    global _next_slot
    with _lock:
        _next_slot = 0.0
        _refusals_in_row.clear()
    set_store(store or MemoryStore())


# --------------------------------------------------------------------------- reguły

def closed_reason(host: str, store=None) -> Optional[str]:
    """Dlaczego host jest zamknięty (None = otwarty). Rzuca przy nieczytelnym stanie."""
    store = store or get_store()
    st = store.state(host)
    now = _now()
    if st.hold:
        return f"wstrzymany ręcznie: {st.hold_reason or 'bez powodu'}"
    if st.blocked_until and st.blocked_until > now:
        return f"zamknięty do {st.blocked_until:%Y-%m-%d %H:%M} UTC ({st.block_reason or '—'})"
    return None


def is_blocked(host: str) -> bool:
    try:
        return closed_reason(host) is not None
    except Exception:  # noqa: BLE001
        return True


def _gate(store, host: str) -> None:
    try:
        st = store.state(host)
        now = _now()
        if st.hold:
            raise HostHeld(f"{host} wstrzymany ręcznie ({st.hold_reason or 'bez powodu'}) — żądanie nie wyszło")
        if st.blocked_until and st.blocked_until > now:
            raise HostBlocked(
                f"{host} zamknięty do {st.blocked_until:%Y-%m-%d %H:%M} UTC "
                f"({st.block_reason or '—'}) — żądanie nie wyszło"
            )
        hour = store.count_since(host, now - timedelta(hours=1))
        if hour >= HOURLY_LIMIT:
            raise BudgetExhausted(f"{host}: limit {HOURLY_LIMIT} żądań/h wyczerpany ({hour})")
        day = store.count_since(host, now - timedelta(days=1))
        if day >= DAILY_LIMIT:
            raise BudgetExhausted(f"{host}: limit {DAILY_LIMIT} żądań/dobę wyczerpany ({day})")
    except HostBlocked:
        raise
    except Exception as e:  # noqa: BLE001 — stan nieczytelny: nie wysyłamy
        raise HostBlocked(f"{host}: stan dostępu nieczytelny ({type(e).__name__}: {e}) — żądanie nie wyszło") from e


def _close_unavailable(store, host: str, why: str) -> None:
    try:
        st = store.state(host)
        until = _now() + UNAVAILABLE_COOLDOWN
        if st.blocked_until and st.blocked_until > until:
            return
        store.save(host, replace(st, blocked_until=until, block_reason=f"brak odpowiedzi: {why}"))
        logger.error(f"{host}: {why} — bez ponawiania, przerwa do {until:%H:%M} UTC")
    except Exception as e:  # noqa: BLE001
        logger.error(f"{host}: nie zapisałem przerwy po braku odpowiedzi: {e}")


def _register_refusal(store, host: str, status: int, url: str) -> None:
    """Odmowa: eskalacja 12 h → 3 doby → wyłącznik."""
    st = store.state(host)
    now = _now()
    level = st.refusal_level
    if st.last_refusal_at and now - st.last_refusal_at > REFUSAL_MEMORY:
        level = 0
    level += 1
    if level > len(REFUSAL_COOLDOWNS):
        reason = f"automatycznie: {level}. odmowa (HTTP {status}) w ciągu {REFUSAL_MEMORY.days} dni"
        store.save(host, replace(st, hold=True, hold_reason=reason, refusal_level=level,
                                 last_refusal_at=now, blocked_until=None, block_reason=None))
        logger.error(f"{host}: HTTP {status} — WYŁĄCZNIK ({reason}). Włączenie tylko ręczne. ({url})")
        return
    cooldown = REFUSAL_COOLDOWNS[level - 1]
    until = now + cooldown
    store.save(host, replace(st, refusal_level=level, last_refusal_at=now, blocked_until=until,
                             block_reason=f"odmowa HTTP {status}, poziom {level}"))
    logger.error(f"{host}: HTTP {status} — odmowa nr {level}, przerwa do {until:%Y-%m-%d %H:%M} UTC ({url})")


class PoliteTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if not _is_polite(host):
            return await self._inner.handle_async_request(request)

        store = get_store()
        _gate(store, host)  # przed czekaniem: wstrzymany host nie czeka 1,5 s na nic
        wait = _reserve_slot()
        if wait > 0:
            await asyncio.sleep(wait)
        _gate(store, host)  # po czekaniu: równoległy przebieg mógł zużyć limit

        request.headers["User-Agent"] = RYBNOLIVE_UA
        path = request.url.raw_path.decode("ascii", "replace")
        started = time.monotonic()
        try:
            response = await self._inner.handle_async_request(request)
        except httpx.TransportError as e:
            ms = int((time.monotonic() - started) * 1000)
            outcome = "timeout" if isinstance(e, httpx.TimeoutException) else "error"
            self._log(store, host, request.method, path, None, outcome, ms)
            _close_unavailable(store, host, f"{outcome} ({type(e).__name__})")
            raise
        ms = int((time.monotonic() - started) * 1000)
        status = response.status_code

        if status in (403, 429):
            outcome = "refused"
        elif status >= 500:
            outcome = "error"
        else:
            outcome = "ok"
        self._log(store, host, request.method, path, status, outcome, ms)

        if status in (403, 429):
            with _lock:
                _refusals_in_row[host] = _refusals_in_row.get(host, 0) + 1
                trip = status == 429 or _refusals_in_row[host] >= REFUSALS_IN_ROW
                if trip:
                    _refusals_in_row.pop(host, None)
            if trip:
                try:
                    _register_refusal(store, host, status, str(request.url))
                except Exception as e:  # noqa: BLE001
                    logger.error(f"{host}: nie zapisałem odmowy: {e}")
        else:
            with _lock:
                _refusals_in_row.pop(host, None)
            if status >= 500:
                _close_unavailable(store, host, f"HTTP {status}")
        return response

    @staticmethod
    def _log(store, host, method, path, status, outcome, ms) -> None:
        logger.info(f"{method} {host}{path} → {status if status is not None else outcome} ({ms} ms)")
        try:
            store.log(host, method, path, status, outcome, ms)
        except Exception as e:  # noqa: BLE001
            logger.error(f"polite_requests: zapis nieudany ({type(e).__name__}: {e})")

    async def aclose(self) -> None:
        await self._inner.aclose()


def transport(inner: Optional[httpx.AsyncBaseTransport] = None) -> PoliteTransport:
    """`transport=` do `httpx.AsyncClient(...)` — obowiązkowy dla *.gminarybno.pl."""
    return PoliteTransport(inner)


# --------------------------------------------------------------------------- obsługa ręczna

def hold(host: str, reason: str, store=None) -> None:
    store = store or get_store()
    store.save(host, replace(store.state(host), hold=True, hold_reason=reason))


def release(host: str, store=None) -> None:
    """Włączenie po zgodzie dostawcy: zdejmuje wyłącznik, przerwę i poziom eskalacji."""
    store = store or get_store()
    store.save(host, replace(store.state(host), hold=False, hold_reason=None,
                             blocked_until=None, block_reason=None, refusal_level=0))
