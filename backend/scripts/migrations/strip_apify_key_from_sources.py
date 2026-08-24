"""
Token Apify wychodzi z bazy do środowiska (2026-08-24)

`sources.scraping_config` trzymał `apify_api_key` jawnym tekstem — ten sam token
w PIĘCIU wierszach (źródła 5, 6, 11, 13, 14). Wypływał przy każdym `select * from
sources`, w zrzucie bazy, w Adminerze i w każdym podglądzie tabeli. Wyszło to przy
zwykłym przeglądaniu listy źródeł.

Sekret ma jedno miejsce: `.env` (`APIFY_API_KEY`). `ApifyFacebookScraper` czyta
najpierw środowisko, a config bazy został mu jako zejście awaryjne — więc kod da
się wdrożyć przed tą migracją i po niej, w dowolnej kolejności.

⚠️ KOLEJNOŚĆ NA PRODUKCJI:
    1. zrotuj token w https://console.apify.com/account/integrations
       (stary wyciekł — samo usunięcie go z bazy tego nie cofa)
    2. wpisz NOWY do `backend/.env` oraz `backend/.env.production`
    3. wdróż kod
    4. `docker compose -f docker-compose.prod.yml up -d --force-recreate backend`
       — samo `up -d` NIE przeładowuje środowiska
    5. dopiero teraz ta migracja

Idempotentna: drugi przebieg nie ma czego usuwać. Nie rusza pozostałych kluczy
konfiguracji (`facebook_page_url`, `results_limit`, `actor_id`, …).

Użycie:
    cd backend && python -m scripts.migrations.strip_apify_key_from_sources [--apply]

Bez `--apply` tylko pokazuje, czego dotknie.
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text

from src.config import settings
from src.database.connection import async_session

SELECT_AFFECTED = text(
    "SELECT id, name FROM sources "
    "WHERE scraping_config ? 'apify_api_key' ORDER BY id"
)

STRIP = text(
    "UPDATE sources SET scraping_config = scraping_config - 'apify_api_key' "
    "WHERE scraping_config ? 'apify_api_key'"
)


async def main(apply: bool) -> int:
    async with async_session() as session:
        rows = (await session.execute(SELECT_AFFECTED)).all()

        if not rows:
            print("✅ Żadne źródło nie trzyma tokenu w bazie — nie ma czego usuwać.")
            return 0

        print(f"Źródła z tokenem w `scraping_config` ({len(rows)}):")
        for source_id, name in rows:
            print(f"  {source_id:>3}  {name}")

        # Bezpiecznik: bez tokenu w środowisku usunięcie go z bazy wyłącza scraping
        # Facebooka — a to jest największe źródło lokalnych wpisów (54 na 162 w tygodniu).
        if not settings.APIFY_API_KEY:
            print(
                "\n⛔ APIFY_API_KEY nie jest ustawione w środowisku.\n"
                "   Usunięcie tokenu z bazy zabiłoby scraping Facebooka.\n"
                "   Wpisz token do backend/.env i uruchom ponownie."
            )
            return 1

        if not apply:
            print("\n(podgląd — uruchom z --apply, żeby usunąć)")
            return 0

        result = await session.execute(STRIP)
        await session.commit()
        print(f"\n✅ Usunięto token z {result.rowcount} wierszy. Token żyje tylko w .env.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="wykonaj zmianę")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.apply)))
