"""
Import danych Polska w Liczbach (PwL) dla Gminy Rybno

Wczytuje dane z istniejącego FIRECRAWL_polska_w_liczbach/rybno_data.json
(nie wymaga Firecrawl API), tworzy tabele DB, generuje raport porównawczy
GUS vs PwL dla nakładających się zmiennych, a następnie po potwierdzeniu
importuje unikalne dane gminne do pwl_gmina_stats.

Uruchomienie:
    cd backend
    python scripts/migrations/import_pwl_rybno.py

Opcje:
    --auto     Pomiń interaktywne potwierdzenie (import bez pytania)
    --verify   Importuj z is_verified=True od razu
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from src.config import settings
from src.integrations.pwl_integration import (
    PWL_UNIT_ID,
    PWL_UNIT_NAME,
    PWL_URL,
    PWL_DATA_YEAR,
    PWL_FIELD_WHITELIST,
    FIELD_NAMES_PL,
    GUS_OVERLAP_MAP,
    GUS_POPULATION_VAR_ID,
    parse_pwl_from_json,
    flatten_pwl_data,
    generate_comparison_report,
    import_to_db,
)

# Ścieżka do istniejącego pliku JSON
RYBNO_JSON_PATH = backend_path.parent / "FIRECRAWL_polska_w_liczbach" / "rybno_data.json"


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_comparison_report(report: list[dict]):
    """Drukuje tabelę porównawczą GUS vs PwL."""
    print_header("WERYFIKACJA: Nakładające się pola GUS BDL vs PwL")

    print(f"\n{'POLE':<35} {'GUS BDL':>15} {'ROK':>6}  {'PwL':>15}  {'RÓŻNICA':>8}  STATUS")
    print("-" * 90)

    all_match = True
    for item in report:
        field = item["field"]
        name = item.get("field_name", field)[:33]
        gus_val = item.get("gus_value")
        gus_year = item.get("gus_year", "?")
        pwl_val = item.get("pwl_value")
        diff = item.get("diff_pct")
        match = item.get("match")
        note = item.get("note", "")

        if gus_val is None:
            status = "⚠️  brak GUS"
            diff_str = "  N/A"
        elif match is True:
            status = "✅ ZGODNE"
            diff_str = f"{diff:>7.2f}%"
        else:
            status = "❌ RÓŻNICA"
            diff_str = f"{diff:>7.2f}%"
            all_match = False

        gus_str = f"{gus_val:>15,.1f}" if isinstance(gus_val, float) else (f"{gus_val:>15,}" if gus_val is not None else "            N/A")
        pwl_str = f"{pwl_val:>15,.1f}" if isinstance(pwl_val, float) else (f"{pwl_val:>15,}" if pwl_val is not None else "            N/A")

        print(f"{name:<35} {gus_str}  {str(gus_year):>4}   {pwl_str}  {diff_str}  {status}")
        if note:
            print(f"  ℹ️  {note}")

    print("-" * 90)
    if all_match:
        print("\n✅ Wszystkie nakładające się pola są ZGODNE między GUS a PwL.")
    else:
        print("\n⚠️  Wykryto różnice w niektórych polach. Sprawdź przed importem.")


def print_import_summary(records: list[dict]):
    """Drukuje podsumowanie danych do importu."""
    print_header("DANE DO IMPORTU (unikalne dla gminy, brak w GUS BDL)")

    by_section: dict[str, list] = {}
    for rec in records:
        sec = rec["section"]
        by_section.setdefault(sec, []).append(rec)

    total = 0
    for section, recs in by_section.items():
        print(f"\n  [{section.upper()}] — {len(recs)} pól:")
        for rec in recs:
            val = rec["value"]
            extra = rec.get("extra_data")
            if val is not None:
                print(f"    • {rec['field_name_pl']:<45} = {val}")
            elif extra:
                keys = list(extra.keys())
                print(f"    • {rec['field_name_pl']:<45} [złożone: {', '.join(keys)}]")
        total += len(recs)

    print(f"\n  Razem do importu: {total} rekordów")


async def create_tables_if_needed(engine):
    """Tworzy tabele pwl_gmina_stats i pwl_scrape_log jeśli nie istnieją."""
    async with engine.begin() as conn:
        # Sprawdź czy tabele już istnieją
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN ('pwl_gmina_stats', 'pwl_scrape_log')
        """))
        existing = {row[0] for row in result.fetchall()}

        if "pwl_gmina_stats" not in existing:
            print("  Tworzę tabelę pwl_gmina_stats...")
            await conn.execute(text("""
                CREATE TABLE pwl_gmina_stats (
                    id SERIAL PRIMARY KEY,
                    unit_id VARCHAR(20) NOT NULL,
                    unit_name VARCHAR(100) NOT NULL,
                    section VARCHAR(50) NOT NULL,
                    field_key VARCHAR(100) NOT NULL,
                    field_name_pl VARCHAR(200) NOT NULL,
                    year INTEGER NOT NULL,
                    value DOUBLE PRECISION,
                    extra_data JSONB,
                    source_url VARCHAR(300) NOT NULL,
                    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                    scrape_log_id INTEGER,
                    fetched_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX idx_pwl_unit_section_field_year
                ON pwl_gmina_stats (unit_id, section, field_key, year)
            """))
            await conn.execute(text("CREATE INDEX idx_pwl_unit_id ON pwl_gmina_stats (unit_id)"))
            await conn.execute(text("CREATE INDEX idx_pwl_section ON pwl_gmina_stats (section)"))
            await conn.execute(text("CREATE INDEX idx_pwl_is_verified ON pwl_gmina_stats (is_verified)"))
            print("  ✅ Tabela pwl_gmina_stats utworzona")
        else:
            print("  ✅ Tabela pwl_gmina_stats już istnieje")

        if "pwl_scrape_log" not in existing:
            print("  Tworzę tabelę pwl_scrape_log...")
            await conn.execute(text("""
                CREATE TABLE pwl_scrape_log (
                    id SERIAL PRIMARY KEY,
                    unit_id VARCHAR(20) NOT NULL,
                    scraped_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    status VARCHAR(30) NOT NULL,
                    records_imported INTEGER NOT NULL DEFAULT 0,
                    records_updated INTEGER NOT NULL DEFAULT 0,
                    error_message VARCHAR(500),
                    verification_report JSONB
                )
            """))
            await conn.execute(text("CREATE INDEX idx_pwl_log_unit_id ON pwl_scrape_log (unit_id)"))
            await conn.execute(text("CREATE INDEX idx_pwl_log_scraped_at ON pwl_scrape_log (scraped_at DESC)"))
            print("  ✅ Tabela pwl_scrape_log utworzona")
        else:
            print("  ✅ Tabela pwl_scrape_log już istnieje")


async def main():
    auto_mode = "--auto" in sys.argv
    verify_mode = "--verify" in sys.argv

    print_header("Import PwL (Polska w Liczbach) — Gmina Rybno")
    print(f"\n  Plik danych:  {RYBNO_JSON_PATH}")
    print(f"  Rok danych:   {PWL_DATA_YEAR}")
    print(f"  Tryb:         {'AUTO (bez pytań)' if auto_mode else 'INTERAKTYWNY'}")
    print(f"  Weryfikacja:  {'is_verified=True od razu' if verify_mode else 'is_verified=False (wymaga zatwierdzenia)'}")

    # Wczytaj dane z JSON
    if not RYBNO_JSON_PATH.exists():
        print(f"\n❌ Plik nie istnieje: {RYBNO_JSON_PATH}")
        print("   Uruchom najpierw scraping: cd FIRECRAWL_polska_w_liczbach && python scraping/run_rybno_scrape.py")
        sys.exit(1)

    print(f"\n  Wczytuję dane z {RYBNO_JSON_PATH.name}...")
    with open(RYBNO_JSON_PATH, "r", encoding="utf-8") as f:
        raw_json = json.load(f)

    pwl_data = parse_pwl_from_json(raw_json)
    print("  ✅ Dane wczytane")

    # Połącz z bazą
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Utwórz tabele jeśli nie istnieją
    print_header("Sprawdzam/tworzę tabele DB")
    await create_tables_if_needed(engine)

    # Generuj raport porównawczy GUS vs PwL
    print_header("Łączę z GUS BDL w bazie...")
    async with async_session() as db:
        try:
            report = await generate_comparison_report(pwl_data, db)
            print_comparison_report(report)
        except Exception as e:
            print(f"\n  ⚠️  Nie można porównać z GUS (może brak danych GUS w bazie): {e}")
            report = []

    # Przygotuj rekordy do importu
    records = flatten_pwl_data(pwl_data, year=PWL_DATA_YEAR)
    print_import_summary(records)

    # Potwierdzenie użytkownika
    if not auto_mode:
        print("\n" + "=" * 70)
        print("  UWAGA: Dane będą zaimportowane z is_verified=False.")
        print("  Aby udostępnić je przez API, użyj endpointu POST /api/stats/pwl/verify/{log_id}")
        print("  lub uruchom z flagą --verify")
        print("=" * 70)
        answer = input("\n  Kontynuować import? [T/n]: ").strip().lower()
        if answer == "n":
            print("  Import anulowany.")
            await engine.dispose()
            return

    # Utwórz log wpis
    async with async_session() as db:
        log_result = await db.execute(
            text("""
                INSERT INTO pwl_scrape_log
                    (unit_id, scraped_at, status, records_imported, records_updated, verification_report)
                VALUES
                    (:uid, :now, :status, 0, 0, CAST(:report AS jsonb))
                RETURNING id
            """),
            {
                "uid": PWL_UNIT_ID,
                "now": datetime.utcnow(),
                "status": "pending_verification",
                "report": json.dumps(report, ensure_ascii=False) if report else None,
            }
        )
        log_id = log_result.fetchone()[0]
        await db.commit()

    print(f"\n  Log scrapowania: ID={log_id}")

    # Import do bazy
    print("\n  Importuję dane...")
    async with async_session() as db:
        imported, updated = await import_to_db(
            records=records,
            db=db,
            log_id=log_id,
            is_verified=verify_mode,
        )

    # Zaktualizuj log
    async with async_session() as db:
        await db.execute(
            text("""
                UPDATE pwl_scrape_log
                SET status = :status,
                    records_imported = :imported,
                    records_updated = :updated
                WHERE id = :id
            """),
            {
                "status": "success",
                "imported": imported,
                "updated": updated,
                "id": log_id,
            }
        )
        await db.commit()

    print_header("WYNIKI IMPORTU")
    print(f"\n  ✅ Zaimportowano nowych rekordów:  {imported}")
    print(f"  🔄 Zaktualizowano istniejących:    {updated}")
    print(f"  📋 Log ID:                         {log_id}")

    if not verify_mode:
        print(f"\n  ⚠️  Dane wymagają weryfikacji przed udostępnieniem przez API.")
        print(f"  Aby zatwierdzić, wywołaj:")
        print(f"    POST http://localhost:8000/api/stats/pwl/verify/{log_id}")
        print(f"  Lub uruchom ponownie z flagą --verify")
    else:
        print(f"\n  ✅ Dane są od razu dostępne przez API (is_verified=True)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
