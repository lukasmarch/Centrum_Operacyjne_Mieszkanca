---
target: pulpit strony głównej
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:/Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca/frontend/src/pages/SimpleHomePage.tsx"
target_fingerprint: "sha256:627d44c07e48512d9a254f2c4e6e65c8b499e1a0ad64faef3d5620c5a48361af"
target_path: /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca/frontend/src/pages/SimpleHomePage.tsx
timestamp: 2026-10-11T13-47-23Z
slug: frontend-src-pages-simplehomepage-tsx
---
Method: dual-agent (A: przegląd projektowy · B: detektor + przeglądarka). Zastrzeżenie: widok mobilny oceniony z kodu (okno Chrome nie dało się zwęzić); nieaktualny briefing lokalnie wynika z wyłączonego schedulera.

## Heurystyki: 23/40 (Do przyjęcia)
1 Stan systemu 2 — nieaktualny briefing pisze „Dziś”; 2 Świat rzeczywisty 3; 3 Kontrola 3 — zamknięty push znika na 30 dni; 4 Spójność 2 — jedna karta na wszystko; 5 Zapobieganie 3; 6 Rozpoznawanie 2 — „Info/Firmy”, odpady bez wyboru wsi; 7 Elastyczność 2 — brak „mojej wsi”; 8 Minimalizm 2 — 15 bloków, hasło na 1. ekranie; 9 Błędy 2 — ciche return null; 10 Pomoc 2 — AskBar na dole.

## Specyficzność
Treść autorska (zdjęcie, imieniny, autobus, apteka), szkielet generyczny dark-SaaS (pigułka NA ŻYWO, gradient hasła, identyczne karty, kropki statusu). Detektor: CLI 1 (CinemaCard.tsx:54 fiolet zastępczy); przeglądarka 17 (kontrast 1,9:1 span, btn-primary 3,7:1, stopka 4,2:1, belka 10px 4,4:1; gradient-text/dark-glow/grid = marka, fałszywe alarmy).

## Problemy priorytetowe
- [P1] Nieaktualny briefing zaprzecza sobie — BriefingCard.tsx:84-96 zmienia tylko kolor etykiety; zwinąć do linku przy day.stale, „Na dziś” na górę. harden
- [P1] Zapowiedziana awaria pod zgięciem (Grądy 14.10 w NewsMini) — stała linia „Prąd i woda” na górze „Na dziś”, z komunikatem „brak wyłączeń”. layout + clarify
- [P1] Prośba o konto/push za późno i za cicho — blok 12/15; AlertPushPrompt.tsx:207 text-xs, zamknięcie 22px, goły select. „W której wsi mieszkasz?” po „Na dziś” → odpady + awarie + push. onboard
- [P2] Pierwszy ekran = hasło (~60%) — HeroBand.tsx:102-172 do jednej linii. distill
- [P2] Drobny szary tekst i małe cele — neutral-600 2,6:1 (NewsletterCta.tsx:120), etykiety 10–11px, zamknięcia 22px, płaski konspekt h2. audit → typeset

## Persony
Casey: zdjęcia przed odpowiedziami, przeskoki układu, AskBar poza kciukiem. Jordan: „wczoraj”+„Dziś”, „Dziś w gminie”→Działdowo, CTA na 6. ekranie. Sam: 2,6:1 i 1,9:1, alt="" przy KadrCard, 3/4 kafli bez nazwy (do sprawdzenia). Mieszkaniec Hartowca: brak stałej odpowiedzi o prądzie, „Wybierz miejscowość” bez wyboru.

## Drobne
„Daj znać” → kalendarz; „Rybno Live” w stopce; capitalize w pogodzie; AdBoard zapychacz; podwójna nawigacja na desktopie; „już 10 października” przy „1d temu”; nierówne kafle.

## Pytania
Wieś jako oferta konta? Dlaczego hasło na 60% ekranu? Co mówi spokojny dzień? Czy „centrum dowodzenia” buduje zaufanie 65-latka?
