"""
Stan źródła: próba, sukces, błąd — i alarm tylko przy ZMIANIE stanu (2026-10-11)

Audyt 11.10.2026 (F-019, F-020): scraper z błędem zwracał pustą listę, job
zapisywał `last_scraped`, a BIP z blokadą 403 od lipca stał jako „zeskanowany
dziś”. O ciszy źródła nie dowiadywał się nikt — ani redakcja, ani agent.

Rozróżniamy trzy rzeczy (kolumny z `add_source_freshness`):
  - `last_scraped`    — ostatnia PRÓBA,
  - `last_success_at` — ostatni raz, gdy źródło ODPOWIEDZIAŁO; pusty wynik też
                        jest odpowiedzią (profil nic nie opublikował),
  - `last_error(_at)` — ostatni błąd.

Alarm na Telegram (kanał sondy kredytów OpenAI, niezależny od poczty) wyłącznie
przy przejściu działa → nie działa i z powrotem. BIP z blokadą padałby dwa razy
dziennie i alarm na każdy przebieg przestałby być czytany po tygodniu.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import update

from src.database.schema import Source

FAILED = "failed"
RECOVERED = "recovered"


def is_failing(last_success_at: Optional[datetime], last_error_at: Optional[datetime]) -> bool:
    """Czy źródło jest teraz w stanie awarii: ostatni błąd późniejszy niż ostatni sukces."""
    return last_error_at is not None and (last_success_at is None or last_error_at > last_success_at)


def transition(
    last_success_at: Optional[datetime],
    last_error_at: Optional[datetime],
    ok: bool,
) -> Optional[str]:
    """Zmiana stanu po bieżącym przebiegu: FAILED, RECOVERED albo None."""
    was_failing = is_failing(last_success_at, last_error_at)
    if ok and was_failing:
        return RECOVERED
    if not ok and not was_failing:
        return FAILED
    return None


async def record(session, source: dict, ok: bool, error: Optional[str] = None,
                 now: Optional[datetime] = None) -> Optional[str]:
    """Zapisuje wynik przebiegu źródła i zwraca zmianę stanu (do alarmu)."""
    now = now or datetime.utcnow()
    change = transition(source.get("last_success_at"), source.get("last_error_at"), ok)
    values = {"last_scraped": now}
    if ok:
        values["last_success_at"] = now
    else:
        values["last_error"] = (error or "nieznany błąd")[:300]
        values["last_error_at"] = now
    await session.execute(update(Source).where(Source.id == source["id"]).values(**values))
    await session.commit()
    return change


def alert_text(changes: list[tuple[str, str, Optional[str]]]) -> Optional[str]:
    """Jedna wiadomość na przebieg: (nazwa, zmiana, błąd) → tekst albo None."""
    failed = [(n, e) for n, c, e in changes if c == FAILED]
    recovered = [n for n, c, _ in changes if c == RECOVERED]
    if not failed and not recovered:
        return None
    lines = []
    if failed:
        lines.append("🔴 Źródła przestały odpowiadać:")
        lines += [f"• {n} — {(e or '')[:120]}" for n, e in failed]
    if recovered:
        lines.append("🟢 Źródła znów odpowiadają:")
        lines += [f"• {n}" for n in recovered]
    return "\n".join(lines)
