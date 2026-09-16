"""
Migration: cztery profile FB z gminy Rybno jako źródła (2026-09-16)

Pomiar wolumenu (3.09.2026, 14 dni): 4–9 wpisów o gminie dziennie, z czego 76%
z jednego profilu (Syla). Oficjalne kanały gminy prawie milczą — „Gmina Rybno"
dała 2 wpisy, „Facebook - Rybno" 8. Radio 7 i KPP wrzucają 91 wpisów, z których
lokalne są dwa. Feed jest więc krótki nie dlatego, że polityka jest ostra,
tylko dlatego, że materiału o gminie po prostu nie ma.

Cztery profile obejrzane 15–16.09.2026 w przeglądarce:
  GOPS Rybno         1,2 tys. obserwujących, ostatni wpis sprzed 4 dni
                     (termin wypłaty świadczeń — dokładnie to, po co ludzie
                     dzwonią do urzędu)
  Żłobek w Rybnie      650 obserwujących, wpis sprzed 5 godzin
  Sołectwo Hartowiec   837 obserwujących, wpis sprzed 4 dni
  Sołtys Sołectwa Żabiny 3 tys. obserwujących, wpis sprzed 4 dni — ogłoszenie
                     o posiedzeniu Komisji Rewizyjnej 22.09, którego nie mamy
                     z żadnego innego źródła (BIP oddaje serwerowi 403)

⚠️ Ostatni to PROFIL OSOBOWY, nie strona instytucji: ma datę urodzenia i listę
znajomych. Decyzja Łukasza z 16.09: pobieramy, ale do feedu wpuszczamy WYŁĄCZNIE
ogłoszenia (`feed_policy.ANNOUNCEMENT_ONLY_SOURCES`) — i tylko do czasu, aż
sołectwa dostaną własne miejsce do publikowania na naszej stronie. Wtedy to
źródło wyłączamy.

⚠️ KOD IDZIE PRZED DANYMI, odwrotnie niż przy migracjach schematu. Źródło dopisane
do bazy jest scrapowane przy najbliższym przebiegu, a stary kod nie zna ani wag
tych profili (liczyłyby się jako obce, `DEFAULT_WEIGHT`), ani bramki ogłoszeń —
więc wpisy z profilu sołtysa weszłyby do feedu bez niej.

💰 Koszt: aktor liczy 0,005 USD za post + 0,002 za filtr daty + 0,001 za start,
a przebieg bez nowych postów też kosztuje 0,008 (aktor zwraca wtedy pozycję
„no_items"). Przy czterech profilach w dni robocze to ~0,7 USD/mies. Plan FREE
ma 5 USD/mies. (cykl od 22. dnia miesiąca), zużycie na 15.09: 3,79 USD.
Dlatego `article_job.WEEKDAY_ONLY_SOURCES` pomija je w soboty i niedziele.

Idempotentna (dopasowanie po nazwie).

Użycie:
    cd backend && python -m scripts.migrations.add_gmina_fb_sources
"""
import asyncio
import json
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


def _apify(page_url: str, results_limit: int = 10) -> dict:
    """Konfiguracja jak dla pozostałych profili FB (`ApifyFacebookScraper`).

    `results_limit` niższy niż u Syli (12) i profilu gminy (15): te profile
    publikują rzadko, a limit jest górną granicą liczby POBRANYCH postów, czyli
    wprost górną granicą rachunku za przebieg.
    """
    return {
        "actor_id": "apify~facebook-posts-scraper",
        "caption_text": False,
        "results_limit": results_limit,
        "scraper_class": "ApifyFacebookScraper",
        "facebook_page_url": page_url,
    }


SOURCES = [
    {
        "name": "Facebook - GOPS Rybno",
        "type": "social_media",
        "url": "https://www.facebook.com/GOPSRybno",
        "config": _apify("https://www.facebook.com/GOPSRybno"),
    },
    {
        "name": "Facebook - Żłobek w Rybnie",
        "type": "social_media",
        "url": "https://www.facebook.com/zlobek.rybno",
        "config": _apify("https://www.facebook.com/zlobek.rybno"),
    },
    {
        "name": "Facebook - Sołectwo Hartowiec",
        "type": "social_media",
        "url": "https://www.facebook.com/profile.php?id=100039887288210",
        "config": _apify("https://www.facebook.com/profile.php?id=100039887288210"),
    },
    {
        # Profil osobowy — patrz nagłówek i `feed_policy.ANNOUNCEMENT_ONLY_SOURCES`
        "name": "Facebook - Sołtys Żabiny",
        "type": "social_media",
        "url": "https://www.facebook.com/profile.php?id=100012870272757",
        "config": _apify("https://www.facebook.com/profile.php?id=100012870272757"),
    },
]


async def migrate():
    print("=" * 70)
    print("Migration: profile FB z gminy Rybno (GOPS, żłobek, sołectwa)")
    print("=" * 70)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        for src in SOURCES:
            row = (await conn.execute(
                text("SELECT id FROM sources WHERE name = :name"),
                {"name": src["name"]},
            )).fetchone()

            params = {
                "name": src["name"],
                "type": src["type"],
                "url": src["url"],
                "config": json.dumps(src["config"], ensure_ascii=False),
            }

            if row:
                await conn.execute(text("""
                    UPDATE sources
                    SET url = :url, scraping_config = CAST(:config AS jsonb)
                    WHERE id = :id
                """), {**params, "id": row.id})
                print(f"✓ '{src['name']}' już jest (id={row.id}) — config odświeżony")
                continue

            await conn.execute(text("""
                INSERT INTO sources (name, type, url, scraping_config, status, created_at)
                VALUES (:name, :type, :url, CAST(:config AS jsonb), 'active', NOW())
            """), params)
            print(f"✓ dodane '{src['name']}'")

    await engine.dispose()
    print("\n✓ Gotowe. Pierwsze pobranie: najbliższy przebieg 6:00 w dzień roboczy.")


if __name__ == "__main__":
    asyncio.run(migrate())
