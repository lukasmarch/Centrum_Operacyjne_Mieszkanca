"""
Strażnik deduplikacji feedu — 29 par z produkcji, oznaczonych ręcznie.

Dlaczego ten test w ogóle powstał: powtórki wracały do feedu czterokrotnie
(12.08.2026 azbest w czterech redakcjach, 24.08 dwa pushe o jednej awarii,
3.09 przedruk Syli, 14.09 pobór krwi i zebranie wiejskie po dwa razy),
a `collapse_duplicates` nie miał ANI JEDNEGO własnego testu — sprawdzał go
mimochodem `test_grounding.py` na dwóch sztucznych wpisach. Każdy nawrót
wychodził więc dopiero na stronie, u mieszkańca.

Test mierzy OBIE strony naraz i to jest jego sedno. Sama liczba zwiniętych
powtórek niczego nie dowodzi: zwinąć wszystko potrafi próg zerowy. Dlatego
obok „ile duplikatów zwinięto" stoi „ile RÓŻNYCH wiadomości sklejono" —
i drugi licznik jest ważniejszy, bo jego błąd UKRYWA przed mieszkańcem
informację, podczas gdy błąd pierwszego tylko ją powtarza.

⚠️ Pary są oznaczone RĘCZNIE i to jest w tym teście najcenniejsze. Nie wolno
zmieniać etykiety, żeby test przeszedł — etykieta mówi, co widzi mieszkaniec,
a nie co potrafi kod. Jeśli zmiana progu przewraca parę, to jest wynik testu,
nie usterka danych.

Skąd biorą się liczby `podobienstwo`: zmierzone 14.09.2026 na produkcji,
`document_embeddings` (source_type='article', chunk 0), cosinus między parami.
Test nie woła modelu — odtwarza zmierzony kąt dwuwymiarowym wektorem, bo
`same_story` pyta wyłącznie o cosinus.

Zakresy, które unieważniają każdy pojedynczy próg (i dlatego ten test pilnuje
REGUŁY, nie liczby):
    zawieranie rdzeni   duplikaty 0,67–1,00   różne 0,71–1,00
    embedding           duplikaty 0,70–0,89   różne 0,50–0,89

Użycie:
    cd backend && python -m scripts.test_feed_dedup [--pary] [--db]

    --pary  wypisz każdą parę z osiami, nie tylko błędy
    --db    dołóż przebieg na ŻYWYM feedzie produkcyjnym (wymaga DATABASE_URL)

Kod wyjścia 1 przy jakimkolwiek błędzie.
"""
import argparse
import asyncio
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services.feed_policy import (  # noqa: E402
    SEMANTIC_DUPLICATE,
    StoryKey,
    _containment,
    _place_axis,
    _stem_tokens,
    _term_axis,
    _tokens,
    collapse_duplicates,
    same_story,
)


def _dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.strptime(value, "%Y-%m-%d %H:%M") if value else None


def _wektory(cosinus: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """
    Dwa wektory o zadanym cosinusie. Dwuwymiarowe celowo: `same_story` pyta
    o KĄT, więc odtworzenie kąta jest wierniejsze od wklejenia 1536 liczb,
    które i tak zestarzałyby się przy pierwszej zmianie modelu osadzeń.
    """
    kat = math.acos(max(-1.0, min(1.0, cosinus)))
    return (1.0, 0.0), (math.cos(kat), math.sin(kat))


@dataclass
class Para:
    etykieta: str          # DUP = jedna sprawa, ROZNE = dwie różne wiadomości
    podobienstwo: float    # cosinus zmierzony na produkcji
    a_id: int
    b_id: int
    a_tytul: str
    b_tytul: str
    a_termin: Optional[str] = None
    a_koniec: Optional[str] = None
    b_termin: Optional[str] = None
    b_koniec: Optional[str] = None
    granica: Optional[str] = None
    """
    Powód, dla którego kod orzeka DZIŚ inaczej, niż mówi etykieta — świadoma
    granica, nie usterka do przemilczenia. Etykiety nie wolno pod kod naginać:
    mówi, co widzi mieszkaniec.

    Test pilnuje takiej pary z DWÓCH stron. Rozbieżność z powodem nie psuje
    wyniku, ale para, która zaczęła być orzekana POPRAWNIE, psuje go celowo —
    wtedy adnotację trzeba skasować. Bez tego lista wyjątków tylko rośnie
    i po pół roku test zielenieje na wszystkim.
    """

    def klucze(self) -> tuple[StoryKey, StoryKey]:
        emb_a, emb_b = _wektory(self.podobienstwo)
        return (
            _klucz(self.a_tytul, self.a_termin, self.a_koniec, emb_a),
            _klucz(self.b_tytul, self.b_termin, self.b_koniec, emb_b),
        )


def _klucz(tytul, termin, koniec, embedding) -> StoryKey:
    from src.services.alert_policy import places_in

    tokens = _tokens(tytul)
    return StoryKey(
        tokens=tokens,
        stems=_stem_tokens(tokens),
        event_at=_dt(termin),
        event_until=_dt(koniec),
        places=frozenset(places_in(tytul, None)),
        embedding=embedding,
    )


# ── Pary z produkcji ─────────────────────────────────────────────────────────
PARY: list[Para] = [
    Para(
        etykieta="ROZNE", podobienstwo=0.887,
        a_id=5887, b_id=5909,
        a_tytul="Planowane wyłączenie prądu 15 września, 08:00–17:00 — Lipówka, Mosznica, Sławkowo",
        b_tytul="Planowane wyłączenie prądu 15 września, 09:30–15:00 — Przełęk, Przełęk Mały",
        a_termin="2026-09-15 06:00", a_koniec="2026-09-15 15:00",
        b_termin="2026-09-15 07:30", b_koniec="2026-09-15 13:00",
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.869,
        a_id=5987, b_id=5988,
        a_tytul="Wyłączenie prądu 13 września, 17:48–20:30 — Wysoka",
        b_tytul="Wyłączenie prądu 13 września, 17:48–20:30 — Prioma, Rutkowice",
        a_termin="2026-09-13 15:48", a_koniec="2026-09-13 18:30",
        b_termin="2026-09-13 15:48", b_koniec="2026-09-13 18:30",
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.863,
        a_id=5836, b_id=5945,
        a_tytul="Zasady bezpieczeństwa dla rowerzystów na drogach",
        b_tytul="Bezpieczeństwo rowerzystów na drogach. Przestrzegaj przepisów",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.837,
        a_id=5501, b_id=5958,
        a_tytul="Restauracja Świtezianka zaprasza na dzisiejsze danie dnia",
        b_tytul="Restauracja Świtezianka oferuje danie dnia za 30 zł",
        a_termin="2026-08-20 22:00", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.82,
        a_id=5886, b_id=5997,
        a_tytul="Planowane wyłączenie prądu 14 września, 08:00–17:00 — Lipówka, Mosznica, Sławkowo",
        b_tytul="Wyłączenie prądu 14 września, 12:37–15:15 — Białuty, Białuty-Kolonia",
        a_termin="2026-09-14 06:00", a_koniec="2026-09-14 15:00",
        b_termin="2026-09-14 10:37", b_koniec="2026-09-14 13:15",
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.791,
        a_id=5892, b_id=5917,
        a_tytul="Mieszkanka powiatu działdowskiego straciła 3400 zł na oszustwie internetowym",
        b_tytul="Ostrzeżenie przed oszustwami w internecie dla mieszkańców powiatu działdowskiego",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.763,
        a_id=5438, b_id=5470,
        a_tytul="Mławianka Mława podejmuje Lechię Tomaszów Mazowiecki w III Lidze",
        b_tytul="Mławianka Mława przegrywa z Lechią Tomaszów 2:3 w III Lidze",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
        granica=(
            "stan zastany: zawieranie rdzeni 0,857 przy progu 0,85 — zapowiedź meczu i relacja z niego. Dla mieszkańca to jedna sprawa, więc zwinięcie nie boli; obniżenie progu byłoby jednak nie do obrony"
        ),
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.753,
        a_id=5924, b_id=5931,
        a_tytul="Delfin Rybno pokonał UKS BSS Iława 12:2 w meczu trampkarzy",
        b_tytul="Mecz GSZS Delfin Rybno z UKS BSS Iława o 17:00",
        a_termin="2026-09-08 22:00", a_koniec=None,
        b_termin="", b_koniec=None,
        granica=(
            "stan zastany, ten sam wzorzec co 5438/5470 (zapowiedź meczu + jego wynik)"
        ),
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.745,
        a_id=5671, b_id=5695,
        a_tytul="Natalia Zakrzewska z Hartowca walczy w Pucharze Świata w Budapeszcie",
        b_tytul="Natalia Zakrzewska zdobyła brązowy medal na Pucharze Świata w Budapeszcie",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.744,
        a_id=5386, b_id=5470,
        a_tytul="Mławianka Mława przegrywa z KTS Weszło 1:5 w III lidze",
        b_tytul="Mławianka Mława przegrywa z Lechią Tomaszów 2:3 w III Lidze",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.741,
        a_id=5671, b_id=5690,
        a_tytul="Natalia Zakrzewska z Hartowca walczy w Pucharze Świata w Budapeszcie",
        b_tytul="Natalia Zakrzewska z Hartowca zdobywa złoto w Pucharze Świata WAKO",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.641,
        a_id=5870, b_id=5872,
        a_tytul="Turniej tenisa stołowego w Jeżewie z udziałem 50 zawodników",
        b_tytul="XIX Ogólnopolski Turniej Tenisa Stołowego w Jeżewie 8 września",
        a_termin="", a_koniec=None,
        b_termin="2026-09-07 22:00", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.634,
        a_id=5746, b_id=5752,
        a_tytul="Obchody 87. rocznicy wybuchu II wojny światowej",
        b_tytul="Olsztyn obchodzi 87. rocznicę wybuchu II wojny światowej",
        a_termin="2026-08-31 22:00", a_koniec=None,
        b_termin="", b_koniec=None,
        granica=(
            "stan zastany i REALNY błąd: zawieranie rdzeni 1,000 przy dwóch różnych MIASTACH (Rybno vs Olsztyn). Oś miejsca milczy, bo places_in zna wyłącznie wsie gminy, a żaden z wpisów ich nie wymienia. Naprawa wymaga rozpoznawania miejscowości spoza gminy — osobna praca, patrz TODO"
        ),
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.579,
        a_id=5743, b_id=5848,
        a_tytul="Znaleziono psa w Gminie Rybno, poszukiwany właściciel",
        b_tytul="Bransoletka znaleziona na chodniku w Rybnie, właściciel poszukiwany",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.533,
        a_id=5456, b_id=6004,
        a_tytul="Charytatywny turniej piłki nożnej i piknik w Tuczkach dla zwierząt",
        b_tytul="Funkcjonariusze z Działdowa na II Charytatywnym Turnieju Piłki Nożnej",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="ROZNE", podobienstwo=0.496,
        a_id=5385, b_id=5793,
        a_tytul="Turniej rycerski w Działdowie przyciągnął tłumy miłośników historii",
        b_tytul="Wernisaż sztuki przyciągnął miłośników w Działdowie",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.891,
        a_id=5808, b_id=5906,
        a_tytul="Nabór do programu Warmińsko-Mazurski Czek Turystyczny od 7 września",
        b_tytul="Nabór do programu Warmińsko-Mazurski Czek Turystyczny trwa do 17 września 2026",
        a_termin="2026-09-16 22:00", a_koniec=None,
        b_termin="2026-09-16 22:00", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.89,
        a_id=5707, b_id=5745,
        a_tytul="Bezpłatne badania mammograficzne w Rybnie 20 września",
        b_tytul="Bezpłatne badania mammograficzne 20 września w Rybnie",
        a_termin="2026-09-19 22:00", a_koniec=None,
        b_termin="2026-09-19 22:00", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.889,
        a_id=5654, b_id=5655,
        a_tytul="Kradzież dożynkowych świnek w Rybnie, sołtys jedzie je odbierać",
        b_tytul="Kradzież dożynkowych świnek w Rybnie, sołtys jedzie po nie",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.888,
        a_id=5628, b_id=5810,
        a_tytul="Oficjalne otwarcie nowej drogi transportu rolnego w Hartowcu",
        b_tytul="Oficjalne otwarcie przebudowanej drogi w Hartowcu",
        a_termin="2026-08-25 22:00", a_koniec=None,
        b_termin="", b_koniec=None,
        granica=(
            "jeden wpis z terminem, drugi bez, więc oś czasu milczy i dowód semantyczny (0,888) nie ma prawa orzekać. Zmierzone: poluzowanie tego wymagania wpuszcza cotygodniowe danie dnia tej samej restauracji (0,837) i dwie kampanie KPP (0,863)"
        ),
    ),
    Para(
        etykieta="DUP", podobienstwo=0.878,
        a_id=5679, b_id=5689,
        a_tytul="Czasowe wyłączenie wody w Rybnie i okolicach 31 sierpnia",
        b_tytul="Czasowe wyłączenie wody w Rybnie i okolicach 31 sierpnia",
        a_termin="2026-08-31 07:00", a_koniec="2026-08-31 13:00",
        b_termin="2026-08-30 22:00", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.855,
        a_id=5496, b_id=5595,
        a_tytul="Planowane wyłączenie prądu 25 sierpnia, 10:00–15:00 — Rybno: Kościelna, Lubawska, Stroma, Wyzwolenia i inne",
        b_tytul="Planowane wyłączenie prądu w Rybnie 25 sierpnia 2026 roku",
        a_termin="2026-08-25 08:00", a_koniec="2026-08-25 13:00",
        b_termin="2026-08-25 08:00", b_koniec="2026-08-25 13:00",
    ),
    Para(
        etykieta="DUP", podobienstwo=0.854,
        a_id=5770, b_id=5875,
        a_tytul="Pobór krwi w Rybnie w dniu 16 września 2026 w godzinach 8:00–11:30",
        b_tytul="Pobór krwi 16 września w Zespole Szkół w Rybnie",
        a_termin="2026-09-16 06:00", a_koniec="2026-09-16 09:30",
        b_termin="2026-09-15 22:00", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.845,
        a_id=5985, b_id=5986,
        a_tytul="Warsztaty Cariboo w Gminie Rybno łączą zabawę i aktywność fizyczną",
        b_tytul="Warsztaty jazdy na rowerze dla dzieci w Gminie Rybno",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
        granica=(
            "oba bez terminu, a model nadał tej samej imprezie nagłówki bez wspólnych słów (warsztaty Cariboo kontra warsztaty jazdy na rowerze) — tekst 0,400. Rozstrzygnąłby embedding (0,845), ale bez osi czasu nie jest wiarygodny"
        ),
    ),
    Para(
        etykieta="DUP", podobienstwo=0.843,
        a_id=5476, b_id=5547,
        a_tytul="Turniej charytatywny o Puchar Budmar w Tuczkach 23 sierpnia",
        b_tytul="Turniej Charytatywny o Puchar Budmar w Tuczkach 23 sierpnia",
        a_termin="2026-08-23 07:00", a_koniec=None,
        b_termin="2026-08-23 07:00", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.807,
        a_id=5390, b_id=5392,
        a_tytul="Odpust i dożynki w Parafii pw. św. Barbary w Rumianie zakończone",
        b_tytul="Odpust i Dożynki w Rumianie 16 sierpnia",
        a_termin="", a_koniec=None,
        b_termin="2026-08-16 10:00", b_koniec=None,
        granica=(
            "jeden wpis z terminem, drugi bez — ten sam powód co 5628/5810"
        ),
    ),
    Para(
        etykieta="DUP", podobienstwo=0.743,
        a_id=5499, b_id=5502,
        a_tytul="Zebranie wiejskie w Rybnie w sprawie Funduszu Sołeckiego na 2027 rok",
        b_tytul="Zebranie wiejskie w Rybnie 17 września w sprawie funduszu sołeckiego na 2027 rok",
        a_termin="", a_koniec=None,
        b_termin="2026-09-16 22:00", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.717,
        a_id=5502, b_id=5856,
        a_tytul="Zebranie wiejskie w Rybnie 17 września w sprawie funduszu sołeckiego na 2027 rok",
        b_tytul="Zebranie wiejskie w Rybnie dotyczące Funduszu Sołeckiego",
        a_termin="2026-09-16 22:00", a_koniec=None,
        b_termin="2026-09-17 16:00", b_koniec=None,
    ),
    Para(
        etykieta="DUP", podobienstwo=0.702,
        a_id=5990, b_id=6003,
        a_tytul="KS Dekorglass Działdowo przegrał z Orliczem Suchedniów w Lotto Superlidze",
        b_tytul="Dekorglass Działdowo przegrywa 1:3 w Superlidze tenisistów stołowych",
        a_termin="", a_koniec=None,
        b_termin="", b_koniec=None,
        granica=(
            "oba bez terminu, dwie redakcje relacji z tego samego meczu; embedding 0,702 leży na samym progu, a RÓŻNE mecze tego samego klubu mają 0,744–0,763"
        ),
    ),]


def _os_czasu(a: StoryKey, b: StoryKey) -> str:
    wynik = _term_axis(a, b)
    return {None: "—", True: "zgodny", False: "WETO"}[wynik]


def _os_miejsca(a: StoryKey, b: StoryKey) -> str:
    wynik = _place_axis(a, b)
    return {None: "—", True: "wspólne", False: "WETO"}[wynik]


def sprawdz_pary(pokaz_wszystkie: bool) -> tuple[int, int, list[str]]:
    trafione = puszczone = 0
    bledy: list[str] = []

    print("=" * 78)
    print("PARY OZNACZONE RĘCZNIE (produkcja, 30 dni)")
    print("=" * 78)

    for para in PARY:
        a, b = para.klucze()
        orzeczenie = same_story(a, b)
        oczekiwane = para.etykieta == "DUP"
        zgodne = orzeczenie == oczekiwane

        if oczekiwane and orzeczenie:
            trafione += 1
        if not oczekiwane and orzeczenie:
            puszczone += 1

        if zgodne and para.granica:
            print(f"! [{para.etykieta:<5}] {para.a_id}/{para.b_id} orzekana już poprawnie "
                  f"— skasuj adnotację `granica`")
            bledy.append(
                f"{para.a_id}/{para.b_id}: granica zniknęła, usuń adnotację "
                f"({para.granica})"
            )
            continue

        if not zgodne or pokaz_wszystkie:
            znak = "✓" if zgodne else ("~" if para.granica else "✗")
            zaw = _containment(a.stems, b.stems) if min(len(a.stems), len(b.stems)) >= 5 else 0.0
            print(
                f"{znak} [{para.etykieta:<5}] {para.a_id}/{para.b_id}  "
                f"czas={_os_czasu(a, b):<7} miejsce={_os_miejsca(a, b):<8} "
                f"tekst={zaw:.2f} embed={para.podobienstwo:.2f} "
                f"→ {'zwija' if orzeczenie else 'zostawia'}"
            )
            print(f"    A: {para.a_tytul[:66]}")
            print(f"    B: {para.b_tytul[:66]}")
            if not zgodne:
                if para.granica:
                    print(f"    ~ znana granica: {para.granica}")
                else:
                    bledy.append(
                        f"{para.a_id}/{para.b_id} oznaczone jako {para.etykieta}, "
                        f"kod {'zwija' if orzeczenie else 'zostawia'}"
                    )

    return trafione, puszczone, bledy


def sprawdz_reguly() -> list[str]:
    """
    Reguły, które mają obowiązywać niezależnie od dzisiejszych danych.
    Para z produkcji dowodzi, że coś działa DZIŚ; te sprawdzenia mówią,
    co ma zostać prawdą po następnej zmianie progu.
    """
    bledy: list[str] = []

    def spr(warunek: bool, opis: str) -> None:
        print(f"  {'✓' if warunek else '✗'} {opis}")
        if not warunek:
            bledy.append(opis)

    print("\n" + "=" * 78)
    print("REGUŁY UKŁADU OSI")
    print("=" * 78)

    emb_a, emb_b = _wektory(0.99)
    tytul = "Zebranie wiejskie w Rybnie w sprawie funduszu sołeckiego"

    # 1. Weto czasu bije dowolnie wysokie podobieństwo
    a = _klucz(tytul, "2026-09-17 16:00", None, emb_a)
    b = _klucz(tytul, "2026-09-24 16:00", None, emb_b)
    spr(not same_story(a, b), "różne doby zdarzenia = nie duplikat, choćby tekst był identyczny")

    # 2. Ta sama doba, obie godziny znane i różne → weto
    a = _klucz(tytul, "2026-09-17 08:00", "2026-09-17 10:00", emb_a)
    b = _klucz(tytul, "2026-09-17 12:00", "2026-09-17 14:00", emb_b)
    spr(not same_story(a, b), "ta sama doba, różne godziny znane obu stronom = nie duplikat")

    # 3. Dokładność SŁABSZEGO terminu — zapowiedź całodniowa vs z godziną
    calodniowy = _klucz(tytul, "2026-09-16 22:00", None, emb_a)   # lokalna północ 17.09
    z_godzina = _klucz(tytul, "2026-09-17 16:00", None, emb_b)
    spr(same_story(calodniowy, z_godzina),
        "zapowiedź bez godziny i ta sama zapowiedź z godziną = jedna sprawa")

    # 4. Weto miejsca bije wysokie podobieństwo
    a = _klucz("Wyłączenie prądu w Rybnie", "2026-09-17 08:00", None, emb_a)
    b = _klucz("Wyłączenie prądu w Tuczkach", "2026-09-17 08:00", None, emb_b)
    spr(not same_story(a, b), "rozłączne miejscowości gminy = nie duplikat")

    # 5. Semantyka NIE orzeka sama — bez zgodnego terminu nie wystarcza
    a = _klucz("Delfin Rybno przegrywa z Iławą", None, None, emb_a)
    b = _klucz("Mecz Delfina z Iławą o 17:00", None, None, emb_b)
    spr(not same_story(a, b),
        f"embedding {0.99} bez zgodnego terminu NIE zwija (próg {SEMANTIC_DUPLICATE})")

    # 6. Brak embeddingu nie zmienia reguł — tylko zawęża
    a = _klucz(tytul, "2026-09-17 16:00", None, None)
    b = _klucz(tytul, "2026-09-17 16:00", None, None)
    spr(same_story(a, b), "bez embeddingu wpisy nadal zwija oś tekstu")

    # 7. Przebieg po liście zostawia pozycję WCZEŚNIEJSZĄ (kolejność = ranking)
    class Wpis:
        def __init__(self, ident, tytul, termin=None):
            self.id = ident
            self.display_title = tytul
            self.title = tytul
            self.content = None
            self.event_at = _dt(termin)
            self.event_until = None

    from src.services.feed_policy import story_key

    wpisy = [
        Wpis(1, "Pobór krwi w Rybnie 16 września o 8:00", "2026-09-16 06:00"),
        Wpis(2, "Pobór krwi 16 września w Zespole Szkół w Rybnie", "2026-09-15 22:00"),
    ]
    zostalo = collapse_duplicates(wpisy, key_of=lambda w: story_key(w))
    spr([w.id for w in zostalo] == [1],
        "z pary zostaje wpis stojący wyżej w rankingu")

    return bledy


async def sprawdz_na_bazie() -> list[str]:
    """Przebieg na ŻYWYM feedzie — ile powtórek zostaje po orzekaniu."""
    from sqlalchemy import select
    from src.database.connection import async_session
    from src.database.schema import Article, Source
    from src.services.feed_policy import publishable_conditions, story_key

    print("\n" + "=" * 78)
    print("ŻYWY FEED")
    print("=" * 78)

    bledy: list[str] = []
    async with async_session() as session:
        wynik = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(*publishable_conditions(Article))
            .where(Article.published_at >= datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0))
        )
        wiersze = list(wynik)
        if not wiersze:
            print("  (brak artykułów z dzisiaj — nic do sprawdzenia)")
            return bledy

        osadzenia = await _pobierz_embeddingi(session, [a.id for a, _ in wiersze])
        zostalo = collapse_duplicates(
            wiersze,
            key_of=lambda w: story_key(w[0], osadzenia.get(w[0].id)),
        )
        zwiniete = len(wiersze) - len(zostalo)
        print(f"  artykułów: {len(wiersze)}, zwiniętych jako powtórki: {zwiniete}")
        for artykul, zrodlo in wiersze:
            if not any(artykul.id == a.id for a, _ in zostalo):
                print(f"    − {artykul.id} [{zrodlo}] "
                      f"{(artykul.display_title or artykul.title or '')[:56]}")
    return bledy


async def _pobierz_embeddingi(session, ids: list[int]) -> dict[int, tuple[float, ...]]:
    from src.services.feed_policy import fetch_article_embeddings

    return await fetch_article_embeddings(session, ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pary", action="store_true", help="wypisz wszystkie pary")
    parser.add_argument("--db", action="store_true", help="przebieg na żywym feedzie")
    args = parser.parse_args()

    trafione, puszczone, bledy = sprawdz_pary(args.pary)
    bledy += sprawdz_reguly()

    if args.db:
        bledy += asyncio.run(sprawdz_na_bazie())

    duplikaty = sum(1 for p in PARY if p.etykieta == "DUP")
    rozne = sum(1 for p in PARY if p.etykieta == "ROZNE")

    print("\n" + "=" * 78)
    print(f"Duplikaty zwinięte:        {trafione}/{duplikaty}")
    print(f"Różne wiadomości sklejone: {puszczone}/{rozne}   ← ten licznik boli bardziej")
    print("=" * 78)

    if bledy:
        print(f"\n❌ {len(bledy)} rozbieżności:")
        for blad in bledy:
            print(f"   • {blad}")
        return 1
    print("\n✅ Wszystko zgodne z oznaczeniem")
    return 0


if __name__ == "__main__":
    sys.exit(main())
