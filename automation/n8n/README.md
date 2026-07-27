# Automatyzacja social media RybnoLive (n8n)

> Stan: 2026-07-25, po rewizji flow. Poprzednia wersja tego pliku opisywała workflowy
> C/D, które nigdy nie zostały zaimportowane, podawała nieaktualną wersję Graph API
> (v21.0 — na produkcji jest v23.0) i sekret, którego nie ma w żadnym działającym nodzie.

## Podział odpowiedzialności

**Backend robi treść, n8n tylko akceptuje i publikuje.**

```
backend  → treść posta, prompt, generowanie grafiki w kie.ai, trwałe hostowanie plików
n8n      → cron, przycisk na Telegramie, wywołanie Facebook Graph API
```

Wcześniej logika treści siedziała w node'ach Code w n8n i była **zduplikowana**: workflow A
budował propozycję na Telegram, a workflow B budował ją PONOWNIE (pobierając summary drugi
raz) przy publikacji — więc opublikowany post nie musiał być tym, co zaakceptowałeś.
Teraz źródłem jest `backend/src/services/social_content.py`, a zmiana copy czy promptu to
commit, nie klikanie po UI.

## Endpointy (nagłówek `X-Social-Token`, credential „RybnoLive Social Token”)

| Endpoint | Zwraca |
|---|---|
| `GET /api/social/proposal?kind=text` | gotowy post z dziennego podsumowania AI |
| `GET /api/social/proposal?kind=photo` | post + grafika z kie.ai (20–60 s, timeout noda 200 s) |
| `GET /api/social/campaign/due` | pozycja kampanii przypadająca na teraz albo `{"due": false}` |
| `POST /api/social/media` | kopiuje grafikę z URL-a do `uploads/social/` (linki kie.ai żyją ~24 h) |
| `GET /api/social/media?subdir=kampania` | lista grafik — weryfikacja |

## Workflowy

Każdy to prosta linia bez rozgałęzień, wszystkie o tym samym kształcie:

```
cron ─────┐
          ├→ HTTP /api/social/… → Telegram [✅ Publikuj][🔄 Ponów] → Wait → Facebook → Telegram ✔
webhook ──┘
```

| Plik | Workflow w n8n | Nodów | Cron |
|---|---|---|---|
| `W1_post_tekstowy.json` | RybnoLive — post tekstowy (podsumowanie AI) | 7 | codziennie 7:45 |
| `W2_post_graficzny.json` | RybnoLive — post graficzny (kie.ai) | 7 | wtorki 17:00 (do 10.08; potem wróć do wt+czw) |
| `W3_kampania.json` | RybnoLive — kampania 27.07–10.08 | 8 | 9 godzin emisji dziennie |

Źródłem jest `build_workflows.py` — JSON-y są z niego generowane:

```bash
set -a; . automation/.env; set +a
python3 automation/n8n/build_workflows.py           # tylko zapis JSON-ów
python3 automation/n8n/build_workflows.py --push    # utworzenie w n8n (nieaktywne)
```

### Dlaczego akceptacja działa bez webhooka i bez sekretu

Przycisk „✅ Publikuj” prowadzi do `$execution.resumeUrl` node'a **Wait** — adresu
jednorazowego i niezgadywalnego, unikalnego dla tej jednej propozycji. Skutki:

- **brak podwójnej publikacji** — drugie kliknięcie nic nie robi (egzekucja już wznowiona),
- **brak wspólnego sekretu w URL-u**, którym dotąd dało się opublikować cokolwiek,
- **fail-closed** — node Wait celowo NIE ma limitu czasu. Limit oznaczałby, że po jego
  upływie przepływ rusza dalej i publikuje post bez akceptacji. Nie klikasz = nic się nie
  dzieje, egzekucja zostaje w stanie „waiting”.

Przycisk „🔄 Ponów” / „🎨 Inna grafika” wskazuje na webhook uruchomienia tego samego
workflow — klik startuje nową egzekucję z nową treścią/grafiką, a stara propozycja
pozostaje niewznowiona. Sekret w tym URL-u pozwala tylko **wygenerować** propozycję,
nie opublikować ją, więc jego wyciek nic nie daje.

## Każdy post ma grafikę (od 2026-07-26)

Do 26.07 W1 publikował przez `/feed` z parametrem `link=https://rybnolive.pl`. Facebook
rysował wtedy kartę linku z tagów OG strony — a te wskazywały **nieistniejącą domenę
`rybno.pl`**, więc pod każdym postem wisiał pusty biały kwadrat 512×512. Poprawka jest
dwutorowa:

1. `frontend/index.html` — OG i canonical na `rybnolive.pl`, `og:image` = dedykowany
   `og-image.jpg` 1200×630, `twitter:card` = `summary_large_image`. Działa wszędzie tam,
   gdzie ktoś wkleja link ręcznie (Messenger, WhatsApp, komentarze).
2. W1 publikuje przez `/photos`, nie `/feed` — zdjęcie zamiast karty linku. Adres
   rybnolive.pl zostaje w treści posta.

Skąd grafika w poście tekstowym — **z `services/social_card.py`, nie z kie.ai**:

| | Karta dnia (W1, codziennie) | Ilustracja AI (W2, wtorki) |
|---|---|---|
| Powstaje | Pillow, lokalnie, ~0,1 s | kie.ai `nano-banana-pro` + Pillow, ~50 s |
| Format | 1200×630 (karta OG) | 1080×1920 (9:16, model renderuje w 2K) |
| Koszt | 0 | ~18 kredytów |
| Tekst na grafice | `headline` renderowany dosłownie | `claim` renderowany dosłownie |
| Rola modelu | — | rysuje **wyłącznie scenę**, ani jednej litery |

### Dlaczego model nie pisze na grafice (od 2026-07-27)

Do 27.07 claim wypalał model i to było widać: pocięte wyrazy („SPADK NIKÓW
MIESZKAŃCÓW”), gubione ogonki, inny krój w każdym poście. Teraz `BRAND_STYLE` zabrania
modelowi jakiegokolwiek tekstu, a `social_card.compose_photo_card` nakłada na gotową
ilustrację nagłówek, pigułkę i stopkę — fontem Outfit i kolorami z `DESIGN/BRAND.md`,
identycznie jak na karcie dnia. Powtarzalność marki bierze się właśnie z tego podziału:
model odpowiada za scenę, my za wszystko, co ma stały kształt.

Scena ma **pokazywać sytuację, nie jej symbol** — zawsze z ludźmi i zawsze w działaniu
(`CLAIM_SYSTEM_PROMPT`). Awaria prądu to rodzina przy świecy w ciemnej kuchni, festyn to
tańczący mieszkańcy — nie ikona żarówki i nie pusty krajobraz.

Karta składa się z fontu `backend/assets/fonts/Outfit.ttf` (OFL) i kadru kuli
`backend/assets/social/orb.jpg` — obie rzeczy leżą w repo i trafiają do obrazu przez
`COPY assets/ assets/` w `backend/Dockerfile`. Kolory pochodzą z `DESIGN/BRAND.md`.

Render jest **fail-closed**: gdy się nie powiedzie, `/proposal?kind=text` zwraca 502
i propozycja nie przychodzi na Telegram. Awaria renderu oznacza brak fontu albo błąd
deployu — jest trwała, więc cichy fallback do posta bez grafiki tylko ukryłby wadę,
a kosztowałby rozgałęzienie w każdym przebiegu. Wyjątkiem jest sam kadr kuli: jego brak
tylko loguje ostrzeżenie i karta wychodzi bez tła.

## Grafiki — jedno miejsce

```
uploads/social/            ← karty dnia (W1) + grafiki kie.ai (W2)
uploads/social/kampania/   ← 11 statycznych grafik kampanii
        ↓
https://api.rybnolive.pl/uploads/social/…
```

Wolumen `uploads` (ten sam wzorzec co logo wizytówek i zdjęcia zgłoszeń, `StaticFiles`
zamontowane w `main.py`). Publiczne od razu, **bez rebuildu frontendu**.

Zlikwidowane 2026-07-25 — grafiki leżały w dwóch miejscach naraz, w różnych wersjach:

| Było | Problem |
|---|---|
| `frontend/public/kampania/` → `rybnolive.pl/kampania/` | 5,1 MB w każdym buildzie; nowa grafika wymagała `npm run build` + rsync + docker cp; grafiki generowane w locie niemożliwe |
| `rybnolive.pl/campaign/` | 1 plik wprost na wolumenie, poza repo, w innej wersji niż jego odpowiednik w `/kampania/` — i to jego używał działający workflow |

Lokalne kopie źródłowe: `automation/kampania/grafiki/` (poza buildem frontendu).

## Kalendarz kampanii

Siedzi w `backend/src/services/social_content.py` → `CAMPAIGN_PLAN` (copy przeniesione
1:1 z zatwierdzonego COPY_HARMONOGRAM.md v2.0). n8n odpytuje `campaign/due` o godzinach
emisji i nie wie nic o datach — **zmiana harmonogramu nie wymaga dotykania n8n**.

Świadome odstępstwo od pierwotnego planu: **karuzela 5 zdjęć z 29.07 została zastąpiona
pojedynczym postem**. Karuzela w Graph API wymaga 5 uploadów `published=false`, zebrania
ID i osobnego `/feed` z `attached_media` — 4 dodatkowe nody i najbardziej awaryjny fragment
starego workflow D. Grafiki `karuzela_2..5` wykorzystane jako osobne posty 5.08 i 7.08.

Po 10.08: **dezaktywuj W3** (przypomnienie przychodzi na Telegram 10.08 o 10:00)
i **przywróć czwartek w W2** (`["0 17 * * 2,4"]` w `build_photo_workflow`).

## Sekrety

`automation/.env` (w `.gitignore`, chmod 600): `N8N_API_KEY`, `KIE_API_KEY`,
`SOCIAL_MEDIA_TOKEN`, `KAMPANIA_SECRET`. Te same wartości po stronie backendu żyją
w `backend/.env.production` (`SOCIAL_MEDIA_TOKEN`, `KIE_API_KEY`).

**W plikach workflowów sekretu nie ma** — jest `__KAMPANIA_SECRET__`, podstawiany dopiero
przy wysyłce (`with_secret()`). Do 26.07 generator wpisywał prawdziwą wartość, więc JSON-y
leżały z nią w publicznym repo. Opublikować niczego się tym nie dało (chroni jednorazowy
`resumeUrl`), ale dało się **uruchamiać** W2 w pętli, a to gpt-4o plus ~22 kredyty kie.ai
za każdym wywołaniem. Sekret zrotowany 26.07, stare ścieżki webhooków już nie działają.

Historia gita zostaje publiczna — stary sekret traktuj jako spalony na zawsze. Kopie
pobierane z n8n trzymaj w `automation/n8n/_backup/` (poza repo), nigdy obok plików
generowanych.

## Zmiana workflow

```bash
set -a; . automation/.env; set +a
python3 automation/n8n/build_workflows.py --update    # nadpisuje po ID z LIVE_IDS
```

`--update` (PUT) zachowuje id i stan aktywności. `--push` (POST) tworzy **nowy** workflow —
używaj tylko dla czegoś, czego jeszcze nie ma w n8n, bo sprzątanie duplikatu to trwały
DELETE.

Klucz Public API n8n wygasa **2026-08-23** — po tej dacie wygeneruj nowy w Settings → API.
