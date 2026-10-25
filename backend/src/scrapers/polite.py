"""Grzeczność wobec serwerów gminy: tempo, przedstawienie się, stop po odmowie.

Dostawca BIP (E-LINE) zdjął blokadę adresu serwera pod jednym warunkiem:
minimum 1 sekunda między zapytaniami na ich adres IP. Do 25.10.2026 nie
mieliśmy tej reguły w jednym miejscu — każdy scraper miał własną pauzę
(0,4 s, 0,5 s, 1 s), próbował od razu ponownie po 403 i podawał się za
przeglądarkę Chrome. Tu jest to JEDNO miejsce; działa jako hak httpx, więc
nie da się go ominąć nowym scraperem, który zapomni o pauzie.

Trzy reguły, wszystkie dla hostów `*.gminarybno.pl`:
- **Tempo**: wspólny dla całego procesu odstęp `MIN_INTERVAL_S` między
  zapytaniami na tę domenę (BIP i serwis gminy to ta sama infrastruktura).
  Rezerwacja slotu jest bezpieczna dla wątków — scheduler uruchamia joby
  przez `asyncio.run` w osobnych pętlach.
- **Przedstawienie się**: `RYBNOLIVE_UA` zamiast udawania przeglądarki.
  Nagłówek jest podstawiany w haku, więc obowiązuje także scrapery, które
  zbudowały klienta z innym `User-Agent`.
- **Stop po odmowie**: dwie odpowiedzi 403 pod rząd (albo jedno 429) = host
  jest zamknięty dla procesu na `BLOCK_COOLDOWN_S`; kolejne zapytania nie
  wychodzą z serwera, tylko rzucają `HostBlocked`. Wcześniej każda odmowa
  była ponawiana trzykrotnie, a niedzielne zadania wiedzy stałej sypały
  zapytaniami w zablokowany adres.
  ⚠️ Pojedyncze 403 NIE zamyka hosta: zdarza się na jednym pliku PDF.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Dict
from urllib.parse import urlparse

import httpx

from src.utils.logger import setup_logger

logger = setup_logger("PoliteHttp")

# Deklaracja z pisma do dostawcy (9.10.2026) — ma być prawdą.
RYBNOLIVE_UA = "RybnoLive/1.0 (+https://rybnolive.pl; biuro@lumargo.pl)"

# Dostawca prosi o ≥ 1 s; 1,5 s zostawia zapas na jitter i czas odpowiedzi.
MIN_INTERVAL_S = 1.5

# Po odmowie nie pytamy ponownie przez pół doby: jeden sondaż na przebieg
# poranny, nie lawina. Restart kontenera zeruje stan (kosztuje 2 zapytania).
BLOCK_COOLDOWN_S = 12 * 3600
REFUSALS_TO_BLOCK = 2

POLITE_DOMAIN = "gminarybno.pl"

# Nagłówki zwykłego, uczciwego klienta — bez `Upgrade-Insecure-Requests`
# i reszty, które miały udawać Chrome.
BIP_HEADERS = {
    "User-Agent": RYBNOLIVE_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9",
}


class HostBlocked(Exception):
    """Host odmówił dostępu — zapytanie nie zostało wysłane (albo dostało odmowę)."""


_lock = threading.Lock()
_next_slot: float = 0.0
_refusals: Dict[str, int] = {}
_blocked_until: Dict[str, float] = {}


def _is_polite(host: str) -> bool:
    return host == POLITE_DOMAIN or host.endswith("." + POLITE_DOMAIN)


def _reserve_slot() -> float:
    """Ile sekund czekać, żeby zachować odstęp od poprzedniego zapytania."""
    global _next_slot
    with _lock:
        now = time.monotonic()
        slot = max(now, _next_slot)
        _next_slot = slot + MIN_INTERVAL_S
        return slot - now


def is_blocked(host: str) -> bool:
    with _lock:
        return _blocked_until.get(host, 0.0) > time.monotonic()


def reset() -> None:
    """Tylko dla testów."""
    global _next_slot
    with _lock:
        _next_slot = 0.0
        _refusals.clear()
        _blocked_until.clear()


async def _before_request(request: httpx.Request) -> None:
    host = request.url.host
    if not _is_polite(host):
        return
    if is_blocked(host):
        raise HostBlocked(
            f"{host} odmówił dostępu — nie ponawiamy do końca okresu karencji"
        )
    request.headers["User-Agent"] = RYBNOLIVE_UA
    wait = _reserve_slot()
    if wait > 0:
        await asyncio.sleep(wait)


async def _after_response(response: httpx.Response) -> None:
    host = response.request.url.host
    if not _is_polite(host):
        return
    status = response.status_code
    # Ślad każdego zapytania: 21.10.2026 nie umieliśmy odtworzyć, co wysłaliśmy
    # przed ponowną blokadą — logi kontenera przepadły przy deployu.
    logger.info(f"{response.request.method} {host}{response.request.url.path} → {status}")
    with _lock:
        if status not in (403, 429):
            _refusals.pop(host, None)
            return
        _refusals[host] = _refusals.get(host, 0) + 1
        trip = status == 429 or _refusals[host] >= REFUSALS_TO_BLOCK
        if not trip:
            return
        cooldown = BLOCK_COOLDOWN_S
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            cooldown = min(max(int(retry_after), MIN_INTERVAL_S), BLOCK_COOLDOWN_S)
        _blocked_until[host] = time.monotonic() + cooldown
        _refusals.pop(host, None)
    logger.error(
        f"{host}: HTTP {status} — wstrzymuję zapytania na {cooldown // 60} min "
        f"(adres {response.request.url})"
    )


def hooks() -> dict:
    """`event_hooks` do `httpx.AsyncClient(...)`."""
    return {"request": [_before_request], "response": [_after_response]}
