#!/bin/bash
# Synchronizacja: baza PRODUKCYJNA → lokalna baza głównego projektu (backend-postgres-1).
# Ten sam zrzut zasila potem bazę audytową (moj-projekt-audyt, :5434).
#
# Bezpieczeństwo:
#   - produkcja: WYŁĄCZNIE odczyt (pg_dump). Nic nie jest zapisywane na serwerze.
#   - push_subscriptions bez danych — adresy urządzeń nie opuszczają serwera.
#   - lokalnie zrzut ląduje najpierw w bazie TYMCZASOWEJ; obecna lokalna baza zostaje nietknięta,
#     dopóki nie zobaczysz różnic schematu i nie potwierdzisz zamiany (--tak).
#   - po zamianie stara baza zostaje jako centrum_operacyjne_przed_sync → --przywroc cofa w sekundę.
#   - dane osobowe są domyślnie ANONIMIZOWANE: lokalny backend/.env ma klucze Resend i VAPID,
#     więc prawdziwe adresy w lokalnej bazie = ryzyko prawdziwego maila wysłanego z MacBooka.
#   - zrzuty w ~/rybnolive-zrzuty (poza Desktopem, który bywa synchronizowany z iCloud),
#     uprawnienia 600, trzymane są 2 ostatnie.
#
# Użycie (z korzenia głównego projektu):
#   bash scripts/sync_prod_do_lokalnej.sh            # 1) zrzut + baza tymczasowa + różnice schematu (bez zamiany)
#   bash scripts/sync_prod_do_lokalnej.sh --tak      # 2) zamiana gotowej bazy tymczasowej (albo zrzut + zamiana)
#   bash scripts/sync_prod_do_lokalnej.sh --przywroc # cofnięcie ostatniej zamiany
#   ... --prawdziwe-dane                             # bez anonimizacji (świadomie; patrz wyżej)
#
# Baza audytowa z tego samego zrzutu:
#   ZRZUT=~/rybnolive-zrzuty/<plik>.pgc bash ~/Desktop/moj-projekt-audyt/scripts/audyt/przygotuj_srodowisko.sh --force
set -euo pipefail

PROD_HOST="root@91.99.142.30"
PROD_CONTAINER="centrum-db-1"
LOCAL_CONTAINER="backend-postgres-1"
DB="centrum_operacyjne"
TMP_DB="${DB}_sync"
OLD_DB="${DB}_przed_sync"
DUMP_DIR="$HOME/rybnolive-zrzuty"
KEEP_DUMPS=2

TAK=0; PRZYWROC=0; ANON=1
for a in "$@"; do
  case "$a" in
    --tak) TAK=1 ;;
    --przywroc) PRZYWROC=1 ;;
    --prawdziwe-dane) ANON=0 ;;
    *) echo "Nieznana opcja: $a"; exit 1 ;;
  esac
done

lpsql() { docker exec -i "$LOCAL_CONTAINER" sh -c "psql -U \"\$POSTGRES_USER\" -v ON_ERROR_STOP=1 $*"; }
db_exists() { [[ "$(lpsql "-d postgres -tAc \"select count(*) from pg_database where datname='$1'\"")" == "1" ]]; }
kick() { lpsql "-d postgres -qtAc \"select pg_terminate_backend(pid) from pg_stat_activity where datname='$1' and pid<>pg_backend_pid()\"" >/dev/null; }

docker ps --format '{{.Names}}' | grep -qx "$LOCAL_CONTAINER" || { echo "STOP: kontener $LOCAL_CONTAINER nie działa (cd backend && docker compose up -d)."; exit 1; }

# ---------- cofnięcie ----------
if [[ $PRZYWROC == 1 ]]; then
  db_exists "$OLD_DB" || { echo "Brak $OLD_DB — nie ma czego przywracać."; exit 1; }
  echo "Przywracam $OLD_DB → $DB (bieżąca trafia do $TMP_DB)."
  kick "$DB"; kick "$OLD_DB"; kick "$TMP_DB"
  lpsql "-d postgres -c \"DROP DATABASE IF EXISTS $TMP_DB\" -c \"ALTER DATABASE $DB RENAME TO $TMP_DB\" -c \"ALTER DATABASE $OLD_DB RENAME TO $DB\""
  echo "Gotowe. Uruchom ponownie lokalny backend."
  exit 0
fi

# ---------- 1. zrzut produkcji (odczyt) ----------
mkdir -p "$DUMP_DIR"; chmod 700 "$DUMP_DIR"
if [[ $TAK == 1 ]] && db_exists "$TMP_DB"; then
  echo "== Baza tymczasowa $TMP_DB już przygotowana — pomijam ponowny zrzut."
else
  DUMP="$DUMP_DIR/prod-$(date '+%Y%m%d-%H%M').pgc"
  echo "== 1/4 pg_dump produkcji (tylko odczyt) → $DUMP"
  ssh -o ConnectTimeout=15 "$PROD_HOST" \
    "docker exec $PROD_CONTAINER sh -c 'pg_dump -U \"\$POSTGRES_USER\" -d $DB -Fc --no-owner --no-acl --exclude-table-data=push_subscriptions'" > "$DUMP"
  [[ -s "$DUMP" ]] || { echo "STOP: pusty zrzut — lokalna baza nietknięta."; rm -f "$DUMP"; exit 1; }
  chmod 600 "$DUMP"; ls -lh "$DUMP"
  ls -1t "$DUMP_DIR"/prod-*.pgc | tail -n +$((KEEP_DUMPS + 1)) | xargs -r rm -f

  # ---------- 2. baza tymczasowa ----------
  echo "== 2/4 Odtworzenie w bazie tymczasowej $TMP_DB (obecna $DB bez zmian)"
  kick "$TMP_DB"
  lpsql "-d postgres -c \"DROP DATABASE IF EXISTS $TMP_DB\" -c \"CREATE DATABASE $TMP_DB\""
  docker exec -i "$LOCAL_CONTAINER" sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $TMP_DB --no-owner --no-acl" < "$DUMP" \
    || echo "(pg_restore zgłosił ostrzeżenia — zwykle rozszerzenia; sprawdzam liczbę tabel)"
  N=$(lpsql "-d $TMP_DB -tAc \"select count(*) from information_schema.tables where table_schema='public'\"")
  [[ "$N" -ge 30 ]] || { echo "STOP: w bazie tymczasowej tylko $N tabel — coś poszło źle, $DB nietknięta."; exit 1; }
  echo "tabel: $N, ostatni artykuł: $(lpsql "-d $TMP_DB -tAc \"select max(published_at) from articles\"")"

  if [[ $ANON == 1 ]]; then
    echo "== 3/4 Anonimizacja (wyłącz: --prawdziwe-dane)"
    lpsql "-d $TMP_DB" <<'SQL'
UPDATE users SET email = 'u_'||left(md5(email),12)||'@lokalnie.invalid',
                 full_name = CASE WHEN full_name IS NULL THEN NULL ELSE '[zanonimizowano]' END,
                 password_hash = 'zanonimizowano-brak-logowania';
UPDATE newsletter_subscribers SET email = 'n_'||left(md5(email),12)||'@lokalnie.invalid',
                 confirmation_token = md5(random()::text), unsubscribe_token = md5(random()::text);
UPDATE reports SET author_email = CASE WHEN author_email IS NULL THEN NULL ELSE 'r_'||left(md5(author_email),12)||'@lokalnie.invalid' END,
                   author_name  = CASE WHEN author_name  IS NULL THEN NULL ELSE '[zanonimizowano]' END,
                   author_phone = CASE WHEN author_phone IS NULL THEN NULL ELSE '[zanonimizowano]' END,
                   address      = CASE WHEN address      IS NULL THEN NULL ELSE '[zanonimizowano]' END;
UPDATE business_claim_log SET admin_email = 'a_'||left(md5(admin_email),12)||'@lokalnie.invalid' WHERE admin_email IS NOT NULL;
UPDATE anonymous_chat_usage SET ip_address = '0.0.0.0' WHERE ip_address IS NOT NULL;
DELETE FROM push_subscriptions;
SQL
    echo "Konta lokalne: zarejestruj się na nowo (hasła i e-maile zanonimizowane). Admin: UPDATE users SET is_admin=true WHERE email='…'."
  else
    echo "== 3/4 BEZ anonimizacji — lokalny .env ma klucze Resend/VAPID: nie uruchamiaj jobów wysyłkowych!"
  fi
fi

# ---------- różnice schematu ----------
echo "== Różnice schematu: obecna lokalna ($DB) vs produkcja ($TMP_DB)"
Q="select table_name||'.'||column_name from information_schema.columns where table_schema='public' order by 1"
lpsql "-d $DB -tAc \"$Q\"" | sort > /tmp/sync_lokalna.txt
lpsql "-d $TMP_DB -tAc \"$Q\"" | sort > /tmp/sync_prod.txt
ONLY_LOCAL=$(comm -23 /tmp/sync_lokalna.txt /tmp/sync_prod.txt)
ONLY_PROD=$(comm -13 /tmp/sync_lokalna.txt /tmp/sync_prod.txt)
echo "-- przybędzie lokalnie (jest na produkcji): $(printf '%s' "$ONLY_PROD" | grep -c . || true)"
[[ -n "$ONLY_PROD" ]] && echo "$ONLY_PROD" | sed 's/^/   + /' | head -40
echo "-- ZNIKNIE lokalnie (tylko u Ciebie — kod czekający na wdrożenie): $(printf '%s' "$ONLY_LOCAL" | grep -c . || true)"
if [[ -n "$ONLY_LOCAL" ]]; then
  echo "$ONLY_LOCAL" | sed 's/^/   - /' | head -40
  echo "   ⚠️ Po zamianie uruchom ponownie migracje tych kolumn (cd backend && python -m scripts.migrations.<nazwa>)."
fi

if [[ $TAK == 0 ]]; then
  echo
  echo "Nic nie zamieniono. Obecna lokalna baza działa jak dotąd."
  echo "Zamiana: bash scripts/sync_prod_do_lokalnej.sh --tak   (zatrzymaj wcześniej lokalny backend)"
  exit 0
fi

# ---------- 4. zamiana ----------
echo "== 4/4 Zamiana: $DB → $OLD_DB, $TMP_DB → $DB"
kick "$DB"; kick "$TMP_DB"; kick "$OLD_DB"
lpsql "-d postgres -c \"DROP DATABASE IF EXISTS $OLD_DB\" -c \"ALTER DATABASE $DB RENAME TO $OLD_DB\" -c \"ALTER DATABASE $TMP_DB RENAME TO $DB\""
echo
echo "GOTOWE. Lokalna baza = produkcja, ostatni artykuł: $(lpsql "-d $DB -tAc \"select max(published_at) from articles\"")."
echo "Cofnięcie: bash scripts/sync_prod_do_lokalnej.sh --przywroc"
echo "Baza audytowa z tego zrzutu:"
echo "  ZRZUT=$(ls -1t "$DUMP_DIR"/prod-*.pgc | head -1) bash ~/Desktop/moj-projekt-audyt/scripts/audyt/przygotuj_srodowisko.sh --force"
