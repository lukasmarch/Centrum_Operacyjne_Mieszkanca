# Enhanced GUS Dashboard - Testing Guide
**Data:** 2026-02-04

---

## Quick Start

### 1. Uruchom Backend
```bash
cd /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca
source .venv/bin/activate
cd backend
uvicorn src.api.main:app --reload --port 8000
```

### 2. Uruchom Frontend
```bash
cd /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca/frontend
npm run dev
```

**Frontend:** http://localhost:5173
**Backend API:** http://localhost:8000/docs

---

## Backend Tests

### Test 1: Integration Test
```bash
cd /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca
source .venv/bin/activate
python backend/scripts/test_enhanced_gus.py
```

**Expected output:**
```
✅ Total GUS variables: 36
✅ Free tier: 5 variables
✅ Premium tier: 21 variables
✅ Business tier: 36 variables
🎉 All tests passed!
```

### Test 2: API Endpoints (curl)

**A. Get variables list (Free user - no auth):**
```bash
curl http://localhost:8000/api/stats/variables/list | jq
```

**Expected:**
```json
{
  "user_tier": "free",
  "total_available": 5,
  "variables": {...},
  "by_category": {
    "demografia": [...],
    "przedsiebiorczosc": [...]
  },
  "tiers": {
    "free": {"count": 5, "price": "0 zł/mc"},
    "premium": {"count": 21, "price": "19 zł/mc"},
    "business": {"count": 36, "price": "99 zł/mc"}
  }
}
```

**B. Get single variable (Free):**
```bash
curl http://localhost:8000/api/stats/variable/population_total | jq
```

**Expected:** 200 OK + data

**C. Get single variable (Premium - no auth):**
```bash
curl http://localhost:8000/api/stats/variable/unemployment_rate | jq
```

**Expected:** 403 Forbidden
```json
{
  "detail": "This variable requires premium subscription"
}
```

**D. Get categories:**
```bash
curl http://localhost:8000/api/stats/categories | jq
```

**Expected:**
```json
{
  "user_tier": "free",
  "categories": {
    "demografia": {
      "name": "Demografia",
      "count": 2,
      "icon": "👥",
      "variables": [...]
    },
    ...
  }
}
```

---

## Frontend Tests (Manual)

### Test 1: Free User (No Login)

**Steps:**
1. Otwórz http://localhost:5173
2. Przejdź do strony GUS (jeśli jest w menu)
3. Sprawdź:

**Expected:**
- ✅ Header pokazuje: "Dostępnych: 5 wskaźników (free)"
- ✅ Category navigation: widoczne 2 kategorie (Demografia, Przedsiębiorczość)
- ✅ Variable selector: 5 zmiennych total
- ✅ Premium upsell card: widoczny, gradient blue→purple
- ✅ Tier info footer: Free plan highlighted (border-2 border-blue-500)

**Test selection:**
1. Wybierz "Ludność ogółem" → powinno załadować dane ✅
2. Spróbuj kliknąć inną kategorię (jeśli dostępna) → powinna się zablokować (nie widoczna)

---

### Test 2: Premium User (Mock)

**Setup:**
Musisz się zalogować jako user z `tier: "premium"`. Jeśli nie masz takiego usera:

```sql
-- W PostgreSQL
UPDATE users SET tier = 'premium' WHERE email = 'your@email.com';
```

**Steps:**
1. Zaloguj się
2. Przejdź do strony GUS

**Expected:**
- ✅ Header: "Dostępnych: 21 wskaźników (premium)"
- ✅ Category navigation: 5 kategorii widocznych
  - Demografia (5 vars)
  - Rynek Pracy (3 vars)
  - Przedsiębiorczość (8 vars)
  - Transport (3 vars)
  - Infrastruktura (2 vars)
- ✅ Business upsell card: widoczny (slate-900 bg)
- ✅ Premium upsell card: NIE widoczny
- ✅ Tier info footer: Premium plan highlighted

**Test premium features:**
1. Kliknij "Rynek Pracy" → powinny pokazać się 3 zmienne
2. Wybierz "Stopa bezrobocia" → powinno załadować dane ✅
3. Wybierz "Średnie wynagrodzenie" → powinno załadować dane ✅

---

### Test 3: Business User (Mock)

**Setup:**
```sql
UPDATE users SET tier = 'business' WHERE email = 'your@email.com';
```

**Steps:**
1. Zaloguj się
2. Przejdź do strony GUS

**Expected:**
- ✅ Header: "Dostępnych: 36 wskaźników (business)"
- ✅ Category navigation: 6 kategorii (+ Turystyka)
- ✅ BRAK upsell cards (ani Premium ani Business)
- ✅ Tier info footer: Business plan highlighted

**Test business features:**
1. Kliknij "Turystyka" → 1 zmienna (Noclegi/10k)
2. Wybierz dowolne zmienne → wszystkie powinny działać
3. (TODO) Multi-metric comparison endpoint

---

## Error Scenarios

### Scenario 1: Premium Paywall
**Steps:**
1. Jako Free user
2. Próba ręcznego wejścia na URL: `http://localhost:8000/api/stats/variable/unemployment_rate`

**Expected:**
```json
HTTP 403
{
  "detail": "This variable requires premium subscription"
}
```

**Frontend powinien wyświetlić:**
```
🔒 Premium Feature
Ten wskaźnik wymaga subskrypcji Premium lub Business.
```

---

### Scenario 2: Backend offline
**Steps:**
1. Zatrzymaj backend (Ctrl+C)
2. Odśwież stronę GUS

**Expected:**
```
⚠️ Błąd
Nie udało się pobrać danych. Sprawdź czy backend jest uruchomiony.
```

---

### Scenario 3: Invalid variable
**Steps:**
```bash
curl http://localhost:8000/api/stats/variable/invalid_var
```

**Expected:**
```json
HTTP 404
{
  "detail": "Unknown variable key: invalid_var"
}
```

---

## Visual Checks

### Free User UI
```
[Header: "Dane GUS – Gmina Rybno"]
[Subheader: "Dostępnych: 5 wskaźników (free)"]

[Category Navigation: Demografia | Przedsiębiorczość]

[Variable Selector: 5 buttons in grid]

[💙 Premium Upsell Card - Gradient Blue→Purple]
🔓 Odblokuj 17+ wskaźników Premium
✓ Stopa bezrobocia i średnie wynagrodzenie
✓ Analiza przedsiębiorczości (MŚP, duże firmy)
...
[Przejdź na Premium (19 zł/mc) →]

[Main Stats Card - Emerald gradient]
[Charts - Trend + Comparison]
[Data Table]

[Tier Info Footer]
🆓 Free (highlighted)  ⭐ Premium  💎 Business
```

### Premium User UI
```
[Header: "Dostępnych: 21 wskaźników (premium)"]

[Category Navigation: 5 tabs]

[Variable Selector: 21 variables grouped]

[⚫ Business Upsell Card - Slate-900]
💎 Upgrade do Business
✓ Multi-metric comparison
✓ Eksport danych (Excel, CSV)
...
[Przejdź na Business (99 zł/mc) →]

[Charts...]
[Tier Info Footer - Premium highlighted]
```

### Business User UI
```
[Header: "Dostępnych: 36 wskaźników (business)"]

[Category Navigation: 6 tabs (+ Turystyka)]

[Variable Selector: 36 variables]

[NO UPSELL CARDS]

[Charts...]
[Tier Info Footer - Business highlighted]
```

---

## Performance Checks

### Backend
```bash
# Test response time
time curl -s http://localhost:8000/api/stats/variables/list > /dev/null
```
**Expected:** < 50ms (in-memory, no DB)

```bash
time curl -s http://localhost:8000/api/stats/variable/population_total > /dev/null
```
**Expected:** < 500ms (GUS API call)

---

### Frontend
Open DevTools → Network tab:

**Expected requests:**
1. `/api/stats/variables/list` - once on mount
2. `/api/stats/variable/{var_key}` - on variable change
3. `/api/stats/trend/{var_id}` - on variable change
4. `/api/stats/comparison/{var_id}` - on variable change

**Total load time:** < 2s for initial page load

---

## Regression Tests

### Test 4: Backward Compatibility
**Old endpoints should still work:**

```bash
curl http://localhost:8000/api/stats/trend/60530?years_back=22 | jq
curl http://localhost:8000/api/stats/comparison/60530 | jq
```

**Expected:** 200 OK + data (same format as before)

---

### Test 5: Database Schema
```sql
-- Check table exists
SELECT * FROM gus_gmina_stats LIMIT 1;
```

**Expected:** Table exists, no errors

---

## Known Issues

1. **`unemployment_rate` returns null** (seen in test)
   - GUS API response has 0 records
   - Possibly wrong var_id or no data for Gmina Rybno
   - **Fix:** Use Powiat-level data instead (UNIT_ID_POWIAT)

2. **Frontend uses old var_id extraction logic**
   - Line 99-104: `const varId = Object.entries(variablesData.variables).find([k]) => k === varKey)?.[1];`
   - This gets metadata object, not var_id
   - **Fix needed:** Extract from GUSDataService.VARS or add var_id to metadata

---

## Success Criteria

- [x] Backend test passes (all 6 tests)
- [ ] Free user sees 5 variables
- [ ] Premium user sees 21 variables
- [ ] Business user sees 36 variables
- [ ] Paywall works (403 → error message)
- [ ] Upsells show for correct tiers
- [ ] Category navigation works
- [ ] Variable selection updates charts
- [ ] No console errors
- [ ] Response times acceptable

---

## Next Steps After Testing

1. Fix any bugs found
2. Commit to `develop`:
   ```bash
   git add .
   git commit -m "feat: Enhanced GUS Dashboard - tier-based access"
   git push origin develop
   ```
3. Create PR to `main` (if ready for production)
4. Monitor metrics (30 days)

---

**Status:** ✅ Ready for testing
**Last updated:** 2026-02-04
