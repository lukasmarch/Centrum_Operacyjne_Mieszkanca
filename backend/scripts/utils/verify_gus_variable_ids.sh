#!/bin/bash
# Weryfikacja Variable IDs dla API GUS BDL
# Uruchom: bash scripts/utils/verify_gus_variable_ids.sh

echo "=============================================="
echo "Weryfikacja Variable IDs - API GUS BDL"
echo "=============================================="
echo ""

echo "🔍 1. Ludność ogółem"
curl -s "https://bdl.stat.gov.pl/api/v1/variables/search?name=Ludność%20ogółem&page_size=5" | python3 -m json.tool | grep -A 2 '"id"'
echo ""

echo "🔍 2. Stopa bezrobocia"
curl -s "https://bdl.stat.gov.pl/api/v1/variables/search?name=Stopa%20bezrobocia&page_size=5" | python3 -m json.tool | grep -A 2 '"id"'
echo ""

echo "🔍 3. Bezrobotni zarejestrowani"
curl -s "https://bdl.stat.gov.pl/api/v1/variables/search?name=Bezrobotni%20zarejestrowani&page_size=5" | python3 -m json.tool | grep -A 2 '"id"'
echo ""

echo "🔍 4. Przeciętne wynagrodzenie"
curl -s "https://bdl.stat.gov.pl/api/v1/variables/search?name=Przeciętne%20wynagrodzenie&page_size=5" | python3 -m json.tool | grep -A 2 '"id"'
echo ""

echo "=============================================="
echo "✅ Weryfikacja zakończona"
echo "=============================================="
echo ""
echo "Porównaj ID z backend/src/integrations/gus_api.py"
echo "Aktualne ID w kodzie:"
echo "  - population_total: 72305"
echo "  - unemployment_rate: 60270"
echo "  - unemployed_count: 60252"
echo "  - avg_salary: 64428"
