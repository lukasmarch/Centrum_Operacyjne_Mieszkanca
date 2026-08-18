"""
Migration: firma dopisana ręcznie, spoza CEIDG (2026-08-18)

Powód. Katalog stoi na `ceidg_businesses`, czyli na tym, co zwraca rejestr.
Poza rejestrem zostaje jednak część firm, które w gminie realnie działają:
spółki (CEIDG obejmuje wyłącznie jednoosobowe działalności), oddziały
zarejestrowane pod adresem spoza gminy, koła gospodyń i stowarzyszenia.
Do tej pory nie miały jak trafić do katalogu — a to one najczęściej pytają
o wizytówkę, bo w rejestrze ich nie ma.

Kolumna `source` rozstrzyga, skąd wiersz pochodzi: 'ceidg' albo 'manual'.

⚠️ Bez niej funkcja nie działałaby wcale, a nie „działała gorzej".
`ceidg_job` oznacza statusem WYKRESLONY każdy wiersz nieobecny w odpowiedzi
API, a wpis ręczny z definicji nie ma tam odpowiednika. Firma zapłaciłaby
za wizytówkę i zniknęła z katalogu w pierwszą niedzielę o 3:00.

Drugi, cichszy skutek: wpisy ręczne wpadałyby do mianownika `coverage`
w bramce bezpieczeństwa syncu. Im więcej ręcznych firm, tym niższe pokrycie —
aż spadnie poniżej progu i sync przestanie oznaczać PRAWDZIWE wykreślenia.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_manual_businesses
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text

from src.database.connection import async_session  # noqa: E402


async def migrate() -> None:
    async with async_session() as session:
        existing = (await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'ceidg_businesses'"
        ))).scalars().all()

        if "source" in existing:
            print("  = kolumna source już istnieje")
        else:
            # NOT NULL z DEFAULT: każdy wiersz, który jest teraz w tabeli,
            # przyszedł z rejestru — innej drogi do niej nie było.
            await session.execute(text(
                "ALTER TABLE ceidg_businesses "
                "ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'ceidg'"
            ))
            print("  + dodano kolumnę source (wszystkie istniejące wiersze → 'ceidg')")

        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ceidg_source "
            "ON ceidg_businesses (source)"
        ))
        print("  + indeks idx_ceidg_source")

        counts = (await session.execute(text(
            "SELECT source, COUNT(*) FROM ceidg_businesses GROUP BY source"
        ))).all()
        for source, count in counts:
            print(f"  ~ {source}: {count} firm")

        await session.commit()
        print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
