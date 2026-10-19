"""
Kontrakt kod ↔ schemat produkcji (audyt 10–11.10.2026, E5).

`prod_schema.sql` (generowany `scripts/db_schema_refresh.sh`) mówi, co NAPRAWDĘ stoi
na produkcji. Ten moduł czyta go bez bazy, więc działa w CI, w runnerze migracji
i w testach tak samo.

Czego NIE sprawdza: SQL pisanego ręcznie w `text("...")` (żadne narzędzie statyczne
tego nie złapie) oraz typów kolumn — tylko istnienie tabeli i kolumny, czyli dokładnie
ten błąd, który kończy się 500 na każdym zapytaniu („kod bez kolumny”).
"""
from __future__ import annotations

import re
from pathlib import Path

SCHEMA_FILE = Path(__file__).parent / "prod_schema.sql"

_TABLE = re.compile(r"^CREATE TABLE public\.(\w+) \($")
_COLUMN = re.compile(r'^    "?([a-z_0-9]+)"? ')


def parse_schema(sql: str) -> dict[str, set[str]]:
    """{tabela: {kolumny}} z zrzutu `pg_dump -s`."""
    tables: dict[str, set[str]] = {}
    current = None
    for line in sql.splitlines():
        if current is None:
            m = _TABLE.match(line)
            if m:
                current = m.group(1)
                tables[current] = set()
        elif line.startswith(");"):
            current = None
        else:
            m = _COLUMN.match(line)
            if m and not line.lstrip().startswith(("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK")):
                tables[current].add(m.group(1))
    return tables


def load_schema() -> dict[str, set[str]]:
    return parse_schema(SCHEMA_FILE.read_text(encoding="utf-8"))


def missing_in_schema(model_columns: dict[str, set[str]], schema: dict[str, set[str]]) -> list[str]:
    """Co kod (modele) zna, a produkcja nie: `tabela` albo `tabela.kolumna`."""
    gaps: list[str] = []
    for table, columns in sorted(model_columns.items()):
        if table not in schema:
            gaps.append(table)
            continue
        gaps.extend(f"{table}.{c}" for c in sorted(columns - schema[table]))
    return gaps


def missing_in_database(schema: dict[str, set[str]], db_columns: dict[str, set[str]]) -> list[str]:
    """Co produkcja ma według pliku, a konkretna baza nie — baza ZA produkcją.
    Odwrotny kierunek (baza ma więcej) to stan normalny: lokalnie testujemy kod przed wdrożeniem."""
    return missing_in_schema(schema, db_columns)


def model_columns() -> dict[str, set[str]]:
    """Tabele i kolumny znane SQLModel (importuje `src.database.schema`)."""
    from sqlmodel import SQLModel

    import src.database.schema  # noqa: F401 — rejestruje modele w metadanych

    return {t.name: {c.name for c in t.columns} for t in SQLModel.metadata.tables.values()}
