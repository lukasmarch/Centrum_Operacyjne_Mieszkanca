# DO ZROBIENIA — RybnoLive.pl

> Stan na: 2026-07-07 (po wdrożeniu RODO Etap 0+1, źródeł Tier 1 i napraw agentów/RAG).
> Historia sesji: `.claude/sessions/session-20260707-2246.md` · Raport: `Raport_Biznesowy_RybnoLive_2026-07-07.pdf`

## 🔴 Priorytet 1 — krytyczne (najbliższa sesja)

- [ ] **Podmienić `[NIP]` i `[ADRES]`** w dokumentach prawnych (dane Lumargo od Łukasza)
      → `frontend/src/pages/TermsPage.tsx` (§1 pkt 2) i `PrivacyPage.tsx` (sekcja 1)
      → potem `./deploy-frontend.sh 91.99.142.30`
- [ ] **Weryfikacja dokumentów prawnych przez radcę prawnego** (wersje robocze na produkcji; budżet ~1,5–3 tys. zł)
- [ ] **UI DSAR w ProfilePage** — przyciski „Pobierz moje dane" i „Usuń konto" (z potwierdzeniem!)
      → endpointy już działają na prod: `GET /api/users/me/export`, `DELETE /api/users/me`

## 🟠 Priorytet 2 — prawo i źródła (30 dni)

- [ ] **Model snippet+link dla Syli** — content FB ≤300 znaków + link do oryginału (plan: `~/.claude/plans/wykluczenie-zrodel-fb-scoring-prawny.md`, Etap C)
- [ ] **Scoring prawny artykułów** (RISK/VALUE, decyzje KEEP/MITIGATE/DROP) — Etap B planu
- [ ] **IMGW ostrzeżenia meteo/hydro** — custom scraper JSON (`danepubliczne.imgw.pl`), filtr TERYT 2803
- [ ] **Minimalizacja `raw_data` CEIDG** (klauzula art. 14 już jest w polityce)
- [ ] Monitoring nowych źródeł Tier 1 — czy Energa/Powiat/Radio Olsztyn dostarczają artykuły (logi po 6:15)
- [ ] Cel: udział FB w treściach <40% po 6 mies. (obecnie ~63%)

## 🔵 Priorytet 3 — produkt i monetyzacja (90 dni, rozdz. 4–5 raportu)

- [ ] **Licznik pracy agentów na dashboardzie** — „Dziś agenci przeczytali za Ciebie X artykułów" (quick win, dane są w bazie)
- [ ] **Persony i awatary agentów** + strona „Poznaj zespół AI Rybna"
- [ ] **Porównania międzygminne w GUS-Analityku** — dane 6 gmin powiatu już są w `gus_gmina_stats`
- [ ] Query rewriting kontynuacji przed RAG („a w Hartowcu?" → pełne zapytanie)
- [ ] **Trial Premium 30 dni bez karty** (job `trial_expiry_job` istnieje; dziś trial=7 dni)
- [ ] **Plan „Firma lokalna" 49 zł/mc** — przebudowa planu Pro (wizytówka premium w katalogu firm)
- [ ] **Oferta B2G dla urzędu gminy** — moduł zgłoszeń + komunikaty + alerty (pilotaż 3 mies.)
- [ ] Briefing audio (TTS, endpoint `voice.py` istnieje)
- [ ] Oceny odpowiedzi AI (👍/👎)

## 🟢 Marketing (zero-cost, do rozpoczęcia od razu — zadania Łukasza)

- [ ] Strona „Rybno Live" na Facebooku + automatyczna publikacja podsumowań AI (własne treści = legalne)
- [ ] Wizytówka Google (Google Business Profile)
- [ ] Plakaty z QR „Sprawdź, kiedy wywóz śmieci" (sklepy, urząd, tablice ogłoszeń)
- [ ] Prezentacja dla sołtysów (24 sołectwa) — sołtys ambasadorem z darmowym Premium
- [ ] Newsletter jako lead-magnet: „e-mail przed wyłączeniem prądu"

## ✅ Zrobione 2026-07-07 (na produkcji)

- [x] Raport biznesowo-prawny PDF (marketing, cennik, RODO, roadmapa)
- [x] RODO Etap 0: regulamin + polityka prywatności + cookies + baner + zgody + AI Act
- [x] RODO Etap 1: DSAR (eksport/usunięcie konta), retencja (job 3:30), hash IP
- [x] Naprawa logowania kosztów AI (`api_cost_log`)
- [x] Wyłączenie Panoramy Regionu i Gazety Olsztyńskiej; 4 legalne źródła Tier 1
- [x] Naprawa GUS-Analityka (dane gmina+powiat, klasyfikator kategorii)
- [x] Naprawa chipów źródeł, historii rozmowy (20 ostatnich), routera (lepkość)
- [x] Kalibracja RAG (progi 0.35/0.50, BM25 prefiksy, recency boost)
