# RybnoLive — System wizualny (brand kit)

Źródło prawdy: `frontend/index.html` (tokeny `:root`), `frontend/tailwind.config.js`,
klasy Tailwind w `frontend/components/**` i `frontend/src/**`, `frontend/public/icon-512.png`,
`backend/src/services/social_content.py` (`BRAND_STYLE` — prompt graficzny).

Ten plik służy do odtworzenia identyfikacji przez inne modele/narzędzia (Claude Design,
Canva, generatory graficzne). Jeśli zmieniasz kolory w `index.html` — zaktualizuj też ten plik.

---

## 1. Charakter marki

Ciemny, „operacyjny" interfejs — dashboard dowodzenia, nie portal informacyjny.
Głęboka granatowa czerń jako baza, jeden dominujący akcent: elektryczny niebieski
z miękką poświatą (glow). Kolor jest funkcjonalny — sygnalizuje status, nie dekoruje.

Słowa-klucze: **ciemny · granatowy · świetlisty · minimalistyczny · cinematic rim light · bez ozdobników**

Marka jest **dark-first** — nie istnieje wersja light interfejsu. Logo musi działać
na tle `#05080f` i na płaskim niebieskim `#2563eb`.

---

## 2. Kolory bazowe (tokeny `:root`)

| Token | HEX | Zastosowanie |
|---|---|---|
| `--background` | `#05080f` | Główne tło strony (granatowa czerń) |
| `--card` | `#0d1117` | Tło kafelków / paneli |
| `--foreground`, `--primary` | `#fafafa` | Tekst podstawowy |
| `--muted-foreground` | `#a1a1a1` | Tekst drugorzędny |
| `--border`, `--input`, `--muted`, `--accent` | `#262626` | Obramowania, pola, tła stanów |
| `--ring` | `#525252` | Focus ring |
| `--radius` | `0.625rem` (10 px) | Bazowy promień; kafelki: `1.25rem` = 20 px |

Rozszerzenia Tailwind (`tailwind.config.js`): `slate-850 #1e293b`, `slate-950 #020617`.
`#020617` to tło używane w promptach graficznych (social media) jako „deep navy".

---

## 3. Skala niebieskiego — kolor wiodący

Zdefiniowana jako `--chart-1…5`. To jest **właściwa paleta marki**, od jasnej poświaty
do głębokiego granatu.

| Token | HEX | Rola |
|---|---|---|
| `--chart-1` | `#91c5ff` | Jasny akcent, hover, koniec gradientu tekstowego, glow |
| `--chart-2` | `#3a81f6` | **Kolor główny marki** — przyciski CTA, aktywne stany |
| `--chart-3` | `#2563ef` | Ciemniejszy wariant, gradienty |
| `--chart-4` | `#1a4eda` | Głębszy granat |
| `--chart-5` | `#1f3fad` | Najciemniejszy, cienie/tła wykresów |

Praktycznie w komponentach dominują odpowiedniki Tailwind:
`blue-300 #93c5fd`, `blue-400 #60a5fa`, `blue-500 #3b82f6`, `blue-600 #2563eb`.

**Kolor ikony/logo (obecny)**: tło `#2563eb`, znak `#f2f6fe`.

---

## 4. Kolory semantyczne

Używane konsekwentnie do statusów — nie zamieniać rolami.

| Znaczenie | Nazwa Tailwind | HEX (jasny / bazowy) |
|---|---|---|
| Informacja, marka, AI | blue | `#60a5fa` / `#3b82f6` |
| Ostrzeżenie, energia, Premium | amber | `#fbbf24` / `#f59e0b` |
| Awaria, alarm, krytyczne | red | `#f87171` / `#ef4444` |
| Stan OK, wzrost, dostępność | emerald | `#34d399` / `#10b981` |
| Plan „Firma lokalna", B2B | violet | `#a78bfa` / `#8b5cf6` |
| Ruch drogowy, utrudnienia | orange | `#fb923c` / `#f97316` |
| Dane, mapy, akcent zimny | cyan / teal | `#06b6d4` / `#14b8a6` |

Neutralne (w kodzie najczęściej używane w ogóle):
`neutral-100 #f5f5f5`, `neutral-200 #e5e5e5`, `neutral-300 #d4d4d4`,
`neutral-400 #a3a3a3`, `neutral-500 #737373`, `neutral-600 #525252`,
`gray-700 #374151`, `gray-800 #1f2937`, `gray-900 #111827`, `gray-950 #030712`.

---

## 5. Gradienty

```
Tekst „gradient" (nagłówki hero):   #91c5ff → #3a81f6   (do prawej)
Tekst „SaaS" (podtytuły):           #fafafa → #a3a3a3   (do dołu)
CTA / logo:                          #3a81f6 → #2563eb
```

Gradienty agentów AI (`src/pages/AssistantPage.tsx`) — sygnatury kolorystyczne postaci:

| Agent | Gradient (Tailwind) | HEX |
|---|---|---|
| Orchestrator / ogólny | `from-blue-600 to-violet-600` | `#2563eb → #7c3aed` |
| Redaktor | `from-sky-500 to-blue-700` | `#0ea5e9 → #1d4ed8` |
| Urzędnik | `from-amber-500 to-orange-700` | `#f59e0b → #c2410c` |
| Strażnik | `from-red-500 to-rose-700` | `#ef4444 → #be123c` |
| Przewodnik | `from-emerald-500 to-teal-700` | `#10b981 → #0f766e` |
| GUS-Analityk | `from-purple-500 to-fuchsia-700` | `#a855f7 → #a21caf` |
| Organizator | `from-cyan-500 to-blue-700` | `#06b6d4 → #1d4ed8` |

---

## 6. Typografia

- **Font podstawowy: `Outfit`** (Google Fonts), wagi `300, 400, 500, 600, 700, 800, 900`.
  Geometryczny grotesk, szerokie okrągłe litery — spójny z okrągłym znakiem w logo.
  `font-family: 'Outfit', sans-serif` na `body`.
- **Font monospace**: domyślny stack Tailwind (`ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas`).
  Używany do danych liczbowych: godziny odjazdów, µg/m³, kody, liczniki, timestampy.
- Nie ma fontu szeryfowego. Nie ma drugiego kroju displayowego.

Typowe traktowania:
- Nagłówki hero: `font-bold`/`font-black`, gradient tekstowy `#91c5ff → #3a81f6`.
- Etykiety/chipy: `text-[10px]–text-xs`, `uppercase`, `tracking-wider`, `font-bold`, kolor `neutral-500/600`.
- Treść: `text-neutral-300/400` na tle `#0d1117`.

**Do logo**: Outfit 700–900, litery drukowane lub mieszane; hasło marki „**Twoja gmina. Na żywo.**".
Nazwa zapisywana jako `RybnoLive` (bez spacji, camel case) lub `rybnolive.pl` w kontekście domeny.

---

## 7. Kształt, efekty, faktura

- **Promień**: kafelki 20 px (`1.25rem`), przyciski 12 px (`0.75rem`), chipy pełne (`9999px`), tokeny bazowe 10 px.
- **Glass panel**: `background: rgba(10,10,10,0.72)`, `backdrop-filter: blur(16px)`,
  `border: 1px solid rgba(255,255,255,0.08)`, `box-shadow: 0 8px 32px rgba(0,0,0,0.5)`.
- **Glow tile**: obracający się `conic-gradient` z `--chart-2 → --chart-1 → biały 50% → --chart-1 → --chart-2`,
  opacity 0.15 w spoczynku, 1.0 na hover; unosi kafelek o `-4px`.
- **Chip hover**: tło `rgba(58,129,246,0.12)`, border `rgba(58,129,246,0.35)`, tekst `#91c5ff`.
- **Scrollbar**: track `#000`, thumb `#1f2937`, hover `#374151`.
- Motyw sygnałowy: pulsująca kropka „live" — `bg-blue-400` z `animate-ping` + `bg-blue-500`.

---

## 8. Motyw graficzny (obrazy, social media)

Stały prompt stylu z `backend/src/services/social_content.py` (`BRAND_STYLE`) — używać go
przy generowaniu jakichkolwiek grafik marki:

> Modern editorial illustration for a Polish local-news brand. Deep navy background (#020617)
> with a soft glowing blue-cyan light source, subtle grain, cinematic rim light, clean minimal
> composition, rural Masurian setting (fields, lake, small village architecture),
> no people's faces in close-up, no watermarks, no logos other than requested text.

Motyw przewodni strony głównej: **kula ziemska z konturami kontynentów**, świecąca na niebiesko
na granatowym tle (animacja canvas w hero, 121 klatek). To jest wizualny rdzeń marki —
okrąg + poświata, i to samo powtarza obecna ikona PWA (pierścień na niebieskim kwadracie).

### Karta dnia (posty tekstowe na Facebooku)

Codzienny post składany lokalnie, bez modelu graficznego — `backend/src/services/social_card.py`.
Układ 1200×630: pasek `#3a81f6` u góry, pigułka z etykietą (dzień i data, albo „AWARIA"),
nagłówek dnia w Outfit ExtraBold wyśrodkowany pionowo (auto-dopasowanie stopnia pisma
66→36 px, maks. 4 wiersze), kadr kuli wtopiony w prawą krawędź na 75% jasności, stopka
`rybnolive.pl · Twoja gmina. Na żywo.` po lewej.

Zasada: **tekst na grafice renderujemy dosłownie z bazy, nigdy nie zlecamy go modelowi** —
kie.ai potrafi pociąć polskie wyrazy, a błąd na wypalonej grafice jest nieodwracalny.

---

## 9. Brief pod nowe logo (skrót do wklejenia)

```
Marka:      RybnoLive (rybnolive.pl) — centrum operacyjne mieszkańca gminy Rybno
Claim:      Twoja gmina. Na żywo.
Charakter:  dark-first, operacyjny dashboard, technologiczny ale przyjazny, wiejsko-mazurski kontekst
Symbol:     okrąg / pierścień / kula z poświatą (kontynenty, sygnał live, punkt na mapie)
Kolory:     tło #05080f lub #020617; znak #3a81f6 z akcentem #91c5ff; wersja mono #f2f6fe
            wariant solid: kwadrat #2563eb + znak #f2f6fe (obecna ikona PWA)
Font:       Outfit (700–900)
Zakaz:      gradienty tęczowe, kolory poza paletą, cienie soft-3D, clipart, herby gminne
Wymóg:      czytelność w 72×72 px (ikona PWA, favicon) i na płaskim niebieskim tle
```

---

## 10. Pliki źródłowe

| Co | Gdzie |
|---|---|
| Tokeny CSS + efekty (glass, glow, scrollbar) | `frontend/index.html` (`<style>` w `<head>`) |
| Rozszerzenia palety Tailwind | `frontend/tailwind.config.js` |
| Ikony PWA / favicon | `frontend/public/icon-512.png`, `icon-192.png`, `icon-72.png`, `badge-72.png` |
| Miniatura linku (OG, 1200×630) | `frontend/public/og-image.jpg` |
| Karta dnia na Facebooka (generator) | `backend/src/services/social_card.py` |
| Font i kadr kuli dla generatora | `backend/assets/fonts/Outfit.ttf`, `backend/assets/social/orb.jpg` |
| Klatki animacji kuli (hero) | `frontend/public/videos/kula6/0001-0121.jpg` |
| Kolory agentów AI | `frontend/src/pages/AssistantPage.tsx` |
| Prompt stylu grafik | `backend/src/services/social_content.py` → `BRAND_STYLE` |
| Materiały kampanii | `DESIGN/assets`, `DESIGN/posts`, `DESIGN/stories`, `DESIGN/video` |

---

*Utworzono: 2026-07-26 · odtworzone ze stanu kodu produkcyjnego (branch `main`)*
