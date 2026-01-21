# Plan Rozwoju: Centrum Operacyjne Mieszkańca

## Podsumowanie
Plan 6 sprintów (12 tygodni) transformujących projekt w pełnoprawne "Centrum Operacyjne" z systemem użytkowników, newsletterem, nowymi widgetami i monetyzacją Premium.

---

## Obecny Stan vs Cel

| Obszar | TERAZ | CEL |
|--------|-------|-----|
| Auth/Users | Brak | JWT + profile z miejscowością |
| Newsletter | Brak | Weekly (free) + Daily (premium) |
| Jakość powietrza | Brak | Widget GIOŚ (Gemini grounding) |
| Harmonogram śmieci | Brak | Widget per gmina |
| Płatności | Brak | Stripe (19 PLN/mies Premium) |
| Powiadomienia | Brak | Web Push + opcjonalnie SMS |

---

## Sprint 1: System Auth/Users (Tyg. 1-2)

### Backend
**Nowe tabele w `schema.py`:**
```python
class User(SQLModel, table=True):
    id: int (PK)
    email: str (unique)
    password_hash: str
    full_name: str
    location: str  # "Rybno", "Działdowo"
    tier: str  # "free", "premium", "business"
    preferences: dict (JSONB)
    created_at, last_login, email_verified

class Subscription(SQLModel, table=True):
    id: int (PK)
    user_id: int (FK)
    tier: str
    status: str  # "active", "cancelled"
    expires_at: datetime
```

**Nowe pliki:**
- `backend/src/auth/jwt.py` - JWT tokens (python-jose, passlib)
- `backend/src/auth/routes.py` - POST /register, /login, /logout
- `backend/src/users/routes.py` - GET /me, PUT /profile

### Frontend
**Nowe pliki:**
- `frontend/src/context/AuthContext.tsx`
- `frontend/pages/login.tsx`, `register.tsx`, `profile.tsx`
- Protected routes dla Premium

### Deliverables
- [ ] Rejestracja/logowanie działające
- [ ] Profil z wyborem miejscowości (dropdown: Rybno, Działdowo, Lubawa...)
- [ ] JWT w cookies

---

## Sprint 2: Newsletter Weekly (Tyg. 3-4)

### Backend
**Nowa tabela:**
```python
class NewsletterSubscriber(SQLModel, table=True):
    email: str (unique)
    user_id: int (FK, nullable)
    frequency: str  # "weekly", "daily"
    status: str  # "active", "unsubscribed"
```

**Nowe pliki:**
- `backend/src/newsletter/generator.py` - AI generowanie treści
- `backend/src/newsletter/templates/weekly.html`
- `backend/src/scheduler/newsletter_job.py`

**Scheduler:** Sobota 10:00
```python
CronTrigger(day_of_week='sat', hour=10)
```

### Struktura Newsletter Weekly (Free)
```
┌─────────────────────────────────────┐
│ 🗓️ Tydzień w Działdowie            │
├─────────────────────────────────────┤
│ 📰 TOP 5 WIADOMOŚCI TYGODNIA       │
│ (AI wybiera z articles)            │
├─────────────────────────────────────┤
│ 📅 WYDARZENIA NA WEEKEND            │
│ (auto z events table)              │
├─────────────────────────────────────┤
│ ☁️ PROGNOZA NA WEEKEND              │
│ (auto z weather)                   │
├─────────────────────────────────────┤
│ 💎 [ZOSTAŃ PREMIUM] →               │
└─────────────────────────────────────┘
```

### Email Provider
**Rekomendacja:** Resend (3000 emaili/mies free, nowoczesne API)
- `RESEND_API_KEY` w .env

### Deliverables
- [ ] Formularz zapisu (landing page)
- [ ] Automatyczna wysyłka sobota 10:00
- [ ] Strona unsubscribe
- [ ] AI generuje treść z daily_summaries + articles

---

## Sprint 3: Widget Jakości Powietrza (Tyg. 5-6)

### WAŻNE: Używamy Gemini CLI do zewnętrznych danych
Zamiast bezpośrednich requestów HTTP, używamy `gemini -p "pytanie"` z grounding:

**Przykład dla jakości powietrza:**
```bash
gemini -p "Podaj aktualną jakość powietrza dla Działdowa, Polska.
Zwróć dane: indeks jakości, PM2.5, PM10, porada dla mieszkańców."
```

**W kodzie Python:**
```python
# backend/src/integrations/air_quality_service.py
import subprocess
import json

async def fetch_air_quality(location: str) -> dict:
    """Pobiera jakość powietrza przez Gemini CLI z grounding"""
    prompt = f"Podaj aktualną jakość powietrza dla {location}, Polska. Zwróć JSON z polami: index_level, pm25, pm10, advice"

    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

**Zastosowania Gemini CLI w projekcie:**
- Jakość powietrza (GIOŚ dane)
- Harmonogramy śmieci (scraping stron gmin)
- Awarie prądu/wody (Energa, PGKiM)
- Ceny nieruchomości (OLX, Otodom)

### Backend
**Nowa tabela:**
```python
class AirQuality(SQLModel, table=True):
    id: int (PK)
    location: str
    index_level: str
    pm25_value: float
    pm10_value: float
    advice: str
    fetched_at: datetime
```

**Endpoint:** `GET /api/air-quality/{location}`

**Scheduler:** Co 30 min
```python
IntervalTrigger(minutes=30)
```

### Frontend
**Nowy komponent:** `AirQualityWidget.tsx`
- Kolorowy indeks (zielony/żółty/czerwony)
- PM2.5, PM10 wartości
- Porada AI ("Możesz wietrzyć" / "Zamknij okna")

### Deliverables
- [ ] Widget na dashboardzie
- [ ] Dane co 30 min (cache)
- [ ] Personalizacja per lokalizacja użytkownika

---

## Sprint 4: Płatności + Premium (Tyg. 7-8)

### Backend
**Nowe pliki:**
- `backend/src/payments/stripe_service.py`
- `backend/src/payments/routes.py`

**Endpointy:**
```
POST /api/payments/create-checkout
POST /api/payments/webhook
GET  /api/payments/subscription
POST /api/payments/cancel
```

**Stripe Setup:**
```env
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_PREMIUM=price_xxx  # 19 PLN/mies
```

### Frontend
**Nowe strony:**
- `/pricing` - cennik z 3 planami
- `/subscription` - zarządzanie subskrypcją

**Nowy komponent:** `PremiumGate.tsx`
```tsx
// Blokuje treść dla free users
<PremiumGate>
  <DailySummaryFull />
</PremiumGate>
```

### Premium Features
1. Daily Summary AI (pełna wersja)
2. Newsletter codzienny
3. Brak reklam (jeśli będą)
4. Alerty Push (Sprint 5)
5. Personalizacja kategorii

### Deliverables
- [ ] Stripe Checkout działa
- [ ] Webhook aktualizuje subscription
- [ ] Gating treści Premium
- [ ] Badge "Premium" w UI

---

## Sprint 5: Newsletter Daily + Push (Tyg. 9-10)

### Newsletter Daily (Premium)
**Scheduler:** Pon-Pt 6:30
```python
CronTrigger(day_of_week='mon-fri', hour=6, minute=30)
```

**Struktura:**
```
┌─────────────────────────────────────┐
│ ☀️ Dzień Dobry! (Pon, 12.01)        │
├─────────────────────────────────────┤
│ 🌡️ POGODA: 18°C | AQI: Dobry        │
├─────────────────────────────────────┤
│ 🚗 DOJAZD: Rybno→Działdowo 12 min   │
├─────────────────────────────────────┤
│ 🤖 AI PODSUMOWANIE                   │
│ 1. Spotkanie rady miasta (18:00)   │
│ 2. Awaria wody na ul. Lipowej      │
│ 3. Nowa oferta pracy w Urzędzie    │
├─────────────────────────────────────┤
│ 📅 DZIŚ: Dyżur apteki Pod Orłem    │
└─────────────────────────────────────┘
```

### Web Push Notifications
**Backend:**
- `backend/src/notifications/push_service.py`
- Biblioteka: `pywebpush`

**Nowa tabela:**
```python
class PushSubscription(SQLModel, table=True):
    user_id: int (FK)
    endpoint: str
    p256dh_key: str
    auth_key: str
```

**Typy alertów:**
- Krytyczne (awarie, smog >200%) - natychmiast
- Ważne (korki, pogoda) - wg preferencji
- Info (wydarzenia) - 1x/dzień max

### Deliverables
- [ ] Daily newsletter dla Premium
- [ ] Web Push subscription
- [ ] Panel preferencji powiadomień
- [ ] Service Worker na frontendzie

---

## Sprint 6: Widget Śmieci + Finalizacja (Tyg. 11-12)

### Harmonogram Śmieci
**Wyzwanie:** Dane są per gmina, często w PDF.

**Rozwiązanie:**
1. Manualna digitalizacja dla: Rybno, Działdowo
2. Kontakt z gminami o API/dane

**Nowa tabela:**
```python
class GarbageSchedule(SQLModel, table=True):
    location: str  # "Rybno", "Działdowo - Centrum"
    waste_type: str  # "mieszane", "segregowane", "bio"
    collection_date: date
```

**Endpoint:** `GET /api/garbage-schedule?location=Rybno`

### Frontend
**Nowy komponent:** `GarbageWidget.tsx`
- Najbliższa data odbioru
- Typ odpadu (ikona)
- Countdown ("Za 2 dni")
- Push reminder (dzień wcześniej)

### Finalizacja
- [ ] Code review całości
- [ ] Testy E2E (Playwright)
- [ ] Dokumentacja API (Swagger)
- [ ] Monitoring (Sentry)
- [ ] CI/CD pipeline

---

## Kluczowe Pliki do Modyfikacji

| Sprint | Plik | Zmiany |
|--------|------|--------|
| 1 | `backend/src/database/schema.py` | +User, +Subscription |
| 1 | `backend/src/api/main.py` | +auth router |
| 2 | `backend/src/scheduler/scheduler.py` | +newsletter_job |
| 3 | `backend/src/integrations/` | +air_quality_service.py |
| 4 | `backend/src/api/main.py` | +payments router |
| 5 | `frontend/components/Dashboard.tsx` | +AirQualityWidget |
| 6 | `frontend/components/Dashboard.tsx` | +GarbageWidget |

---

## Nowe Zmienne .env

```env
# Sprint 1: Auth
JWT_SECRET=your-secret-key-min-32-chars

# Sprint 2: Email
RESEND_API_KEY=re_xxx

# Sprint 4: Payments
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Sprint 5: Push
VAPID_PUBLIC_KEY=xxx
VAPID_PRIVATE_KEY=xxx
```

---

## Budżet Szacunkowy

| Usługa | Obecny | Po wdrożeniu |
|--------|--------|--------------|
| Infra | 100 PLN | 100 PLN |
| AI (OpenAI) | 65 PLN | 100 PLN |
| Email (Resend) | 0 | 0-85 PLN |
| **RAZEM** | ~580 PLN | ~500-700 PLN |

**Breakeven:** ~30 subskrybentów Premium (30 × 19 = 570 PLN)

---

## Weryfikacja (po każdym sprincie)

### Sprint 1
```bash
curl -X POST http://localhost:8000/api/auth/register -d '{"email":"test@test.pl","password":"xxx"}'
curl -X POST http://localhost:8000/api/auth/login -d '{"email":"test@test.pl","password":"xxx"}'
```

### Sprint 2
- Sprawdź email w skrzynce po uruchomieniu joba ręcznie

### Sprint 3
```bash
curl http://localhost:8000/api/air-quality/Rybno
```

### Sprint 4
- Test Stripe Checkout (tryb testowy)
- Webhook test przez Stripe CLI

### Sprint 5
- Subskrybuj push w przeglądarce
- Wyślij testowe powiadomienie

### Sprint 6
```bash
curl http://localhost:8000/api/garbage-schedule?location=Rybno
```

---

## Priorytety (MoSCoW)

**MUST:** Sprint 1 (Auth), Sprint 2 (Newsletter)
**SHOULD:** Sprint 3 (Air Quality)
**COULD:** Sprint 4 (Payments), Sprint 5 (Push)
**WON'T (teraz):** Sprint 6 (Garbage) - odłożone

---

## Decyzje Podjęte

| Kwestia | Decyzja |
|---------|---------|
| Start | Sprint 1: Auth/Users |
| Email provider | Do ustalenia później |
| Płatności | Do ustalenia później |
| Widget śmieci | Odłożony na później |

---

## Następny Krok: Sprint 1 - Auth/Users

**Co robimy TERAZ:**
1. Tabele `users` + `subscriptions` w `schema.py`
2. JWT auth w `backend/src/auth/`
3. Endpointy: register, login, logout, me, profile
4. Frontend: login, register, profile pages
5. AuthContext w React

**Pliki do utworzenia:**
```
backend/src/auth/
├── __init__.py
├── jwt.py          # JWT tokens
├── dependencies.py # get_current_user
├── routes.py       # POST /register, /login
└── schemas.py      # Pydantic models

backend/src/users/
├── __init__.py
├── routes.py       # GET /me, PUT /profile
└── service.py      # CRUD operations

frontend/src/
├── context/AuthContext.tsx
├── pages/login.tsx
├── pages/register.tsx
└── pages/profile.tsx
```

**Biblioteki do dodania:**
```
# backend/requirements.txt
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
email-validator>=2.0.0
```

**Rekomendacja:** Zacznij od Sprint 1 (Auth) - jest fundamentem dla wszystkiego innego.
