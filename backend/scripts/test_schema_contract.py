"""
Kontrakt kod ↔ schemat produkcji (audyt 10–11.10.2026, E5). BEZ BAZY — działa w CI.

Reguła „migracja idzie na produkcję PRZED kodem” była pilnowana wyłącznie pamięcią:
kod z kolumną, której produkcja nie ma, to 500 na każdym zapytaniu, a zielony job
Actions niczego nie zauważał. Teraz modele nie mogą znać tabeli ani kolumny, której nie ma
w `scripts/schema/prod_schema.sql` — a ten plik powstaje z produkcji (`scripts/db_schema_refresh.sh`),
więc dodać do niego kolumnę można dopiero po wykonaniu migracji na produkcji.

Sprawdza:
  1. parser czyta zrzut (52 tabele, znane kolumny; `\\restrict` i inne śmieci nie wchodzą)
  2. KONTRAKT: każda tabela i kolumna modeli istnieje w zrzucie
  3. strażnik naprawdę łapie rozjazd (kolumna dopisana do modelu, zrzut bez niej → czerwono)
  4. zrzut ma to, czego create_all nie zbuduje: rozszerzenie vector, funkcję i trigger tsvector
  5. informacyjnie: tabele produkcji, których modele nie znają (nie błąd — czytane przez text())

Użycie: cd backend && python -m scripts.test_schema_contract
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.schema import contract

results: list[bool] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))
    return ok


def main() -> int:
    sql = contract.SCHEMA_FILE.read_text(encoding="utf-8")
    schema = contract.parse_schema(sql)

    print("\n1️⃣  Parser zrzutu")
    check("52 tabele produkcji w zrzucie", len(schema) >= 50, len(schema))
    check("users ma kolumnę email", "email" in schema.get("users", set()))
    check("document_embeddings ma kolumnę wektorową i tsvector",
          {"embedding", "search_vector"} <= schema.get("document_embeddings", set()))
    check("brak śmieci z pg_dump (\\restrict, wersje narzędzi)",
          "\\restrict" not in sql and "-- Dumped from" not in sql)
    check("kolumny bez ograniczeń typu CONSTRAINT/PRIMARY",
          not any(c.upper() == c for cols in schema.values() for c in cols))

    print("\n2️⃣  KONTRAKT: modele ⊆ produkcja")
    models = contract.model_columns()
    gaps = contract.missing_in_schema(models, schema)
    check(f"{len(models)} tabel modeli, {sum(len(c) for c in models.values())} kolumn — wszystkie są na produkcji",
          not gaps, ", ".join(gaps[:8]))

    print("\n3️⃣  Strażnik łapie rozjazd")
    fake = {t: set(c) for t, c in models.items()}
    fake["users"].add("kolumna_ktorej_nie_ma_na_produkcji")
    check("kolumna w modelu bez pokrycia w zrzucie → wykryta",
          contract.missing_in_schema(fake, schema) == ["users.kolumna_ktorej_nie_ma_na_produkcji"])
    fake2 = {**models, "nowa_tabela": {"id"}}
    check("tabela w modelu bez pokrycia w zrzucie → wykryta",
          "nowa_tabela" in contract.missing_in_schema(fake2, schema))
    behind = {t: set(c) for t, c in schema.items()}
    behind["articles"].discard("withdrawn_at")
    check("baza ZA produkcją (brak kolumny z pliku) → wykryta",
          contract.missing_in_database(schema, behind) == ["articles.withdrawn_at"])
    ahead = {t: set(c) | {"kolumna_testowa"} for t, c in schema.items()}
    check("baza PRZED produkcją (lokalnie więcej) → stan normalny, bez alarmu",
          contract.missing_in_database(schema, ahead) == [])

    print("\n4️⃣  Zrzut zawiera to, czego create_all nie zbuduje")
    check("rozszerzenie vector", "CREATE EXTENSION IF NOT EXISTS vector" in sql)
    check("funkcja i trigger tsvector (wyszukiwanie BM25)",
          "update_search_vector" in sql and "CREATE TRIGGER tsvector_update" in sql)
    check("indeks HNSW na embeddingach", "USING hnsw" in sql)

    print("\n5️⃣  Informacyjnie: tabele poza modelami (czytane przez text())")
    outside = sorted(set(schema) - set(models))
    print(f"   ℹ️  {len(outside)}: {', '.join(outside)}")

    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
