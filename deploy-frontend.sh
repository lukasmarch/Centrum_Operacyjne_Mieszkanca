#!/bin/bash
# Deploy frontendu na VPS
# Użycie: ./deploy-frontend.sh <VPS_IP>

set -e

VPS_IP="${1:?Podaj IP VPS: ./deploy-frontend.sh <IP>}"
VPS_USER="root"

echo "Budowanie frontendu..."
cd frontend
VITE_API_URL=https://api.rybnolive.pl/api npm run build
cd ..

echo "Kopiowanie na VPS..."
# Tymczasowy katalog na VPS
ssh ${VPS_USER}@${VPS_IP} "mkdir -p /tmp/frontend_dist"
rsync -avz --delete frontend/dist/ ${VPS_USER}@${VPS_IP}:/tmp/frontend_dist/

echo "Przenoszenie do Docker volume..."
ssh ${VPS_USER}@${VPS_IP} "
  cd /opt/centrum
  # Kopiuj dist do volume przez pomocniczy kontener
  docker run --rm \
    -v centrum_frontend_dist:/srv/frontend \
    -v /tmp/frontend_dist:/src:ro \
    alpine sh -c 'cp -r /src/. /srv/frontend/'
  echo 'Frontend zaktualizowany'
"

echo "Gotowe! https://rybnolive.pl"
