#!/bin/bash
# Odświeża backend/constraints.txt z działającego kontenera produkcji (pip freeze).
# Użycie: bash scripts/refresh_constraints.sh   (z katalogu backend/)
# Świadome odświeżenie = osobny commit + CI + deploy; nie wołać przy zwykłej pracy.
set -euo pipefail
ssh root@91.99.142.30 'docker exec centrum-backend-1 pip freeze' | grep '==' > constraints.txt
echo "constraints.txt: $(wc -l < constraints.txt) pakietów"
