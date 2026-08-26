# Materiał odniesienia — sesja XXIII (24.06.2026)

Transkrypt i skrót jedynej sesji, która przeszła cały mechanizm. Leżą tu, bo
`/tmp/council_sessions` czyści się przy restarcie systemu, a **odtworzenie tego
transkryptu kosztuje $0,52** (Whisper, 86 minut nagrania). Praca nad promptem
skrótu ma kosztować tokeny gpt-4o, nie transkrypcję od nowa.

| plik | co to |
|---|---|
| `xxiii_2026-06-24.transcript.json` | 650 segmentów, 5185 s, źródło: `youtube.com/watch?v=6h9iKlveTcs` |
| `xxiii_2026-06-24.summary.json` | skrót przyjęty przez człowieka (`status = published` w bazie lokalnej), cytaty 5/7, koszt całości $0,5934 |

Skąd wzięte: `council_sessions.transcript_json` / `.summary_json`, wiersz
`external_id = 7556`, baza lokalna, 26.08.2026.

## Użycie

```bash
# sam skrót na gotowym transkrypcie — zero kosztu Whispera
cd backend && python -m scripts.run_council_session \
    --transcript data/council/xxiii_2026-06-24.transcript.json
```

## Do czego się nadaje, a do czego nie

- ✅ praca nad promptem skrótu, bramką cytatów i weryfikacją opisów
- ✅ porównanie „przed / po" przy zmianie modelu albo promptu
- ❌ **nie jest testem pobierania i transkrypcji** — te dwa etapy omija w całości.
  Ścieżkę YouTube → audio → Whisper sprawdza dopiero przebieg na żywym adresie

## Kontrola treści z nagraniem (26.08.2026, przed publikacją na produkcji)

Każde zdanie skrótu skonfrontowane z transkryptem ręcznie, nie przez model.

**Cytaty — 5/5 dosłownych.** Każdy występuje w nagraniu słowo w słowo.

**Liczby — wszystkie potwierdzone:**

| twierdzenie skrótu | w nagraniu |
|---|---|
| kredyt 500 tys. zł, średni samochód dla OSP Rybno | `00:34:57` — dosłownie |
| kredyt 350 tys. zł, lekki samochód dla OSP Dębień | `00:37:58` — dosłownie |
| dotacja 60 tys. zł na łódź ratowniczą | `00:53:20` — potwierdzone |
| dotacja 63 tys. zł, dawny kościół parafialny i plebania w Rybnie | `00:54:11` — dosłownie |
| działka **w Koszelewach**, ok. **0,15 ha** | `00:59:40` — „obręb kosze lewy o powierzchni 0 przecinek 15 29 hektara" |

⚠️ Ostatni wiersz jest ważny dla przyszłych sprawdzeń: Whisper rozbił „Koszelewy"
na **„kosze lewy"**, więc szukanie po nazwie miejscowości w transkrypcie NIE
znajduje tego fragmentu. Brak trafienia w wyszukiwarce nie dowodzi, że model zmyślił.

**Znaleziona i naprawiona usterka:** punkt o działce miał znacznik `00:57:35` —
ten sam, co poprzedni punkt, bo wskazywał na ogłoszenie wyniku **poprzedniego**
głosowania. Poprawione na `00:57:50`, czyli moment, w którym przewodniczący
przechodzi do punktu siódmego. Poprawka naniesiona w tym pliku i w bazie lokalnej.

**Do naprawy w mechanizmie:** nic nie pilnuje, żeby dwa punkty nie dostały tego
samego znacznika. `verify_against_transcript` prostuje znacznik do miejsca cytatu,
a gdy cytatem jest formuła „za podjęciem uchwały głosowało…", trafia w koniec
poprzedniej sprawy. Bramka na duplikaty jest tania i wyłapałaby dokładnie ten błąd.

## Pozostałe obserwacje

- **„OSP w Hartowcu"** — nagranie mówi konsekwentnie „w **Kartowsku**" (`00:53:25`,
  `00:53:46`, `00:54:02`). Wsi Kartowsko w gminie nie ma, Hartowiec jest — model
  poprawił przekręcenie Whispera i zrobił dobrze, ale to znaczy, że opis nie jest
  w tym miejscu dosłowny. Sędzia zgłosił to jako rozbieżność i miał rację formalnie
- cytat „Dziękuję bardzo. Za podjęciem uchwały głosowało 12 radnych." jest prawdziwy,
  ale nic nie mówi — cytatem bywa formuła przewodniczącego zamiast zdania z dyskusji
- `resolutions[].number` puste we wszystkich pozycjach: numer uchwały nie pada
  w nagraniu, dokleja się go z rejestru aktów po dacie sesji
