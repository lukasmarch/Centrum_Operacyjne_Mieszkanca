"""
Migration: articles.event_checked_at — ślad po pytaniu modelu o wydarzenie (2026-09-16)

Ekstrakcja wydarzeń bierze artykuły z okna `scraped_at >= teraz - 6 h`, a artykuł,
który JUŻ dał wydarzenie, odsiewa podzapytanie po `events.source_article_id`.
Skutek: zapowiedź, której model nie zdążył wyłuskać w tym oknie, nie wraca NIGDY.
16.09.2026 w kalendarzu brakowało przez to zebrania wiejskiego w Rybnie 17.09
o 18:00 (art. 5856, ogłoszone 6.09) i sołeckiego turnieju halowego 27.09
(art. 5902, ogłoszone 8.09) — oba z `articles.event_at` stojącym w bazie.

Okno ekstrakcji obejmuje teraz także wpisy z PRZYSZŁYM terminem, bez względu na
wiek pobrania. Sama ta zmiana zapętliłaby jednak koszt: artykuł, o którym model
powie „to nie wydarzenie" (nabory, konkursy, akcje trwające do końca września),
nie zostawia śladu w `events`, więc wracałby do gpt-4o przy każdym przebiegu
(2× dobę) aż do swojego terminu. 16.09 takich wpisów jest 19 — z czego realnymi
wydarzeniami są trzy.

`event_checked_at` to właśnie ten brakujący ślad: znacznik „model to widział",
stawiany po KAŻDEJ próbie, niezależnie od wyniku. Rozstrzyga wyłącznie o gałęzi
nadrabiania — zwykłe okno 6 h działa jak dotąd, więc świeży materiał jest
sprawdzany tak samo często jak dziś.

NULL znaczy „jeszcze nie pytaliśmy" i takie są wszystkie wpisy sprzed migracji.
Zamierzone: pierwszy przebieg po wdrożeniu nadrobi zaległe zapowiedzi (~8 wywołań
gpt-4o, ok. $0,05), a każdy następny będzie już pytał wyłącznie o nowe.

Idempotentna. Migracja idzie na produkcję PRZED kodem: kolumna, której stary kod
nie używa, nie szkodzi nikomu — kod bez kolumny to 500 na każdym przebiegu AI.

Użycie:
    cd backend && python -m scripts.migrations.add_article_event_checked
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


async def migrate():
    print("=" * 60)
    print("Migration: articles.event_checked_at")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS event_checked_at "
            "TIMESTAMP WITHOUT TIME ZONE NULL"
        ))
        print("✓ kolumna event_checked_at (TIMESTAMP NULL)")

        # Indeks pod gałąź nadrabiania: „zapowiedź jeszcze niesprawdzona".
        # Częściowy, bo pyta o nią wyłącznie ekstrakcja i wyłącznie o wpisy
        # z terminem — pełny indeks na kolumnie NULL-owalnej nic by tu nie dał.
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_articles_event_unchecked "
            "ON articles (event_at) "
            "WHERE event_checked_at IS NULL AND event_at IS NOT NULL"
        ))
        print("✓ indeks idx_articles_event_unchecked (częściowy)")

        pending = (await conn.execute(text("""
            SELECT COUNT(*) FROM articles
            WHERE event_at > NOW() AND event_checked_at IS NULL
              AND is_filler = false AND is_promotional = false
        """))).scalar()
        print(f"  zapowiedzi do nadrobienia przy pierwszym przebiegu: {pending}")
        print("  (część odpadnie na taniej bramce `is_event_candidate` — "
              "awarie, wpisy spoza powiatu)")

    await engine.dispose()
    print("\n✓ Gotowe.")


if __name__ == "__main__":
    asyncio.run(migrate())
