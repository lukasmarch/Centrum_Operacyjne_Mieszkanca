"""
Napełnia `gmina_institutions` danymi z BIP — `python -m scripts.run_bip_institutions`

    --dry   pokaż, co by zapisał, i nie zapisuj

⚠️ **`hours` i `scope` są RĘCZNE i przebieg ich NIE KASUJE.** BIP nie publikuje
godzin pracy jednostek, więc kolejny przebieg nadpisujący je pustką skasowałby
to, co ktoś wpisał. Aktualizujemy wyłącznie pola, które przyszły niepuste.

⚠️ Uruchamiać LOKALNIE — serwerownia Hetznera dostaje z BIP 403 (CLAUDE.md,
24.08). Zapis na produkcję przez tunel:
    ssh -f -N -L 55432:<IP kontenera db>:5432 root@91.99.142.30
    DATABASE_URL=…@localhost:55432/centrum_operacyjne python -m scripts.run_bip_institutions
"""
import asyncio
import sys
from datetime import datetime

from sqlalchemy import text

from src.database.connection import async_session
from src.scrapers.bip_institutions import BipInstitutionsScraper
from src.utils.logger import setup_logger

logger = setup_logger("RunBipInstitutions")

# Pola z BIP. `hours` i `scope` świadomie poza listą — patrz docstring.
SCRAPED_FIELDS = ("name", "kind", "address", "phone", "email", "website",
                  "manager", "bip_url", "content_hash")


async def main() -> None:
    dry = "--dry" in sys.argv

    async with BipInstitutionsScraper() as scraper:
        items = await scraper.fetch_all()

    ok = [i for i in items if not i.get("_error")]
    print(f"\nPobrano {len(ok)}/{len(items)} jednostek\n" + "─" * 70)
    for item in items:
        mark = "✗" if item.get("_error") else "✓"
        print(f"{mark} {item['slug']:14} {item.get('name', '')[:52]}")
        print(f"  {item.get('address') or '(brak adresu)':44} "
              f"tel. {item.get('phone') or '—'}")
        if item.get("manager"):
            print(f"  {item['manager']}")
        if item.get("hours"):
            print(f"  godziny: {item['hours']}")

    if dry:
        print("\n--dry — nic nie zapisano")
        return

    created = updated = unchanged = 0
    async with async_session() as session:
        for item in items:
            if item.get("_error"):
                continue
            row = (await session.execute(
                text("SELECT id, content_hash FROM gmina_institutions WHERE slug = :s"),
                {"s": item["slug"]},
            )).first()

            values = {k: item.get(k) for k in SCRAPED_FIELDS}
            # Ręczne pola zapisujemy TYLKO przy tworzeniu wiersza — później
            # należą do człowieka, nie do scrapera.
            if row is None:
                values.update({
                    "slug": item["slug"],
                    "hours": item.get("hours"),
                    "scope": item.get("scope"),
                })
                cols = ", ".join(values)
                await session.execute(
                    text(f"INSERT INTO gmina_institutions ({cols}) "
                         f"VALUES ({', '.join(':' + c for c in values)})"),
                    values,
                )
                created += 1
                continue

            if row.content_hash == item["content_hash"]:
                await session.execute(
                    text("UPDATE gmina_institutions SET last_checked_at = :now WHERE id = :id"),
                    {"now": datetime.utcnow(), "id": row.id},
                )
                unchanged += 1
                continue

            sets = ", ".join(f"{k} = :{k}" for k, v in values.items() if v is not None)
            params = {k: v for k, v in values.items() if v is not None}
            params.update({"id": row.id, "now": datetime.utcnow()})
            await session.execute(
                text(f"UPDATE gmina_institutions SET {sets}, "
                     f"last_checked_at = :now, content_changed_at = :now WHERE id = :id"),
                params,
            )
            updated += 1

        await session.commit()

    print(f"\nZapisano: {created} nowych, {updated} zmienionych, {unchanged} bez zmian")
    logger.info(f"gmina_institutions: +{created} ~{updated} ={unchanged}")


if __name__ == "__main__":
    asyncio.run(main())
