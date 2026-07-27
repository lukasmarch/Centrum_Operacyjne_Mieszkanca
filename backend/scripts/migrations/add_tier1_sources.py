"""
Migration: Add Tier 1 legal replacement sources (Etap A planu z 29.06.2026)

Dodaje 4 legalne źródła RSS zastępujące wartość informacyjną wyłączonej
Panoramy Regionu (blackouty, komunikaty JST, region):

  - Energa-Operator: wyłączenia bieżące i planowane (filtr: powiat działdowski)
  - Powiat Działdowski: oficjalny feed WordPress
  - Radio Olsztyn: wiadomości regionalne (filtr: powiat działdowski)

Nazwy zawierają "(RSS)" — registry automatycznie mapuje je na RSSFeedScraper.
`keyword_filter` w scraping_config zawęża feedy wojewódzkie do artykułów
wspominających powiat działdowski (obsługa w RSSFeedScraper.scrape_feed).

Skrypt jest idempotentny (dopasowanie po nazwie źródła).

Użycie:
    cd backend && python -m scripts.migrations.add_tier1_sources
"""
import asyncio
import json
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


# Miejscowości powiatu działdowskiego. Frazy muszą być jednoznaczne:
# - samo "lidzbark" łapie Lidzbark Warmiński (inny powiat),
# - "rumian" łapie "ulica Rumiankowa" (Morąg); wyłączenia w Rumianie i tak
#   złapie "rybno" — Energa tytułuje "Region Działdowo - Rybno obszar wiejski".
POWIAT_KEYWORDS = [
    "rybno", "działdow", "płośnic", "iłowo",
    "lidzbark welski", "gminie lidzbark", "gmina lidzbark", "gminy lidzbark",
    "koszelewy", "hartowiec", "tuczki", "żabiny", "gralewo",
]

SOURCES = [
    {
        "name": "Energa - wyłączenia bieżące (RSS)",
        "type": "rss",
        # id=6 = Oddział Płock (Region Mława obsługuje powiat działdowski).
        # Oddział Olsztyn (id=5) NIE obejmuje naszego terenu — stąd zero wpisów
        "url": "https://rss.energa-operator.pl/rss/wylaczenia_biezace?id=6",
        # item_parser: termin zdarzenia, wspólny id i kontekst — src/services/energa.py
        # max_age_days: ogłoszenie bywa sprzed trzech tygodni, liczy się termin
        "config": {
            "keyword_filter": POWIAT_KEYWORDS,
            "max_age_days": 30,
            "item_parser": "energa",
        },
    },
    {
        "name": "Energa - wyłączenia planowane (RSS)",
        "type": "rss",
        "url": "https://rss.energa-operator.pl/rss/wylaczenia_planowane?id=6",
        "config": {
            "keyword_filter": POWIAT_KEYWORDS,
            "max_age_days": 30,
            "item_parser": "energa",
        },
    },
    {
        "name": "Powiat Działdowski (RSS)",
        "type": "rss",
        "url": "https://powiatdzialdowski.pl/feed/",
        "config": {},
    },
    {
        "name": "Radio Olsztyn (RSS)",
        "type": "rss",
        "url": "https://radioolsztyn.pl/feed",
        "config": {"keyword_filter": POWIAT_KEYWORDS + ["dk7"]},
    },
]


async def migrate():
    print("=" * 60)
    print("Migration: add Tier 1 sources (Energa, Powiat, Radio Olsztyn)")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        for src in SOURCES:
            result = await conn.execute(
                text("SELECT id, status FROM sources WHERE name = :name"),
                {"name": src["name"]},
            )
            row = result.fetchone()

            if row:
                # Źródło istnieje — zaktualizuj url i config (kalibracja filtrów)
                await conn.execute(text("""
                    UPDATE sources
                    SET url = :url, scraping_config = CAST(:config AS jsonb)
                    WHERE id = :id
                """), {
                    "id": row.id,
                    "url": src["url"],
                    "config": json.dumps(src["config"], ensure_ascii=False),
                })
                print(f"✓ '{src['name']}' exists (id={row.id}) – config updated")
                continue

            await conn.execute(text("""
                INSERT INTO sources (name, type, url, scraping_config, status, created_at)
                VALUES (:name, :type, :url, CAST(:config AS jsonb), 'active', NOW())
            """), {
                "name": src["name"],
                "type": src["type"],
                "url": src["url"],
                "config": json.dumps(src["config"], ensure_ascii=False),
            })
            print(f"✓ Added '{src['name']}'")

    await engine.dispose()
    print("=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate())
