"""
Podgląd: co nadrobi ekstrakcja wydarzeń po wdrożeniu `event_checked_at`.

Ekstrakcja bierze świeży materiał z okna `scraped_at` ORAZ zapowiedzi z terminem,
których model jeszcze nie widział (16.09.2026 kalendarz nie miał przez to zebrania
wiejskiego z 17.09 ani turnieju sołectw z 27.09). Gałąź nadrabiania kosztuje
wywołania gpt-4o, więc przed wdrożeniem chcemy wiedzieć dokładnie, ile wpisów
pójdzie do modelu i jakich.

Skrypt NIE woła modelu i niczego nie zapisuje: wykonuje produkcyjne zapytanie
`EventExtractor.candidates` (to samo, nie kopię) i dzieli wynik na to, co przejdzie
tanią bramkę `is_event_candidate`, i to, co na niej odpadnie.

Użycie:
    cd backend && python -u -m scripts.diagnostics.preview_event_catchup
    # na bazie produkcyjnej, przez tunel (tylko odczyt):
    #   ssh -f -N -L 55432:<IP kontenera db>:5432 root@91.99.142.30
    #   DATABASE_URL=postgresql+asyncpg://…@localhost:55432/centrum_operacyjne \
    #     python -u -m scripts.diagnostics.preview_event_catchup
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.ai.event_extractor import EventExtractor, is_event_candidate
from src.config import settings
from src.services.time_span import to_local

# Rząd wielkości jednego wywołania gpt-4o przy ekstrakcji (~1,5 tys. tokenów
# wejścia, kilkaset wyjścia) — do oszacowania kosztu jednorazowego nadrobienia.
COST_PER_ARTICLE_USD = 0.006

WINDOW_HOURS = 6  # tyle, ile ma przebieg produkcyjny (`ai_jobs.run_ai_processing`)


def _stamp(value) -> str:
    return to_local(value).strftime("%d.%m %H:%M") if value else "—"


def _line(article) -> str:
    return (
        f"  #{article.id:5d} termin {_stamp(article.event_at):>12}  "
        f"pobrano {_stamp(article.scraped_at):>12}  loc={article.locality}  "
        f"{(article.category or '—')[:12]:12} "
        f"{(article.display_title or article.title or '')[:52]}"
    )


async def preview(hours: int = WINDOW_HOURS) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    now = datetime.utcnow()
    async with async_session() as session:
        rows = await EventExtractor().candidates(session, hours=hours, now=now)

        to_model = [a for a in rows if is_event_candidate(a)]
        skipped = [a for a in rows if not is_event_candidate(a)]
        cutoff = now - timedelta(hours=hours)
        catchup = [a for a in to_model if not (a.scraped_at and a.scraped_at >= cutoff)]

        print("=" * 78)
        print(f"PODGLĄD EKSTRAKCJI — okno {hours} h + nadrabianie zapowiedzi")
        print("=" * 78)
        print(f"kandydatów z zapytania: {len(rows)}   do modelu: {len(to_model)}   "
              f"odrzuconych bramką: {len(skipped)}")
        print(f"  w tym nadrabianych (zapowiedź spoza okna {hours} h): {len(catchup)}")
        print(f"koszt jednorazowy (szacunek): "
              f"${len(to_model) * COST_PER_ARTICLE_USD:.2f}")

        for label, group in (("DO MODELU", to_model), ("ODRZUCONE BRAMKĄ", skipped)):
            print(f"\n--- {label} ---")
            for article in sorted(group, key=lambda a: (a.event_at or a.scraped_at)):
                print(_line(article))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(preview())
