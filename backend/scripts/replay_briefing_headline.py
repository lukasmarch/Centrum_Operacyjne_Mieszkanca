"""
Odtworzenie wyboru nagłówka briefingu dla minionych dni — bez modelu.

Przechodzi tą samą drogą co `SummaryGenerator.generate_daily_summary`:
`_material_window` → `_gather_material` (okno, zapas z wczoraj, bramki, dedup,
lokalność) → `_select_top_article`. Model nie jest wołany: nagłówek wybiera kod
(walidator briefingu wymusza go na modelu), więc to wystarcza do pomiaru.

Po co: audyt 11.10.2026 (F-012) znalazł 4 nagłówki na 31 spoza gminy. Zapas
z wczoraj liczył wszystkie wpisy, a lokalne wpisy dnia przychodzą z Facebooka
dopiero nazajutrz. Ten skrypt mierzy, ile nagłówków byłoby z gminy dziś.

⚠️ Odtworzenie, nie zapis historii: baza mogła się od tamtej chwili zmienić
(ponowna kategoryzacja, `scraped_at` nadpisywany przy re-scrapie). Domyślnie
wpis jest „dostępny” od publikacji — to OPTYMIZM: post z FB z popołudnia
trafia do bazy nazajutrz o 6:00, i właśnie to robiło nagłówki spoza gminy.
`--pobrane` liczy dostępność od `scraped_at` — PESYMIZM (pole bywa nadpisane
późniejszym pobraniem). Prawda leży pomiędzy; brakuje `first_seen_at` (F-017).

    cd backend && python -m scripts.replay_briefing_headline [--since 2026-09-10] [--until 2026-10-09] [--przed] [--pobrane] [--godzina 13:30]
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import select

from src.ai.summary_generator import SummaryGenerator
from src.database.connection import async_session
from src.database.schema import Source
from src.services.time_span import to_utc


def _arg(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


async def headline_at(gen: SummaryGenerator, session, now: datetime):
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)  # tz-ok: klucz dnia, jak w generatorze
    window_start, window_end = gen._material_window(now, today_start)
    articles, extended = await gen._gather_material(
        session, now, window_start, window_end, today_start, today_start, 10
    )
    by_category: dict = {}
    for article in articles:
        by_category.setdefault(article.category or "Inne", []).append(article)
    recent = await gen._recent_headline_topics(session, today_start)
    top = gen._select_top_article(by_category, now, recent)
    return top, extended, len(articles)


async def main() -> int:
    since = datetime.fromisoformat(_arg("--since", "2026-09-10"))
    until = datetime.fromisoformat(_arg("--until", "2026-10-09"))
    gen = SummaryGenerator.__new__(SummaryGenerator)
    if "--przed" in sys.argv:
        gen.EXTEND_WHEN_NO_LOCAL = False  # reguła sprzed 11.10: zapas tylko przy < 10 wpisach
    if "--pobrane" in sys.argv:
        fetch = gen._fetch_articles

        async def fetched_by_now(session, window_start, window_end, now=None):
            rows = await fetch(session, window_start, window_end, now)
            return [a for a in rows if a.scraped_at is None or a.scraped_at <= now]
        gen._fetch_articles = fetched_by_now
    foreign = 0
    days = 0
    async with async_session() as session:
        gen._source_names = {r.id: r.name for r in (await session.execute(select(Source.id, Source.name))).all()}
        day = since
        while day <= until:
            hh, mm = (int(x) for x in _arg("--godzina", "7:00").split(":"))
            now = to_utc(day.replace(hour=hh, minute=mm))  # godzina LOKALNA przebiegu (7:00 rano, 13:30 odświeżenie)
            top, extended, n = await headline_at(gen, session, now)
            days += 1
            if top is None:
                print(f"{day:%d.%m}  — brak materiału")
            else:
                local = gen._is_local(top)
                foreign += not local
                print(f"{day:%d.%m}  {'GMINA ' if local else 'OBCY  '} {top.id:>5} loc={top.locality}"
                      f" {'(+wczoraj)' if extended else '          '} n={n:<3} {(top.display_title or top.title)[:60]}")
            day += timedelta(days=1)
    print(f"\nNagłówki spoza gminy: {foreign}/{days}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
