---
version: 1
slug: "frontend-src-pages-simplehomepage-tsx"
primary_target: "frontend/src/pages/SimpleHomePage.tsx"
related_targets: ["frontend/components/simple"]
---

---
version: 1
slug: "frontend-src-pages-simplehomepage-tsx"
primary_target: "frontend/src/pages/SimpleHomePage.tsx"
related_targets: ["frontend/components/simple"]
---

# Pulpit strony głównej — odświeżenie

**Tryb:** Operate. Cel: mieszkaniec z telefonu (z posta FB lub pusha) w 2 sekundy wie, czy w jego wsi jest awaria, kiedy wywóz, co dziś; potem zostawia wieś i zgodę push.
**Zakres:** pulpit (`SimpleHomePage` + `components/simple/*`) oraz szkielet (nagłówek, nawigacja, stopka, tokeny i krój) — reszta podstron dziedziczy tokeny i szkielet, ich układ zostaje do kolejnych etapów. Lokalnie, do akceptacji; bez generowanych grafik.
**Nie ruszać:** logika czasu (`eventTime`, `briefingDay`), bramka wsi (`concernsLocation`), uczciwe stany „nie wiem”, kolejność push ↔ alert (nigdy oba naraz).
**Anty-cele:** hasło na pół ekranu, poświata, gradient tekstu, pigułka „na żywo”, kropki API, jednakowe karty z ikoną, reklama-zapychacz.

## Direction contract
THESIS: Sprawa Twojej wsi jako belka serwisu informacyjnego — plakietka tematu + biały pas z jednym zdaniem + żółty pasek kontekstu; reszta dnia w plakietkach. Odrzuca stos jednakowych świecących kart pod hasłem reklamowym.
OWN-WORLD: Granatowa czerń #0a0e1a, panele #121829, szew 1 px #1f2740; biały pas z atramentowym tekstem; plakietki: chaber #1f4fff (spokój/temat), czerwień #e63027 (awaria teraz/jutro), żółć #ffd23f (pasek kontekstu „w gminie”). Archivo: wąskie 75–85% grube dla belki i liczb, normalna szerokość dla treści. Kąty proste, bez cieni i poświaty; cyfry tabelaryczne.
STORY: Mieszkaniec widzi stan swojej wsi, wierzy, bo zdanie ma termin i źródło, i robi jedno: zapisuje wieś i włącza powiadomienia o niej.
FIRST VIEWPORT: Telefon 390: pasek z logo i plakietką wsi „Żabiny ▾”; belka (plakietka „ŻABINY · TERAZ” nad białym pasem 24–30 px „Bez wyłączeń prądu i wody”); żółty pasek „W gminie: wt 14.10 9:00–13:00 — Grądy”; siatka 2×2 plakietek Wywóz/Autobus/Pogoda/Rada; przycisk „Powiadamiaj o Żabinach” w zasięgu kciuka. WWW 1440: górna nawigacja sekcji, ta sama belka na szerokość treści, 4 plakietki w rzędzie, pod nimi wiadomości i rada.
DEVIATIONS (cytowane po przeglądzie końcowym 11.10): (1) plakietka wsi stoi w główce pulpitu, nie w górnym pasku — górny pasek jest wspólny dla wszystkich podstron, a wieś steruje wyłącznie pulpitem; (2) czwarta plakietka to „Wydarzenia”, nie „Rada” — sesja jest raz w miesiącu i ma własny moduł obok wiadomości, wydarzenia zmieniają się codziennie; (3) belka w stanie spokoju mówi okno czasu w zdaniu („Najbliższe 7 dni: …”), a źródło i godzinę sprawdzenia w żółtym pasku — zawsze.
FORM: Pasek informacyjny (wybór Impeccable, pozycja 1 mojej listy w rozdaniu 3), seed 4b22fe31. Ruch-sygnatura: przy zmianie stanu belki plakietka wjeżdża, a biały pas odsłania się od lewej (clip-path, 220 ms) — tylko przy zmianie, nie przy każdym wejściu.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
