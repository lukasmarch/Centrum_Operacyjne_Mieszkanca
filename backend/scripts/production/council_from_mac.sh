#!/bin/bash
# Skrót sesji Rady z MacBooka — bez człowieka przy komputerze (2026-09-29).
#
# Dlaczego z MacBooka: YouTube odpowiada serwerowi bot-checkiem (IP Hetznera),
# więc `council_job` na produkcji widzi sesję, ale nie pobierze nagrania.
# Łącze domowe przechodzi. Ten skrypt robi to, co job, tylko pobieranie
# i Whisper idą stąd, a zapis do kolejki — w kontenerze (poświadczenia bazy
# nie opuszczają serwera). Do czasu proxy dla serwera.
#
# Pętla: od START do STOP co INTERVAL sekund sprawdza, czy nagranie jest gotowe.
# Gotowe → audio → Whisper → transkrypt na serwer → `--save` → Telegram z linkiem
# do akceptacji (ta sama wiadomość co z joba). Porażkę też zgłasza Telegramem.
#
# Uruchomienie (MacBook na ładowarce, klapa otwarta):
#   nohup caffeinate -ims backend/scripts/production/council_from_mac.sh \
#       > ~/Library/Logs/rybnolive_sesja.log 2>&1 &
# Zmienne: VIDEO, NAME, START/STOP („RRRR-MM-DD GG:MM"), INTERVAL, DRY=1
# (DRY: sprawdza gotowość, pobiera audio i test Telegramu — bez Whispera i zapisu).
set -u

VIDEO="${VIDEO:-quyYDnXDBEY}"
NAME="${NAME:-sesja_7598}"
START="${START:-2026-09-30 12:00}"
STOP="${STOP:-2026-09-30 23:00}"
INTERVAL="${INTERVAL:-900}"
MAX_FAILS="${MAX_FAILS:-3}"
DRY="${DRY:-0}"
SERVER="${SERVER:-root@91.99.142.30}"
CONTAINER="centrum-backend-1"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKEND="$ROOT/backend"
WORK="$BACKEND/data/council"
URL="https://www.youtube.com/watch?v=$VIDEO"

# nvm nie jest w PATH procesu w tle; yt-dlp z ~/.local/bin (nowszy niż w .venv)
NODE_BIN="$(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | tail -1)"
# ⚠️ PO aktywacji venv — ona dokleja na początek `.venv/bin`, gdzie leży stary
# yt-dlp (2025.10, bez `--js-runtimes`). Złapane próbą 29.09.
source "$ROOT/.venv/bin/activate"
export PATH="$HOME/.local/bin:${NODE_BIN}:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$BACKEND" || exit 1

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }
epoch() { date -j -f "%Y-%m-%d %H:%M" "$1" +%s; }

# Telegram przez kontener — token zostaje na serwerze.
tg() {
  printf %s "$1" | ssh -o BatchMode=yes -o ConnectTimeout=20 "$SERVER" \
    "docker exec -i $CONTAINER python -c 'import sys,httpx
from src.config import settings as s
httpx.post(f\"https://api.telegram.org/bot{s.TELEGRAM_BOT_TOKEN}/sendMessage\",json={\"chat_id\":s.TELEGRAM_CHAT_ID,\"text\":sys.stdin.read()},timeout=20).raise_for_status()'" \
    >/dev/null 2>&1 || log "Telegram nie przyjął wiadomości: $1"
}

# Krok z zapamiętaną przyczyną porażki — trafia do ostrzeżenia na Telegram.
# 30.09 alert mówił tylko „zajrzyj do logu", a log leży na MacBooku, do którego
# z telefonu nie ma dostępu. Przyczyna = ostatnia linia błędu (dla wyjątku
# Pythona to linia z typem i treścią, np. RateLimitError … credit_balance_exhausted).
LAST_ERROR=""
run_step() {
  local what="$1"; shift
  local out; out="$(mktemp -t council_step)"
  "$@" 2>&1 | grep -v Deprecat | tee "$out"
  local rc="${PIPESTATUS[0]}"
  if [ "$rc" != "0" ]; then
    LAST_ERROR="$what: $(grep -v '^[[:space:]]*$' "$out" | tail -1 | cut -c1-300)"
    log "Nie wyszło — $LAST_ERROR"
  fi
  rm -f "$out"
  return "$rc"
}

# 0 = gotowe do pobrania, 2 = jeszcze nie (zapowiedź/trwa/VOD w obróbce), 1 = błąd
readiness() {
  python -u -c "
import sys
from src.services.council_transcript import video_metadata, not_ready_reason
m = video_metadata('$URL')
r = not_ready_reason(m)
print(m['live_status'], m['duration_s'], r or 'GOTOWE')
sys.exit(2 if r else 0)
" 2>&1 | grep -v Deprecat
  return "${PIPESTATUS[0]}"
}

process() {
  if [ "$DRY" = "1" ]; then
    python -u -c "
from pathlib import Path
from src.services.council_transcript import download_audio
p = download_audio('$URL', Path('/tmp/council_dry'), name='dry')
print('DRY audio', round(p.stat().st_size/1e6,1), 'MB')
" 2>&1 | grep -v Deprecat || return 1
    rm -rf /tmp/council_dry
    ssh -o BatchMode=yes "$SERVER" "docker exec $CONTAINER python -m scripts.run_council_session --help >/dev/null && echo DRY kontener OK" || return 1
    return 0
  fi

  # Transkrypt już jest (poprzednia próba zapłaciła za Whisper i padła dalej)
  # → nie liczymy go drugi raz. 30.09 ponowne próby startowały od zera; padły
  # na braku kredytów od razu, ale przy innym błędzie każda to kolejne $1,10.
  if [ -s "$WORK/$NAME.transcript.json" ]; then
    log "Transkrypt już jest — Whisper pominięty"
  else
    # Audio i 13 kawałków mp3 w katalogu tymczasowym, nie w data/council.
    TMP_WORK="$(mktemp -d -t council)"
    run_step "Transkrypcja (Whisper)" python -u -m scripts.run_council_session \
        --url "$URL" --name "$NAME" --work-dir "$TMP_WORK" --transcript-only \
      || { rm -rf "$TMP_WORK"; return 1; }
    [ -s "$TMP_WORK/$NAME.transcript.json" ] || { LAST_ERROR="brak pliku transkryptu"; rm -rf "$TMP_WORK"; return 1; }
    mkdir -p "$WORK" && mv "$TMP_WORK/$NAME.transcript.json" "$WORK/" && rm -rf "$TMP_WORK"
  fi

  # Skrót powstaje wyłącznie na serwerze — raz, tam gdzie jest zapisywany.
  run_step "Wysłanie transkryptu" scp -o BatchMode=yes "$WORK/$NAME.transcript.json" "$SERVER:/tmp/" || return 1
  run_step "Skrót i zapis (serwer)" ssh -o BatchMode=yes "$SERVER" "docker cp /tmp/$NAME.transcript.json $CONTAINER:/tmp/ \
    && docker exec $CONTAINER python -u -m scripts.run_council_session \
         --transcript /tmp/$NAME.transcript.json --name $NAME --work-dir /tmp/council_out --save" || return 1

  # Pliki skrótu wracają na MacBooka — z nich druga sesja robi rolkę.
  ssh -o BatchMode=yes "$SERVER" "docker cp $CONTAINER:/tmp/council_out/$NAME.skrot.md /tmp/ \
    && docker cp $CONTAINER:/tmp/council_out/$NAME.transcript.txt /tmp/" \
    && scp -q -o BatchMode=yes "$SERVER:/tmp/$NAME.skrot.md" "$SERVER:/tmp/$NAME.transcript.txt" "$WORK/" \
    || log "Nie skopiowałem plików skrótu na MacBooka (skrót i tak czeka na akceptację)"

  # To samo powiadomienie co z joba: skrót, punkty, przycisk do akceptacji.
  run_step "Powiadomienie" ssh -o BatchMode=yes "$SERVER" "docker exec $CONTAINER python -c '
import asyncio
from sqlmodel import select
from src.database.connection import async_session
from src.database.schema import CouncilSession
from src.scheduler.council_job import _notify_admin
async def main():
    async with async_session() as s:
        row = (await s.execute(select(CouncilSession).where(CouncilSession.youtube_id == \"$VIDEO\"))).scalars().first()
        _notify_admin(row)
asyncio.run(main())
'" || return 1
  return 0
}

START_E=$(epoch "$START"); STOP_E=$(epoch "$STOP")
log "Start: $URL, okno $START – $STOP, co ${INTERVAL}s, DRY=$DRY"
[ "$DRY" = "1" ] && START_E=0
fails=0
while [ "$(date +%s)" -lt "$STOP_E" ]; do
  if [ "$(date +%s)" -lt "$START_E" ]; then
    sleep 300; continue
  fi
  log "Sprawdzam nagranie…"
  readiness; rc=$?
  if [ "$rc" = "0" ]; then
    log "Nagranie gotowe — przetwarzam"
    if process; then
      log "GOTOWE"
      [ "$DRY" = "1" ] && tg "🧪 Test automatu sesji z MacBooka: pobranie audio i dostęp do kontenera działają. Jutro skrót przyjdzie sam."
      exit 0
    fi
    fails=$((fails + 1))
    log "Porażka $fails/$MAX_FAILS"
    if [ "$fails" -ge "$MAX_FAILS" ]; then
      tg "⚠️ Automat sesji z MacBooka: $MAX_FAILS nieudane próby dla $URL.

Przyczyna: ${LAST_ERROR:-nieznana}
$([ -s "$WORK/$NAME.transcript.json" ] && echo "
Transkrypt jest zapisany — kolejna próba nie zapłaci za Whisper.")
Log: ~/Library/Logs/rybnolive_sesja.log"
      exit 1
    fi
  elif [ "$rc" = "1" ]; then
    log "Błąd odczytu metadanych"
  fi
  sleep "$INTERVAL"
done
tg "⚠️ Automat sesji z MacBooka: do $STOP nagranie $URL nie było gotowe do pobrania. Skrótu nie ma."
log "Koniec okna bez nagrania"
exit 1
