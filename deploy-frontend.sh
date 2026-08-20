#!/bin/bash
# Deploy frontendu na VPS
# Użycie: ./deploy-frontend.sh <VPS_IP> [--yes]
#
# ⚠️ TEN SKRYPT WYPUSZCZA CAŁE DRZEWO ROBOCZE, nie „ostatnią zmianę".
#
# 20.08.2026: deploy uruchomiony po drobnej poprawce profilu wypchnął na produkcję
# przebudowę strony głównej (`c9d18cf`), która leżała w `main` od 12.08 niewdrożona.
# Front jedzie ręcznie, więc `main` potrafi wyprzedzać produkcję o tygodnie, a build
# nie pyta, co jeszcze zabiera po drodze.
#
# Dlatego przed wysyłką skrypt porównuje commit stojący NA PRODUKCJI (znacznik
# `.deployed-commit` w wolumenie) z bieżącym HEAD i wypisuje wszystko, co wyjdzie.
# Bez `--yes` czeka na świadome potwierdzenie.

set -e

VPS_IP="${1:?Podaj IP VPS: ./deploy-frontend.sh <IP> [--yes]}"
AUTO_YES="${2:-}"
VPS_USER="root"
MARKER="/srv/frontend/.deployed-commit"

HEAD_SHA="$(git rev-parse HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "════════════════════════════════════════════════════════════"
echo "  DEPLOY FRONTU  →  ${VPS_IP}"
echo "════════════════════════════════════════════════════════════"
echo "  gałąź:  ${BRANCH}"
echo "  commit: ${HEAD_SHA:0:9}  $(git log -1 --format=%s | cut -c1-60)"
echo

# Co stoi na produkcji? Znacznik zakłada ten skrypt; przy pierwszym użyciu go nie ma.
DEPLOYED_SHA="$(ssh ${VPS_USER}@${VPS_IP} "docker run --rm -v centrum_frontend_dist:/srv/frontend:ro alpine sh -c 'cat ${MARKER} 2>/dev/null || true'" | tr -d '[:space:]')"

if [ -z "$DEPLOYED_SHA" ]; then
  echo "  ⚠️  Na produkcji nie ma znacznika wersji (pierwszy deploy tym skryptem)."
  echo "      Nie wiem, co tam stoi — sprawdź stronę po wdrożeniu."
  echo
else
  echo "  na produkcji stoi: ${DEPLOYED_SHA:0:9}"
  if [ "$DEPLOYED_SHA" = "$HEAD_SHA" ]; then
    echo "  ✓ To ten sam commit — wychodzą tylko niezacommitowane zmiany (jeśli są)."
    echo
  else
    echo
    echo "  ── COMMITY FRONTU, KTÓRE TERAZ WYJDĄ ─────────────────────"
    git log --oneline "${DEPLOYED_SHA}..HEAD" -- frontend/ 2>/dev/null | sed 's/^/     /' \
      || echo "     (nie znam commitu z produkcji — pokazuję 10 ostatnich)"
    echo "  ──────────────────────────────────────────────────────────"
    echo
  fi
fi

# Niezacommitowane zmiany też jadą — łatwo o tym zapomnieć
DIRTY="$(git status --porcelain -- frontend/ | head -10)"
if [ -n "$DIRTY" ]; then
  echo "  ⚠️  Niezacommitowane zmiany w frontend/ (też wyjdą):"
  echo "$DIRTY" | sed 's/^/     /'
  echo
fi

if [ "$AUTO_YES" != "--yes" ]; then
  printf "  Wypuścić to na https://rybnolive.pl? [wpisz TAK]: "
  read -r ANSWER
  if [ "$ANSWER" != "TAK" ]; then
    echo "  Przerwane — nic nie zostało wysłane."
    exit 1
  fi
  echo
fi

echo "Budowanie frontendu..."
cd frontend
VITE_API_URL=https://api.rybnolive.pl/api npm run build
cd ..

# Znacznik jedzie razem z plikami — dzięki temu następny deploy wie, co zastał
echo "${HEAD_SHA}" > frontend/dist/.deployed-commit

echo "Kopiowanie na VPS..."
ssh ${VPS_USER}@${VPS_IP} "mkdir -p /tmp/frontend_dist"
rsync -avz --delete frontend/dist/ ${VPS_USER}@${VPS_IP}:/tmp/frontend_dist/

echo "Przenoszenie do Docker volume..."
# UWAGA: `cp -r` NIE usuwa plików, których już nie ma w buildzie — stare bundle
# zostają w wolumenie. Nieszkodliwe (index.html wskazuje nowy), ale przy rollbacku
# nie licz na to, że stara wersja zniknęła.
ssh ${VPS_USER}@${VPS_IP} "
  cd /opt/centrum
  docker run --rm \
    -v centrum_frontend_dist:/srv/frontend \
    -v /tmp/frontend_dist:/src:ro \
    alpine sh -c 'cp -r /src/. /srv/frontend/'
  echo 'Frontend zaktualizowany'
"

echo "Gotowe! https://rybnolive.pl  (wersja ${HEAD_SHA:0:9})"
