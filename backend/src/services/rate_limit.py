"""
Dzienny limit kosztownych tras publicznych (2026-10-11)

Audyt z 11.10.2026 znalazł dwie publiczne trasy, które za każde żądanie płacą
zewnętrznej usłudze, bez żadnej granicy: Whisper (`/api/voice/transcribe`)
i Zgłoszenia 24 (`POST /api/reports` — Gemini, Nominatim, mail do redakcji).
Pętla żądań mogła wypalić kredyty, a bez kredytów OpenAI staje cała kategoryzacja.

Licznik w PAMIĘCI, nie w bazie: backend ma jeden worker (`--workers 1`),
a restart zerujący liczniki to akceptowalna cena za brak migracji. Doba
LOKALNA (`time_span.local_now`), jak limit pytań do asystenta.

⚠️ Klucz to zahaszowane IP (`chat._hash_ip`), więc limit działa per osoba
WYŁĄCZNIE z `--forwarded-allow-ips` w `docker-compose.prod.yml`. Bez tej flagi
każdy ma IP Caddy i pierwsze `per_key` żądań gminy blokuje trasę wszystkim.
"""
from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import HTTPException, Request

from src.services.time_span import local_now
from src.utils.logger import setup_logger

logger = setup_logger("RateLimit")


def client_key(request: Request) -> str:
    """Zahaszowane IP klienta — ten sam klucz, co limit anonimowego czatu."""
    from src.api.endpoints.chat import _hash_ip
    return _hash_ip(request.client.host if request.client else "unknown")


class DailyLimit:
    """`per_key` żądań na klucz i `total` łącznie na dobę lokalną."""

    def __init__(self, name: str, per_key: int, total: int, message: str):
        self.name = name
        self.per_key = per_key
        self.total = total
        self.message = message
        self._day: Optional[date] = None
        self._counts: dict = defaultdict(int)
        self._total = 0

    def reset(self) -> None:
        self._day = None

    def used(self, key: str) -> int:
        self._roll()
        return self._counts[key]

    def _roll(self) -> None:
        today = local_now().date()
        if self._day != today:
            self._day = today
            self._counts.clear()
            self._total = 0

    def hit(self, key: str) -> None:
        """Zalicza żądanie albo rzuca 429. Woła się PO walidacji wejścia —
        odrzucone żądanie nie kosztuje nic, więc nie zjada limitu."""
        self._roll()
        if self._total >= self.total:
            logger.warning(f"{self.name}: dzienny sufit {self.total} wyczerpany")
            raise HTTPException(status_code=429, detail=self.message)
        if self._counts[key] >= self.per_key:
            raise HTTPException(status_code=429, detail=self.message)
        self._counts[key] += 1
        self._total += 1

    def count(self, key: str) -> None:
        """Zalicza zdarzenie BEZ odmowy — dla liczników porażek (nieudane
        logowanie), gdzie o blokadzie decyduje `used()` przed kolejną próbą."""
        self._roll()
        self._counts[key] += 1
        self._total += 1
