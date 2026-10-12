---
name: RybnoLive
description: Pulpit gminy Rybno w języku paska informacyjnego — plakietka tematu, biały pas, żółty pasek kontekstu
colors:
  tv-ink: "#0a0e1a"
  tv-panel: "#121829"
  tv-panel-2: "#182036"
  tv-seam: "#222b45"
  tv-paper: "#f5f6fa"
  tv-text-soft: "#d7dbe8"
  tv-muted: "#b4bbd0"
  tv-blue: "#1f4fff"
  tv-blue-hover: "#3a63ff"
  tv-blue-soft: "#8fa8ff"
  tv-red: "#d42a1f"
  tv-yellow: "#ffd23f"
  tv-yellow-hover: "#ffe27a"
  tv-green: "#3fcf7a"
typography:
  belt:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 800
    lineHeight: 1.08
    letterSpacing: "-0.01em"
    fontVariation: "'wdth' 78"
  value:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.01em"
    fontFeature: "'tnum'"
    fontVariation: "'wdth' 78"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 800
    lineHeight: 1.375
    letterSpacing: "-0.01em"
    fontVariation: "'wdth' 78"
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.375
    fontVariation: "'wdth' 100"
  body-lead:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.375
    fontVariation: "'wdth' 100"
  tag:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.025em"
    fontVariation: "'wdth' 78"
  nav:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.025em"
    fontVariation: "'wdth' 78"
  meta:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.375
    fontVariation: "'wdth' 100"
rounded:
  none: "0px"
spacing:
  seam: "1px"
  tag-y: "4px"
  tag-x: "10px"
  grid-x: "12px"
  panel: "16px"
  section: "24px"
  section-lg: "32px"
components:
  tag-blue:
    backgroundColor: "{colors.tv-blue}"
    textColor: "#ffffff"
    typography: "{typography.tag}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  tag-red:
    backgroundColor: "{colors.tv-red}"
    textColor: "#ffffff"
    typography: "{typography.tag}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  tag-yellow:
    backgroundColor: "{colors.tv-yellow}"
    textColor: "{colors.tv-ink}"
    typography: "{typography.tag}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  tag-paper:
    backgroundColor: "{colors.tv-paper}"
    textColor: "{colors.tv-ink}"
    typography: "{typography.tag}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  tag-seam:
    backgroundColor: "{colors.tv-seam}"
    textColor: "{colors.tv-paper}"
    typography: "{typography.tag}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  belt-bar:
    backgroundColor: "{colors.tv-paper}"
    textColor: "{colors.tv-ink}"
    typography: "{typography.belt}"
    rounded: "{rounded.none}"
    padding: "12px 16px"
  belt-context:
    backgroundColor: "{colors.tv-yellow}"
    textColor: "{colors.tv-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "8px 16px"
  plate-body:
    backgroundColor: "{colors.tv-panel}"
    textColor: "#ffffff"
    typography: "{typography.value}"
    rounded: "{rounded.none}"
    padding: "12px 14px 14px"
  plate-body-hover:
    backgroundColor: "{colors.tv-panel-2}"
  section-panel:
    backgroundColor: "{colors.tv-panel}"
    textColor: "#ffffff"
    rounded: "{rounded.none}"
    padding: "12px 16px 4px"
  button-primary:
    backgroundColor: "{colors.tv-blue}"
    textColor: "#ffffff"
    typography: "{typography.nav}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "52px"
  button-primary-hover:
    backgroundColor: "{colors.tv-blue-hover}"
  button-paper:
    backgroundColor: "{colors.tv-paper}"
    textColor: "{colors.tv-ink}"
    typography: "{typography.nav}"
    rounded: "{rounded.none}"
    padding: "0 24px"
    height: "52px"
  row-link:
    textColor: "{colors.tv-blue-soft}"
    typography: "{typography.body-lead}"
    height: "44px"
  nav-item:
    textColor: "{colors.tv-paper}"
    typography: "{typography.nav}"
    padding: "0 12px"
    height: "44px"
  nav-item-active:
    backgroundColor: "{colors.tv-paper}"
    textColor: "{colors.tv-ink}"
  ask-input:
    backgroundColor: "{colors.tv-panel}"
    textColor: "#ffffff"
    rounded: "{rounded.none}"
    height: "60px"
---

# Design System: RybnoLive

> **Zakres.** Ten plik opisuje świat „Pasek informacyjny” (odświeżenie 10.2026) — pulpit (`SimpleHomePage`) i wspólny szkielet: górny pasek, nawigację sekcji, dolną belkę zakładek, stopkę, ekran ładowania. `DESIGN/DESIGN.md` i `DESIGN/BRAND.md` (świat „centrum dowodzenia”: poświata, gradienty, zaokrąglone karty, krój Outfit) są **zastąpione** dla pulpitu i szkieletu; opisują świat sprzed 10.2026, wciąż widoczny na podstronach, których jeszcze nie odświeżono. Nowa praca idzie według tego pliku.

## Overview

**Creative North Star: "Pasek informacyjny"**

Pulpit mówi językiem grafiki telewizji informacyjnej: plakietka tematu (wąskie wersaliki na pełnym kolorze) stoi nad pasem treści, a pod nim leży żółty pasek kontekstu. Sprawa wsi czytelnika jest belką na górze strony; reszta dnia to plakietki z jedną wartością (termin, godzina, temperatura) i zdaniem dopowiedzenia. Tło to granatowa czerń, panele są o stopień jaśniejsze, podziały to szew 1 px.

Świat jest płaski i kanciasty. Nie ma cieni, poświaty, gradientów ani zaokrągleń; hierarchię robią kolor plakietki, szerokość kroju i biały pas, nie głębia. Kolor nie dekoruje — niesie stan. Gęstość jest umiarkowana: odpowiedź najpierw, szczegół w zdaniu pod nią, przejście głębiej przez link w chabrze.

Ruch jest jeden i znaczący: przy zmianie stanu belki plakietka wjeżdża, a biały pas odsłania się od lewej. Przy zwykłym wejściu na stronę nic się nie rusza.

**Key Characteristics:**
- Plakietka nad pasem — ten sam układ w belce, kaflach „Na dziś”, nagłówkach sekcji i znaku „Rybno LIVE”.
- Kolor = stan: chaber, czerwień, żółć, papier; nic więcej na powierzchniach pulpitu.
- Jedna rodzina (Archivo) w dwóch szerokościach: wąska gruba dla belki, liczb i etykiet, normalna dla treści.
- Kąty proste, szew 1 px, zero cieni.
- Cyfry tabelaryczne we wszystkich terminach i godzinach.

## Colors

Granatowa czerń z trzema stopniami paneli i czterema kolorami stanu, z których każdy ma jedno znaczenie.

### Primary
- **Chaber** (tv-blue): temat i spokój. Domyślna plakietka sekcji, belka w spokojny dzień („Najbliższe 7 dni: bez zapowiedzianych wyłączeń”), główny przycisk akcji, górna krawędź 2 px paneli sekcji, pasek 3 px nad aktywną zakładką dolnej belki, plakietka „LIVE” w znaku. Najechanie: jaśniejszy chaber (tv-blue-hover).
- **Chaber jasny** (tv-blue-soft): kolor linku tekstowego na ciemnym tle (RowLink, „Zmień”, „szczegóły”). Najechanie przechodzi w biel.

### Secondary
- **Czerwień awarii** (tv-red): wyłącznie awaria trwająca teraz albo zaczynająca się w ciągu 36 h, i tylko gdy dotyczy wsi czytelnika (albo gminy, gdy wsi nie wybrano). Plakietka belki, płaski kwadrat miniatury awarii na liście wiadomości.

### Tertiary
- **Żółć kontekstu** (tv-yellow): kontekst i zapowiedź. Pasek pod belką (co jeszcze w gminie, źródło, godzina sprawdzenia), plakietka zapowiedzi dalszej niż 36 h, pasy „Zdrowie” i „Drogi”, gdy coś się zmieniło, plakietka „Ostrzeżenie” meteo, przycisk wyboru wsi, zaznaczenie tekstu i pierścień fokusu. Tekst na żółci zawsze atramentowy (tv-ink).
- **Zieleń potwierdzenia** (tv-green): tylko ikona potwierdzenia (włączone powiadomienia, drogi przejezdne). Nigdy tło, nigdy plakietka.

### Neutral
- **Granatowa czerń** (tv-ink): tło strony, górnego paska, dolnej belki; tekst na papierze i żółci; `theme-color`.
- **Panel** (tv-panel): ciało kafla, panel sekcji, pole pytania, rozwijany wybór wsi.
- **Panel podniesiony** (tv-panel-2): stan najechania na kafle i panele-przyciski, tło miniatur i szkieletów ładowania.
- **Szew** (tv-seam): linie 1 px (`border`, `divide`, siatki `gap-px` na tle szwu), plakietka stanu „nie sprawdzono”, plakietka „Reklama”.
- **Papier** (tv-paper): biały pas belki, aktywna pozycja nawigacji sekcji, przycisk „Załóż konto”, plakietka neutralna, jasny tekst drugiego planu.
- **Tekst miękki** (tv-text-soft): akapity treści w panelach (lead briefingu, skrót rady, opisy). Wartość żyje dziś jako literał w komponentach, nie w `:root`.
- **Tekst przygaszony** (tv-muted): metadane, podpisy, ikony, placeholder.

### Named Rules
**The Color Is State Rule.** Kolor plakietki niesie znaczenie i nic poza nim: chaber = temat/spokój, czerwień = awaria teraz lub ≤ 36 h, żółć = kontekst/zapowiedź, papier = neutralne wyróżnienie, szew = brak wiedzy. Nowy kolor na pulpicie wymaga nowego stanu, nie nowej ozdoby.

**The Red Is Rare Rule.** Czerwień tylko dla awarii, która dotyczy czytelnika teraz albo jutro. Zapowiedź za trzy dni jest żółta; awaria w cudzej wsi stoi w żółtym pasku kontekstu.

## Typography

**Font:** Archivo (variable, wagi 400–900, szerokość 62–125%), samohostowany z `/fonts/archivo/` (latin + latin-ext), fallback `system-ui, sans-serif`.

**Character:** jedna rodzina w dwóch szerokościach. Wąska (`font-stretch: 78%`, `letter-spacing: -0.01em`, waga 800–900) to głos paska — belka, wartości kafli, nagłówki, etykiety, nawigacja. Normalna (100%) to głos treści.

### Hierarchy
- **Belka** (wąska, 800, 24 → 30 px od `sm` → 44 px od `lg`, interlinia 1.08): jedno zdanie białego pasa.
- **Wartość** (wąska, 800, cyfry tabelaryczne, 26 → 30 px od `lg`, interlinia 1.05): odpowiedź w kaflu „Na dziś”; kino 24 px.
- **Nagłówek** (wąska, 800, 20–23 px, interlinia ~1.375): tytuł daty (22 → 28 px), lead briefingu (22 → 26 px), tytuł rady (21 → 23 px), kadr 21 px, CTA konta 22 px, Zgłoszenia 20 px.
- **Treść** (normalna, 400–600, 15 px, interlinia 1.375–1.625): dominujący rozmiar; paski kontekstu, opisy, podpisy kafli.
- **Treść wiodąca** (normalna, 600–700, 16–17 px): tytuły pozycji listy (16), pytanie do asystenta (17), RowLink (15, 700).
- **Etykieta** (wąska, 800, 13 px, wersaliki, `tracking-wide`, interlinia 1): plakietka; w belce 14 px. Przyciski i nawigacja: wąska, 700–800, 16–18 px, wersaliki.
- **Meta** (normalna, 13–14 px): kategoria i czas przy wiadomości, statusy zgłoszeń, stopka (14).

### Named Rules
**The Two Widths Rule.** Wąski krój mówi „pasek” — wartości, belka, etykiety, nawigacja. Zdanie do przeczytania zawsze w normalnej szerokości. Akapitu wąskim krojem nie składamy.

**The Tabular Time Rule.** Każda godzina, data i liczba w wartości ma cyfry tabelaryczne (`.tabular`).

**The 13 px Floor.** Żaden tekst na pulpicie i w szkielecie poniżej 13 px.

## Layout

- **Szkielet:** kontener `max-w-7xl` (1280 px), wcięcia 16 px, od `md` 32 px. Górny pasek przyklejony; od `lg` drugi wiersz z nawigacją sekcji oddzielony szwem. Poniżej `lg` nawigację przejmuje dolna belka zakładek (5 pozycji, przyklejona, szew u góry); stopka ma wtedy margines 80 px, żeby jej nie zasłaniała, a `main` ma `pb-24`.
- **Rytm pulpitu:** sekcje co 24 px, od `lg` co 32 px. Belka i prośba o powiadomienia zwarte (12 px).
- **Kafle „Na dziś”:** siatka 2 kolumny (odstęp 12 px poziomo, 16 px pionowo), od `lg` 4 kolumny (16 px). Pod nimi pasy Zdrowie i Drogi stykające się szwem 1 px.
- **Pary sekcji:** od `lg` dwie kolumny 1.3fr / 1fr (wiadomości | rada, kadr | kino + weekend), odstęp 24 px; na telefonie jedna kolumna.
- **Siatki list** (zgłoszenia, firmy): `gap-px` na tle szwu — linie między komórkami robi tło, nie obramowanie; od `lg` dwie kolumny.
- **Panele:** wcięcie 16 px, od `lg` 20 px. Akapit leadu briefingu ograniczony do 70 znaków.
- **Rezerwacja miejsca:** belka przed odpowiedzią serwera trzyma 124 px wysokości, żeby kafle pod nią nie skakały.

## Elevation & Depth

Świat jest płaski. Nie ma cieni ani poświaty; głębię zastępują trzy stopnie tła (tv-ink → tv-panel → tv-panel-2) i szew 1 px. Najechanie podnosi panel o jeden stopień tonu (tv-panel → tv-panel-2), nigdy przesunięciem ani cieniem.

**The Flat Plate Rule.** Rzecz ważniejsza jest jaśniejsza albo ma kolor stanu — nie jest wyżej. `box-shadow` na pulpicie i w szkielecie nie występuje.

## Shapes

Wszystkie narożniki proste (0 px): plakietki, pasy, kafle, przyciski, pole pytania, miniatury, rozwijany wybór wsi. Podziały to szew 1 px; jedynym grubszym akcentem jest górna krawędź 2 px w chabrze nad panelem sekcji (papierowa nad CTA konta), aktywna zakładka dolnej belki (3 px) i obramowanie 2 px pola pytania. Miniatury kwadratowe (56 px w wiadomościach i zgłoszeniach, 44 px w firmach), plakat kina 2:3.

**The Square Corner Rule.** Zaokrąglenie nie istnieje w tym świecie. Element z `border-radius` pochodzi ze starego świata.

## Components

### Plakietka (Tag)
Jedna forma: pojedynczy prostokąt w pełnym kolorze tonu, wąskie wersaliki 13 px, 800, wcięcie 10 × 4 px, wyrównana do lewej, nie szersza niż treść. Tony: blue (domyślny), red, yellow, paper, seam. Jako `h2`/`h3` **jest** nagłówkiem sekcji — „Ostatnio w gminie”, „Briefing dnia”, „W ten weekend”, nazwa kina, „Reklama” — a nie ozdobnikiem nad innym nagłówkiem. Plakietki nie sklejamy w dwa człony ani nie stawiamy nad tytułem, który i tak mówi to samo.

### Belka (StatusBelt) — sygnatura
Anatomia: plakietka (14 px, kto · kiedy) → biały pas (papier, zdanie w kroju belki, wcięcie 16 × 12 px, od `lg` 24 × 20 px) → żółty pasek kontekstu (15 px, 600; dopisek źródła „wg komunikatów Energi i ZGK, sprawdzone HH:MM” w 400; opcjonalny link „szczegóły komunikatu” podkreślony, 800).
Stany:
- **Spokój** — plakietka chabrowa „{Wieś} · teraz”, pas mówi okno czasu w zdaniu („Najbliższe 7 dni: bez zapowiedzianych wyłączeń prądu i wody”).
- **Zapowiedź > 36 h** — plakietka żółta „{Wieś} · zapowiedź”.
- **Awaria teraz / ≤ 36 h** — plakietka czerwona „{Wieś} · trwa teraz | dziś | jutro”.
- **Nie sprawdzono** (serwer nie odpowiedział) — plakietka w kolorze szwu „Prąd i woda”, pas „Nie udało się sprawdzić komunikatów o awariach”, pasek: do tego czasu nie wiemy. „Bez awarii” wolno powiedzieć wyłącznie po udanym sprawdzeniu.
- **Ładowanie** — dwa bloki szkieletu (panel-2 nad panelem) w zarezerwowanych 124 px.
Pod belką, gdy obowiązuje: pas ostrzeżenia meteo (panel, żółta plakietka „Ostrzeżenie”, tytuł 15 px, 600).
**Ruch:** plakietka wjeżdża (`tv-tag-in`, 200 ms, przesunięcie −12 px i przezroczystość), biały pas odsłania się od lewej (`tv-wipe`, clip-path, 220 ms), oba `cubic-bezier(0.16, 1, 0.3, 1)` — tylko gdy stan różni się od ostatnio widzianego (pamięć w sessionStorage). Przy `prefers-reduced-motion` brak animacji.

### Kafel z wartością (Plate)
Plakietka nad ciałem w kolorze panelu (wcięcie 14 px, u góry 12 px). Wartość w kroju belki 26/30 px, białą; pod nią zdanie 15 px w tv-muted. Cały kafel jest jednym przyciskiem; najechanie zmienia ciało na panel-2. Pogoda dokłada ikonę obok wartości i żółtą adnotację „pomiar z HH:MM”, gdy odczyt jest nieświeży.

### Panel sekcji
Tło panelu, górna krawędź 2 px w chabrze, wcięcie 16 px (od `lg` 20 px). Nagłówkiem jest plakietka nad panelem albo wąski nagłówek wewnątrz (rada, Zgłoszenia). Listy wewnątrz dzielone szwem. Panel-przycisk podnosi tło do panel-2 przy najechaniu.

### Pasy stanu (Zdrowie, Drogi)
Pełna szerokość, wcięcie 16 × 12 px, ikona 20 px. Bez zmian: panel, tekst papierowy, ikona przygaszona (zielona dla przejezdnych dróg). Zmiana (lekarz nie przyjmuje, utrudnienie): całe tło żółte, tekst atramentowy, separatory `black/25`.

### Link dalej (RowLink)
Tekst 15 px, 700, chaber jasny, chevron 16 px, wysokość 44 px; najechanie: biel i podkreślenie z odstępem 4 px. Jeden wygląd w całym pulpicie.

### Przyciski
- **Główny:** chaber, biały tekst wąski wersalikami 17 px, 800, wysokość 52 px (rejestracja w pasku: 44 px, 16–17 px); najechanie tv-blue-hover.
- **Papierowy:** papier z atramentowym tekstem 18 px — CTA konta; najechanie biel.
- **Wybór wsi:** żółty, wąskie wersaliki 17 px, ikona pinezki i chevron, 44 px; najechanie tv-yellow-hover. Rozwija panel z siatką wsi (2 → 3 od `sm` → 6 od `lg`, pozycje 48 px).
- **Zamknij:** kwadrat 44 px w rogu panelu, ikona przygaszona.

### Pole pytania (AskBar)
Panel z obramowaniem 2 px w kolorze szwu, wysokość 60 px; fokus wewnątrz zmienia obramowanie na papier. Tekst 17 px. Przycisk wysyłki chabrowy na całą wysokość: strzałka na telefonie, „ZAPYTAJ” od `lg`.

### Lista wiadomości (NewsMini)
Pozycja: kwadrat 56 px (zdjęcie albo płaski panel-2 z jedną ikoną; czerwony z ikoną ostrzeżenia dla awarii), meta 13 px (kategoria pogrubiona papierem · czas), tytuł 16 px, 600, do 3 linii, podkreślenie przy najechaniu.

### Nawigacja
- **Górny pasek:** tło granatowej czerni, szew na dole. Znak: „Rybno” wąskim 900 (22 → 26 px) + plakietka „LIVE” w chabrze. Prawa strona: „Cennik”, „Zaloguj” (na telefonie sama ikona w kwadracie 44 px), „Zarejestruj” jako przycisk główny.
- **Nawigacja sekcji (od `lg`):** drugi wiersz, pozycje wąskie wersaliki 16 px, 700, wysokość 44 px; aktywna = papier z atramentowym tekstem (plakietka), najechanie = panel.
- **Dolna belka (poniżej `lg`):** 5 zakładek, ikona 22 px nad etykietą, pozycja 56 × 60 px; aktywna = biały tekst, pogrubiona ikona i pasek 3 px w chabrze na górnej krawędzi.
- **Pasek podsekcji (SubNavBar):** te same pozycje co nawigacja sekcji, na tle czerni, szew na dole.

### Stopka i ekran ładowania
Stopka: szew u góry, tekst 14 px przygaszony, nazwa i linki prawne w papierze, najechanie biel z podkreśleniem. Ekran ładowania: znak „Rybno LIVE” 30 px na środku i „Ładowanie…” 15 px — bez pulsującej poświaty.

## Do's and Don'ts

### Do:
- **Do** stawiać plakietkę nad pasem treści: belka, kafle, sekcje i znak mówią tym samym układem.
- **Do** wybierać kolor plakietki według stanu (The Color Is State Rule); stan nieznany = szew i zdanie „nie wiemy”.
- **Do** dawać każdemu celowi dotyku co najmniej 44 px (przyciski akcji 52 px, pole pytania 60 px, zakładki 56 px).
- **Do** trzymać tekst ≥ 13 px i zostawić globalny pierścień fokusu: 3 px żółci z odstępem 2 px.
- **Do** dzielić powierzchnie szwem 1 px albo `gap-px` na tle szwu; panel sekcji otwierać krawędzią 2 px w chabrze.
- **Do** grać ruch belki tylko przy zmianie stanu i wyłączać go przy `prefers-reduced-motion`.
- **Do** pisać czas w zdaniu („Najbliższe 7 dni: …”) i podawać źródło z godziną sprawdzenia w żółtym pasku.

### Don't:
- **Don't** używać gradientów (tła, tekstu, miniatur), poświaty, `backdrop-filter` ani cieni.
- **Don't** zaokrąglać narożników kart, przycisków, pól ani miniatur.
- **Don't** stawiać kickerów/eyebrow nad nagłówkiem — plakietka jest nagłówkiem, nie ozdobnikiem nad nim.
- **Don't** podstawiać kolorowych miniatur kategorii (fiolet, róż, cyjan); bez zdjęcia jest płaski kwadrat panelu z jedną ikoną.
- **Don't** używać czerwieni dla zapowiedzi dalszej niż 36 h ani dla awarii w cudzej wsi.
- **Don't** mówić „bez awarii”, gdy sprawdzenie się nie udało.
- **Don't** składać akapitów wąskim krojem ani używać kroju systemowego jako display.
- **Don't** wprowadzać kolorów spoza palety tv-* na pulpicie i w szkielecie.
