#!/bin/bash
# Skrypt pomocniczy do uruchamiania sprawdzania bazy danych
# Używa pythona z wirtualnego środowiska (.venv)

# Ścieżka do katalogu projektu (zakładamy, że skrypt jest w backend/scripts)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Uruchomienie skryptu
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/backend/scripts/check_database.py" "$@"
