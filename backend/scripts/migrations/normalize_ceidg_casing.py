"""
Migration: normalizacja wielkości liter w adresach CEIDG

Część rekordów (starszy import) ma powiat/gmina/miasto zapisane WIELKIMI LITERAMI
("DZIAŁDOWSKI", "RYBNO", "HARTOWIEC"). Skutki w produkcie:
- zapytania filtrują dokładnym dopasowaniem `powiat == "działdowski"` → 12 firm
  (w tym 6 aktywnych) wypadało ze wszystkich statystyk i z katalogu
- lista miejscowości pokazywała zduplikowane kafelki ("HARTOWIEC" obok "Hartowiec")

Normalizuje każde pole niezależnie (są rekordy z poprawnym powiatem, ale wielkim
miastem). Idempotentna — kolejne uruchomienia nic nie zmienią.

Użycie:
    cd backend && python -m scripts.migrations.normalize_ceidg_casing
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


async def migrate():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # powiat: konwencja w bazie to małe litery ("działdowski")
        res = await conn.execute(text(
            "UPDATE ceidg_businesses SET powiat = lower(powiat) "
            "WHERE powiat <> lower(powiat)"
        ))
        powiat_fixed = res.rowcount

        # gmina i miasto: konwencja to Initcap ("Rybno", "Gralewo-Stacja")
        res = await conn.execute(text(
            "UPDATE ceidg_businesses SET gmina = initcap(gmina) "
            "WHERE gmina <> initcap(gmina)"
        ))
        gmina_fixed = res.rowcount

        res = await conn.execute(text(
            "UPDATE ceidg_businesses SET miasto = initcap(miasto) "
            "WHERE miasto <> initcap(miasto)"
        ))
        miasto_fixed = res.rowcount

        check = await conn.execute(text(
            "SELECT count(*) FROM ceidg_businesses WHERE powiat = 'działdowski'"
        ))
        widoczne = check.scalar() or 0
        total = (await conn.execute(text("SELECT count(*) FROM ceidg_businesses"))).scalar() or 0

    await engine.dispose()
    print(f"✅ Znormalizowano — powiat: {powiat_fixed}, gmina: {gmina_fixed}, miasto: {miasto_fixed}")
    print(f"   Firm w statystykach: {widoczne} / {total} w bazie")
    if widoczne != total:
        print(f"   ⚠️  {total - widoczne} rekordów nadal poza filtrem powiatu — sprawdzić ręcznie")


if __name__ == "__main__":
    asyncio.run(migrate())
