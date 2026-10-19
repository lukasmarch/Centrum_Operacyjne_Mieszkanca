"""
Runner migracji schematu (audyt 10–11.10.2026, E5).

Do tej pory: 54 ręczne skrypty, żaden nie zapisywał, że poszedł, `alembic_version` stoi od lutego.
Nikt nie umiał powiedzieć, czego brakuje w danej bazie, a „migracja przed kodem” była pilnowana
pamięcią. Teraz `schema_migrations` jest licznikiem, a `scripts/migrations/manifest.py` — listą.

  python -m scripts.migrate --status            # co poszło, co czeka (nic nie zmienia)
  python -m scripts.migrate --check             # kod wyjścia: 0 czysto | 1 czeka migracja | 2 brak rejestru
  python -m scripts.migrate --apply --yes       # uruchom CZEKAJĄCE migracje `schema`, po kolei
  python -m scripts.migrate --baseline --yes    # zapisz WSZYSTKIE migracje `schema` jako wykonane (bez uruchamiania)

Reguły:
  • Uruchamiane są wyłącznie migracje `schema` z manifestu. Skryptów `data` (clean_database, źródła, RODO)
    runner nie ruszy nigdy.
  • `--apply` staje na pierwszym błędzie i nie zapisuje nieudanej migracji.
  • `--baseline` jest dla bazy, w której migracje już zostały wykonane ręcznie (produkcja, lokalna).
    Odmawia, jeśli baza jest ZA produkcją według `prod_schema.sql` (brakuje jej kolumn) — wtedy trzeba
    wykonać brakujące migracje, a nie udawać, że je wykonano. `--force` obchodzi tę blokadę.
  • Baza PRZED produkcją (lokalnie więcej) to stan normalny: tu testujemy kod, który czeka na wdrożenie.

Nowa migracja na produkcji (wdrożenie z bramką, gdy `migrate --check` jest w deployu):
  1. plik `add_*.py` + linia w manifeście, test zielony, commit
  2. na serwerze, nowym obrazem, bez podmiany działającego kontenera:
       docker compose -f docker-compose.prod.yml build backend
       docker compose -f docker-compose.prod.yml run --rm --no-deps backend python -m scripts.migrate --apply --yes
  3. `bash scripts/db_schema_refresh.sh`, commit zrzutu, dopiero potem push kodu używającego nowej kolumny
"""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.migrations.manifest import DATA, MANIFEST, SCHEMA, Migration
from scripts.schema import contract

CREATE_REGISTRY = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name VARCHAR(100) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    baseline BOOLEAN NOT NULL DEFAULT FALSE
)
"""


def pending(applied: set[str], manifest: list[Migration] = MANIFEST) -> list[Migration]:
    """Migracje `schema`, których baza jeszcze nie ma, w kolejności manifestu.
    `data` nigdy nie jest „czekające” — to nie jest rzecz do uruchomienia automatem."""
    return [m for m in manifest if m.kind == SCHEMA and m.name not in applied]


async def registry_applied(conn) -> set[str] | None:
    """Zbiór wykonanych migracji albo None, gdy rejestr jeszcze nie istnieje."""
    exists = (await conn.execute(text("SELECT to_regclass('public.schema_migrations')"))).scalar()
    if exists is None:
        return None
    return {r[0] for r in (await conn.execute(text("SELECT name FROM schema_migrations")))}


async def db_columns(conn) -> dict[str, set[str]]:
    rows = await conn.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
    ))
    columns: dict[str, set[str]] = {}
    for table, column in rows:
        columns.setdefault(table, set()).add(column)
    return columns


def _print_status(applied: set[str] | None) -> list[Migration]:
    todo = pending(applied or set())
    if applied is None:
        print("Rejestr `schema_migrations` NIE istnieje w tej bazie (użyj --baseline albo --apply).")
    for m in MANIFEST:
        if m.kind == DATA:
            mark = "ręczny (data)"
        elif applied is not None and m.name in applied:
            mark = "✓ wykonana"
        else:
            mark = "✗ CZEKA"
        print(f"  {m.date}  {m.name:42s} {mark}")
    schema_total = sum(1 for m in MANIFEST if m.kind == SCHEMA)
    print(f"\nschema: {schema_total - len(todo)}/{schema_total} wykonanych, czeka: {len(todo)}; "
          f"data (ręczne): {sum(1 for m in MANIFEST if m.kind == DATA)}")
    return todo


async def run(args) -> int:
    engine = create_async_engine(settings_url(), echo=False)
    try:
        async with engine.begin() as conn:
            applied = await registry_applied(conn)

            if args.status:
                _print_status(applied)
                return 0

            if args.check:
                if applied is None:
                    print("✗ Rejestr migracji nie istnieje w tej bazie — najpierw `--baseline --yes`.")
                    return 2
                todo = pending(applied)
                if todo:
                    print(f"✗ Czeka {len(todo)} migracji schematu, a kod może ich wymagać:")
                    for m in todo:
                        print(f"    - {m.name}")
                    print("  Wykonaj je PRZED kodem: python -m scripts.migrate --apply --yes")
                    return 1
                print("✓ Wszystkie migracje schematu wykonane.")
                return 0

            if not args.yes:
                print("Ta operacja zmienia bazę — dodaj --yes, jeśli to ma być TA baza:")
                print(f"  {engine.url.render_as_string(hide_password=True)}")
                return 2

            await conn.execute(text(CREATE_REGISTRY))
            applied = await registry_applied(conn) or set()

            if args.baseline:
                gaps = contract.missing_in_database(contract.load_schema(), await db_columns(conn))
                gaps = [g for g in gaps if not g.startswith("schema_migrations")]
                if gaps and not args.force:
                    print(f"✗ Baza jest ZA produkcją ({len(gaps)} brakujących elementów, np. {', '.join(gaps[:6])}).")
                    print("  Baseline oznaczałby je jako wykonane, choć ich nie ma. Wykonaj migracje ręcznie,")
                    print("  potem powtórz. (--force obchodzi blokadę — tylko świadomie.)")
                    return 1
                added = 0
                for m in MANIFEST:
                    if m.kind == SCHEMA and m.name not in applied:
                        await conn.execute(
                            text("INSERT INTO schema_migrations (name, baseline) VALUES (:n, TRUE) ON CONFLICT DO NOTHING"),
                            {"n": m.name},
                        )
                        added += 1
                print(f"✓ Baseline: zapisano {added} migracji jako wykonane "
                      f"(razem {len(applied) + added}; skryptów `data` nie zapisuje się nigdy).")
                return 0

        if args.apply:
            todo = pending(applied)
            if not todo:
                print("✓ Nie ma czego wykonywać.")
                return 0
            print(f"Wykonuję {len(todo)} migracji w kolejności manifestu…")
            for m in todo:
                print(f"\n── {m.name} ──")
                done = subprocess.run([sys.executable, "-m", f"scripts.migrations.{m.name}"], cwd=BACKEND)
                if done.returncode != 0:
                    print(f"✗ {m.name} zakończyła się błędem ({done.returncode}) — przerywam, nie zapisuję jej.")
                    return 1
                async with engine.begin() as conn:
                    await conn.execute(
                        text("INSERT INTO schema_migrations (name) VALUES (:n) ON CONFLICT DO NOTHING"),
                        {"n": m.name},
                    )
            print("\n✓ Gotowe. Odśwież zrzut: bash scripts/db_schema_refresh.sh")
            return 0
        return 0
    finally:
        await engine.dispose()


def settings_url() -> str:
    from src.config import settings
    return settings.DATABASE_URL


def main() -> int:
    parser = argparse.ArgumentParser(description="Runner migracji schematu")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--baseline", action="store_true")
    parser.add_argument("--yes", action="store_true", help="potwierdza zmianę bazy (--apply, --baseline)")
    parser.add_argument("--force", action="store_true", help="--baseline mimo braków względem prod_schema.sql")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
