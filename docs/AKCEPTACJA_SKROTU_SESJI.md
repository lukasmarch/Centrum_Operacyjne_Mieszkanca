# Akceptacja skrótu obrad — lista kontrolna

*Spisane 26.08.2026, wieczorem przed XXIV sesją. Do otwarcia za każdym razem,
gdy na Telegramie pojawi się skrót do zatwierdzenia — nie tylko jutro.*

---

## Zanim skrót powstanie

Sesja kończy się orientacyjnie **1,5–3 h po rozpoczęciu** (XXIII trwała 86 minut).
Transmisja idzie na żywo, więc nagranie da się przepisać dopiero po jej zakończeniu.

```bash
# 1. sprawdzenie, czy transmisja się skończyła — nic nie kosztuje
cd backend && python -m scripts.run_council_session --url "<adres YouTube sesji>"
#    dopóki trwa: „Nagranie jeszcze nie do przepisania: transmisja trwa…"

# 2. gdy przejdzie — pełny przebieg z zapisem do kolejki akceptacji
python -m scripts.run_council_session --url "<adres YouTube sesji>" --save
```

Koszt: Whisper ~$0,006/min (90 minut ≈ $0,54) plus gpt-4o na skrót i sędziego.
Dla sesji XXIII całość wyszła **$0,59**.

Adres jutrzejszej sesji XXIV: `https://www.youtube.com/watch?v=ytBiBVzlduU`

---

## Gdy dostaniesz skrót do akceptacji

Wiadomość na Telegramie da Ci nagłówek, lead, tytuły punktów i licznik.
**Licznik nie jest zgodą na publikację.** Przejdź to tak:

**1. Każde nazwisko z osobna.** Bramka mówi tylko, że nazwisko gdzieś w oknie
padło — nie że mówiła ta osoba. Przy każdym `speaker` otwórz znacznik i posłuchaj
piętnastu sekund. Nie zgadza się albo nie masz pewności — **skasuj samo nazwisko,
punkt zostaw**. Skrót bez nazwiska jest pełnowartościowy, z cudzym nazwiskiem
jest szkodą.

**2. Czy w skrócie jest ktokolwiek spoza Rady i urzędu.** Prompt ma to teraz
wyłączone, ale prompt to instrukcja, nie mechanizm — a wolne wnioski są na końcu
sesji, czyli w części, którą model widzi w całości. Jeśli padnie mieszkaniec ze
swoją sprawą: usuń nazwisko i okoliczności osobiste, zostaw samą sprawę publiczną.

**3. Zdania oznaczone przez sędziego.** Każde sprawdź w nagraniu. Na sesji XXIII
trzy takie były i jedno z nich było fałszywym alarmem („OSP w Hartowcu" — Whisper
przekręcił na „Kartowsko"). Oznaczenie to pytanie, nie wyrok.

**4. Duplikaty znaczników.** Nadal nic nie pilnuje, żeby dwa punkty nie dostały
tego samego czasu — na XXIII właśnie tak było i wskazywało na koniec poprzedniej
sprawy. Rzuć okiem na listę znaczników: powtórzony to sygnał, że jeden punkt jest
zakotwiczony w złym miejscu.

**5. Dopiero potem publikuj.** I to jest ta rzecz, o której mówi analiza RODO przy
AI Act: zwolnienie z art. 50 ust. 4 kupuje **realna** kontrola redakcyjna, nie
kliknięcie „Publikuj". Pięć minut czytania raz w miesiącu jest ceną tego zwolnienia.

Jeśli zobaczysz **`USUNIĘTE NAZWISKA BEZ POKRYCIA`** — to znaczy, że bramka
zadziałała i model rzeczywiście zgadywał. Warto to zgłosić: to sygnał do
przykręcenia reguły 4 w prompcie.

---

## Co znaczą liczniki w wiadomości

| licznik | co mówi | kiedy to problem |
|---|---|---|
| `cytaty X/Y potwierdzonych` | ile cytatów naprawdę padło w nagraniu | X < Y znaczy, że reszta została **wycięta** — nie poprawiona |
| `USUNIĘTE ZMYŚLONE CYTATY` | ile zdań brzmiało jak cytat, a nie padło | zawsze warto wiedzieć; poniżej 50 % skuteczności — prompt do poprawy |
| `USUNIĘTE NAZWISKA BEZ POKRYCIA` | ile razy model przypisał mówcę bez oparcia w nagraniu | każde wystąpienie to sygnał, patrz wyżej |
| `zdania opisów N/M bez zastrzeżeń` | druga bramka: opisy konfrontowane z fragmentem nagrania | różnica to lista do ręcznego sprawdzenia (punkt 3) |
| `znaczniki poprawione` | ile znaczników przesunięto do sekundy cytatu | wysoka liczba jest normalna, nie jest błędem |

⚠️ **`publishable = True` nie znaczy „publikuj bez czytania".** Znaczy tylko, że ani
bramka cytatów, ani bramka nazwisk, ani zakreślacz opisów niczego nie podniosły.
Żadna z nich nie ocenia **doboru tematów** ani tego, czy skrót jest uczciwy wobec
przebiegu obrad.

---

## Gdzie ląduje zatwierdzony skrót

Na **rybnolive.pl/sesje** — rejestr obrad działa na produkcji od 26.08.2026.
`council_sessions` czyta wyłącznie `published`, więc do momentu akceptacji skrót
nie istnieje dla nikogo poza Tobą. Dotyczy to również agenta: `ai/tools/council.py`
nie sięga po nic poza `published`.

---

## Czego ta lista NIE załatwia

Trzy rzeczy zostają otwarte i warto o nich pamiętać, zanim mechanizm urośnie:

- **`retention_job` nie dotyka transkryptu.** Okres jest zapisany w polityce
  prywatności, ale kod go nie egzekwuje. Do zrobienia na spokojnie.
- **Transkrypt w RAG to osobna decyzja**, nie automatyczne rozszerzenie tego, co
  jest. Dziś transkrypt jest prywatny i służy weryfikacji cytatu. W RAG stałby się
  materiałem, z którego agent zacytuje dowolne zdanie z sali — także wypowiedź
  mieszkańca i to, co padło przy niewyłączonym mikrofonie.
- **Czy jesteśmy działalnością prasową** — jedyne pytanie z analizy RODO, którego
  nie rozstrzygnie się czytaniem kodu. Jeśli tak, art. 2 ust. 1 ustawy z 10.05.2018
  wyłącza wobec nas sporą część RODO. Warte godziny prawnika.

*Podstawa mechanizmu: `backend/src/scheduler/council_job.py`,
`backend/src/ai/council_summary.py`. Materiał odniesienia i wynik kontroli treści
sesji XXIII: `backend/data/council/README.md`.*
