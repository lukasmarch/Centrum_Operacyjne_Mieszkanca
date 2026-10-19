"""
Rejestr migracji (audyt 10–11.10.2026, E5). BEZ BAZY — działa w CI.

Pilnuje, żeby lista migracji i katalog z plikami nie rozjechały się po cichu — dokładnie ten
rodzaj dryfu, który przez pół roku zostawiał bazy w różnych stanach:
  1. każdy plik w `scripts/migrations/` ma wpis w manifeście i odwrotnie
  2. nazwy unikalne, rodzaje tylko `schema` / `data`, daty w porządku rosnącym
  3. skrypty `data` (clean_database, źródła, RODO) NIGDY nie są „czekające” — runner ich nie uruchomi
  4. `pending()` zwraca tylko `schema`, w kolejności manifestu, i uwzględnia już wykonane
  5. migracja `schema` jest addytywna i idempotentna (`IF NOT EXISTS`/`IF EXISTS`) albo świadomie oznaczona
  6. każdy skrypt `schema` da się uruchomić jako moduł (ma punkt wejścia), bo runner robi `python -m`
  7. nowa migracja bez wpisu w manifeście → wykryta (strażnik naprawdę łapie)

Użycie: cd backend && python -m scripts.test_migration_registry
"""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.migrate import pending
from scripts.migrations.manifest import BY_NAME, DATA, MANIFEST, SCHEMA, Migration

DIR = Path(__file__).parent / "migrations"
results: list[bool] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))
    return ok


def files_on_disk() -> set[str]:
    return {p.stem for p in DIR.glob("*.py") if p.name not in ("__init__.py", "manifest.py")}


def unregistered(files: set[str], manifest: list[Migration]) -> set[str]:
    return files - {m.name for m in manifest}


def main() -> int:
    print("\n1️⃣  Manifest ↔ katalog")
    files = files_on_disk()
    names = [m.name for m in MANIFEST]
    check(f"{len(files)} plików, {len(names)} wpisów", len(files) == len(names), f"{len(files)} vs {len(names)}")
    check("każdy plik ma wpis w manifeście", not unregistered(files, MANIFEST), ", ".join(sorted(unregistered(files, MANIFEST))))
    check("każdy wpis ma plik", not ({m.name for m in MANIFEST} - files), ", ".join(sorted({m.name for m in MANIFEST} - files)))
    check("nazwy unikalne", len(names) == len(set(names)))

    print("\n2️⃣  Rodzaje i kolejność")
    check("rodzaje tylko schema/data", all(m.kind in (SCHEMA, DATA) for m in MANIFEST))
    check("daty w porządku rosnącym (kolejność = kolejność dodania)",
          [m.date for m in MANIFEST] == sorted(m.date for m in MANIFEST))
    n_schema = sum(m.kind == SCHEMA for m in MANIFEST)
    check(f"{n_schema} migracji schematu, {len(MANIFEST) - n_schema} ręcznych (data)", n_schema >= 40)

    print("\n3️⃣  Skrypty `data` nie są uruchamiane przez runner")
    dangerous = {"clean_database", "remove_duplicate_events", "disable_risky_sources",
                 "ceidg_usun_kontakt_rejestrowy", "strip_apify_key_from_sources", "normalize_ceidg_casing"}
    check("skrypty niszczące/zmieniające dane mają rodzaj `data`",
          all(BY_NAME[n].kind == DATA for n in dangerous), str([n for n in dangerous if BY_NAME[n].kind != DATA]))
    check("pending(pusta baza) nie zawiera ani jednego `data`",
          all(m.kind == SCHEMA for m in pending(set())))
    check("pending(pusta baza) = wszystkie `schema` w kolejności manifestu",
          [m.name for m in pending(set())] == [m.name for m in MANIFEST if m.kind == SCHEMA])

    print("\n4️⃣  pending()")
    first = next(m.name for m in MANIFEST if m.kind == SCHEMA)
    last = [m.name for m in MANIFEST if m.kind == SCHEMA][-1]
    done = {m.name for m in MANIFEST if m.kind == SCHEMA} - {last}
    check("baza ze wszystkim oprócz ostatniej → czeka dokładnie ostatnia", [m.name for m in pending(done)] == [last])
    check("baza kompletna → nic nie czeka", pending({m.name for m in MANIFEST if m.kind == SCHEMA}) == [])
    check("wpis `data` w rejestrze nic nie psuje", pending(done | {"clean_database"}) == [BY_NAME[last]])
    check("pending zachowuje kolejność manifestu", [m.name for m in pending({first})][0] != first)

    print("\n5️⃣  Idempotencja skryptów schematu")
    # Starsze skrypty (sprzed rejestru) nie zawsze mają IF NOT EXISTS — to dług, nie błąd; BASELINE
    # oznacza je jako wykonane, więc ich ponowne uruchomienie nie grozi. Wymagamy tego od NOWYCH.
    legacy_without_guard = {"add_admin_and_moderation", "add_business_impressions", "add_event_unique_constraint",
                            "add_gus_database_first_tables", "add_health_tables", "add_user_consents"}
    unguarded = []
    for m in MANIFEST:
        if m.kind != SCHEMA or m.name in legacy_without_guard:
            continue
        src = (DIR / f"{m.name}.py").read_text(encoding="utf-8")
        if not re.search(r"IF NOT EXISTS|IF EXISTS|ON CONFLICT|WHERE NOT EXISTS|create_all|checkfirst|ALTER COLUMN \S+ TYPE|bez zmian", src, re.I):
            unguarded.append(m.name)
    check("każda migracja schematu poza listą historyczną ma zabezpieczenie idempotencji", not unguarded, ", ".join(unguarded))
    check("lista historycznych wyjątków się nie rozrasta (6)", len(legacy_without_guard) == 6)

    print("\n6️⃣  Punkt wejścia (runner robi `python -m scripts.migrations.<nazwa>`)")
    no_entry = []
    for m in MANIFEST:
        if m.kind != SCHEMA:
            continue
        tree = ast.parse((DIR / f"{m.name}.py").read_text(encoding="utf-8"))
        has_main_guard = any(
            isinstance(n, ast.If) and "__name__" in ast.dump(n.test) for n in tree.body
        )
        if not has_main_guard:
            no_entry.append(m.name)
    check("każda migracja schematu ma blok `if __name__ == \"__main__\"`", not no_entry, ", ".join(no_entry))

    print("\n7️⃣  Strażnik łapie zapomnianą migrację")
    check("nowy plik bez wpisu w manifeście → wykryty", unregistered(files | {"add_nowa_rzecz"}, MANIFEST) == {"add_nowa_rzecz"})

    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
