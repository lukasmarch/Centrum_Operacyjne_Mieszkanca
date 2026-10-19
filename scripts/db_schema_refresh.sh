#!/bin/bash
# Odświeża backend/scripts/schema/prod_schema.sql — STRUKTURĘ bazy produkcyjnej (bez danych).
#
# Po co (audyt 10–11.10.2026, E5): jedynym źródłem prawdy o schemacie była żywa produkcja.
# Modele znają 42 z 52 tabel, `create_all` buduje inną bazę, `alembic_version` stoi od lutego.
# Ten plik jest drugim punktem odniesienia: test `test_schema_contract` (w CI) pilnuje, żeby
# kod nie wymagał kolumny, której produkcja jeszcze nie ma — czyli „migracja PRZED kodem”.
#
# Produkcja: WYŁĄCZNIE odczyt (pg_dump -s przez SSH).
#
# Użycie (z korzenia projektu):
#   bash scripts/db_schema_refresh.sh           # nadpisz plik w repo aktualną strukturą produkcji
#   bash scripts/db_schema_refresh.sh --check   # tylko porównaj; kod wyjścia 1 = repo nie nadąża za produkcją
#
# Kiedy odświeżyć: PO każdej migracji wykonanej na produkcji, przed commitem kodu, który jej używa.
set -euo pipefail

PROD_HOST="root@91.99.142.30"
PROD_CONTAINER="centrum-db-1"
DB="centrum_operacyjne"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/backend/scripts/schema/prod_schema.sql"
MODE="write"; [[ "${1:-}" == "--check" ]] && MODE="check"

generate() {
  cat <<'HDR'
-- Struktura bazy PRODUKCYJNEJ (pg_dump -s, bez danych) — plik GENEROWANY, nie edytuj ręcznie.
-- Odśwież: bash scripts/db_schema_refresh.sh   |   porównaj z produkcją: ... --check
-- Pilnuje go backend/scripts/test_schema_contract.py (CI). Opis: CLAUDE.md, „Wyrównanie baz”.
HDR
  # Usuwamy to, co zmienia się przy każdym zrzucie bez zmiany schematu:
  # losowy token `\restrict`/`\unrestrict` (pg_dump ≥16.10) i wersje narzędzi w komentarzu.
  ssh -o ConnectTimeout=15 "$PROD_HOST" \
    "docker exec $PROD_CONTAINER sh -c 'pg_dump -U \"\$POSTGRES_USER\" -d $DB -s --no-owner --no-acl'" \
    | grep -v -E '^\\(un)?restrict ' | grep -v -E '^-- Dumped (from|by) '
}

TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
generate > "$TMP"

# Pusty albo okrojony zrzut (błąd SSH/Dockera) nie może zastąpić dobrego pliku.
N=$(grep -c '^CREATE TABLE public\.' "$TMP" || true)
[[ "$N" -ge 40 ]] || { echo "STOP: w zrzucie tylko $N tabel — plik w repo nietknięty."; exit 1; }

if [[ "$MODE" == "check" ]]; then
  if diff -u "$OUT" "$TMP" > /tmp/schema_diff.txt; then
    echo "✓ prod_schema.sql zgodny z produkcją ($N tabel)."
  else
    echo "✗ Produkcja różni się od prod_schema.sql:"; head -60 /tmp/schema_diff.txt
    echo; echo "Odśwież: bash scripts/db_schema_refresh.sh (jeśli zmiana na produkcji jest zamierzona)."
    exit 1
  fi
else
  cp "$TMP" "$OUT"
  echo "Zapisano $OUT ($N tabel, $(wc -l < "$OUT") linii)."
fi
