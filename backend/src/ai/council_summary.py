"""
Skrót sesji Rady Gminy — transkrypt obrad → punkty, które coś mieszkańcowi mówią.

Trzy godziny obrad to ~100 tys. znaków. Nikt tego nie przeczyta, więc jawność
obrad jest formalna. Skrót zamienia ją w faktyczną: sześć punktów, przy każdym
znacznik czasu i link do minuty w nagraniu.

**Dlaczego weryfikacja cytatów jest tu osobnym krokiem, a nie zdaniem w prompcie.**
5.08.2026 czterdziestoznakowy post o restauracji „RyBaśka" wyszedł z kategoryzacji
jako „nowa, otwarta restauracja regionalnych smaków w Rybnie" — model nie miał
z czego wypełnić obowiązkowych pól, więc je wymyślił, a briefing przepisał to jako
fakt. Tam kosztowało to wiarygodność jednego wpisu. Tutaj stawką jest zdanie
przypisane imiennie radnemu albo wójtowi, czego nie powiedzieli. Stąd trzy reguły
konstrukcyjne:

1. `quote` i `speaker` są OPCJONALNE. Pole obowiązkowe, którego nie da się
   wypełnić z materiału, zmusza model do konfabulacji — to jedyne wyjście, jakie
   mu zostawiamy. Model ma prawo powiedzieć „nie wiem, kto to mówił".
2. Każdy cytat jest po wygenerowaniu SZUKANY w transkrypcie (`Transcript.locate`).
   Nie znaleziono — cytat leci, punkt zostaje. Prośba w prompcie to nie mechanizm.
3. Znacznik czasu punktu musi mieścić się w długości nagrania i jest korygowany
   do znacznika znalezionego cytatu, gdy oba istnieją.
4. **Każde zdanie opisu** jest konfrontowane z fragmentem nagrania wokół znacznika
   (`verify_descriptions`). Zdanie bez pokrycia znika z opisu.
   Ta bramka powstała 9.08.2026, bo reguły 1-3 okazały się niewystarczające:
   przy raporcie „5/7 cytatów, zero zmyślonych" model dwa razy z rzędu, w dwóch
   niezależnych przebiegach na tej samej sesji, dopisał działce w Koszelewach
   przeznaczenie („cele rekreacyjne"), o którym w nagraniu nie pada ani słowo.
   Wniosek ogólny: pole, którego nic nie sprawdza, prędzej czy później skłamie.

`QualityReport` zlicza, ile model zmyślił. To nie jest metryka do schowania —
przy pierwszym uruchomieniu na nowej sesji jest jedynym sygnałem, czy skrót
nadaje się do publikacji bez czytania trzech godzin transkryptu.

Test: `cd backend && python -m scripts.test_council_summary`
"""
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.config import settings
from src.services.council_transcript import Transcript, normalize_quote
from src.utils.logger import setup_logger

logger = setup_logger("CouncilSummary")

# Ile punktów ma mieć skrót. Sesja rozstrzyga zwykle 5-15 spraw, z czego
# mieszkańca dotyczy kilka. Powyżej ośmiu robi się protokół, a protokół
# już jest — i nikt go nie czyta.
MAX_POINTS = 8

# Powyżej tylu znaków transkrypt nie mieści się bezpiecznie w oknie gpt-4o
# razem z odpowiedzią. Trzygodzinna sesja to ~110 tys. znaków, więc próg
# jest realny; `_condense` wycina wtedy środek i mówi o tym wprost.
MAX_TRANSCRIPT_CHARS = 260_000

COUNCIL_SUMMARY_PROMPT = """Jesteś redaktorem lokalnego serwisu informacyjnego dla mieszkańców gminy Rybno.
Dostajesz TRANSKRYPT nagrania sesji Rady Gminy ze znacznikami czasu w postaci [HH:MM:SS].

Twoim zadaniem jest napisać skrót dla mieszkańca, który nie ma trzech godzin na obejrzenie obrad.

ZASADY BEZWZGLĘDNE:
1. Opieraj się WYŁĄCZNIE na transkrypcie. Nie dopisuj tła, nie domyślaj się intencji,
   nie uzupełniaj wiedzą o tym, jak zwykle działają gminy.
2. Jeśli czegoś nie ma w transkrypcie — pomiń to. Nie pisz "prawdopodobnie", "zapewne".
3. Pole `quote` wypełniaj TYLKO cytatem przepisanym DOSŁOWNIE z transkryptu, słowo w słowo.
   Jeśli nie masz dosłownego cytatu — zostaw puste. Cytat zmyślony lub sparafrazowany
   zostanie wykryty i usunięty.
4. Pole `speaker` wypełniaj TYLKO, gdy z transkryptu jednoznacznie wynika, kto mówi
   (np. ktoś zwraca się do niego po nazwisku albo sam się przedstawia).
   W nagraniu obrad zwykle NIE da się tego ustalić — wtedy zostaw puste. To normalne.
5. Transkrypt jest automatyczny i bywa przekręcony. Gdy fragment jest niezrozumiały,
   nie zgaduj jego treści — pomiń.
6. Każdy punkt MUSI mieć znacznik czasu `timestamp` skopiowany z najbliższego
   znacznika [HH:MM:SS] poprzedzającego omawianą sprawę.

CZEGO SZUKASZ (w tej kolejności ważności dla mieszkańca):
- decyzje, które zmieniają czyjeś pieniądze, obowiązki albo otoczenie
  (stawki podatków i opłat, inwestycje, drogi, wodociąg, odpady, szkoły, fundusz sołecki),
- uchwały: numer, czego dotyczy, wynik głosowania — jeśli padł w nagraniu,
- sprawy zgłoszone przez radnych i sołtysów w wolnych wnioskach,
- terminy i zapowiedzi (co, kiedy).

CZEGO NIE PISZESZ:
- przebiegu proceduralnego (otwarcie, stwierdzenie kworum, przyjęcie protokołu),
  chyba że coś nietypowego się przy tym wydarzyło,
- podziękowań, powitań, życzeń.

STYL: rzeczowy, bez ozdobników, bez emoji, bez wykrzykników. Zdania krótkie.
Piszesz dla sąsiada, nie dla urzędu — ale bez spoufalania się i bez oceniania.
"""

DESCRIPTION_JUDGE_PROMPT = """Sprawdzasz, czy zdania ze skrótu obrad mają pokrycie we FRAGMENCIE nagrania.

Dostajesz fragment transkryptu sesji Rady Gminy i ponumerowane zdania, które ktoś
o tym fragmencie napisał. Dla KAŻDEGO zdania orzekasz, czy wynika z fragmentu.

Pytanie brzmi WYŁĄCZNIE: czy ktoś to we fragmencie powiedział. Nie oceniasz
stylu, ważności ani tego, czy zdanie jest prawdziwe w świecie.

ZDANIE MA POKRYCIE (supported = true), gdy fragment podaje tę treść — również:
- innymi słowami i w innej kolejności (parafraza to pokrycie),
- w formie zniekształconej przez automatyczną transkrypcję. Transkrypcja jest
  maszynowa i przekręca nazwy fonetycznie: „obręb kosze lewy" to Koszelewy,
  „Krajowy Ośrodek Sprawiedliwości Rolnictwa" to KOWR, „0 przecinek 15 29
  hektara" to 0,15 ha, „sto tysięcy" to 100 tys.
- jako wniosek z wprost podanych liczb. Jeśli padło „głosowało 12 radnych, nikt
  nie był przeciw", to zdanie „przyjęto jednogłośnie" MA pokrycie. Jeśli padło
  „dotacja 60 tysięcy złotych", to „w kwocie 60 tys. zł" MA pokrycie.

ZDANIE NIE MA POKRYCIA (supported = false) w JEDNYM przypadku: wnosi konkret,
którego we fragmencie nie ma w żadnej postaci — przeznaczenie, cel, uzasadnienie,
skutek, kwotę, nazwę miejsca albo osoby, o których nikt nie mówi.
Typowy przykład: „działka zostanie zagospodarowana na cele rekreacyjne", gdy
we fragmencie mowa wyłącznie o nieodpłatnym nabyciu nieruchomości. Brzmi
sensownie, ale to domysł piszącego, nie treść obrad.

W polu `missing` napisz wtedy dokładnie, którego konkretu brakuje
(np. „przeznaczenie działki — mowa tylko o nabyciu").

Nie zgłaszaj zdania dlatego, że fragment mówi to mniej precyzyjnie albo innymi
słowami. Zgłaszaj wyłącznie dopisane fakty.

REGUŁA NADRZĘDNA — NAZWY MIEJSCOWOŚCI:
Nazwa miejscowości NIGDY nie jest powodem do zgłoszenia zdania. Transkrypcja
kaleczy je systematycznie („w Kartowsku" = Hartowiec, „obręb kosze lewy" =
Koszelewy), więc nie da się ich tą metodą sprawdzić. Gdy jedyną różnicą między
zdaniem a fragmentem jest nazwa miejscowości — zdanie MA pokrycie (true).
Miejscowości gminy Rybno: {places}."""


class SessionPoint(BaseModel):
    """Jedna sprawa z obrad."""

    title: str = Field(
        max_length=120,
        description="O co chodzi, w jednym zdaniu. Konkret na początku, bez emoji.",
    )
    description: str = Field(
        max_length=700,
        description="2-4 zdania: co ustalono, kogo to dotyczy, co z tego wynika. Tylko z transkryptu.",
    )
    timestamp: str = Field(
        description="Znacznik [HH:MM:SS] z transkryptu, w którym ta sprawa się zaczyna.",
    )
    quote: Optional[str] = Field(
        default=None,
        max_length=300,
        description=(
            "DOSŁOWNY cytat z transkryptu albo puste. Nigdy parafraza. "
            "Puste pole jest poprawną odpowiedzią."
        ),
    )
    speaker: Optional[str] = Field(
        default=None,
        max_length=100,
        description=(
            "Kto mówi — tylko gdy transkrypt mówi to wprost. "
            "Puste pole jest poprawną i najczęstszą odpowiedzią."
        ),
    )


class Resolution(BaseModel):
    """Uchwała poddana pod głosowanie."""

    subject: str = Field(max_length=250, description="Czego dotyczy uchwała.")
    number: Optional[str] = Field(
        default=None, max_length=60,
        description="Numer uchwały, jeśli padł w nagraniu. Inaczej puste.",
    )
    outcome: Optional[str] = Field(
        default=None, max_length=120,
        description="Wynik głosowania, jeśli padł (np. 'przyjęta jednogłośnie'). Inaczej puste.",
    )
    timestamp: Optional[str] = Field(default=None, description="Znacznik [HH:MM:SS] głosowania.")


class CouncilSummaryModel(BaseModel):
    """Skrót sesji — kształt odpowiedzi modelu."""

    headline: str = Field(
        max_length=120,
        description="Najważniejsza rzecz z sesji dla mieszkańca. Bez 'Sesja Rady Gminy' na początku.",
    )
    lead: str = Field(
        max_length=400,
        description="2-3 zdania: co się działo na sesji i co z tego wynika dla mieszkańców.",
    )
    points: List[SessionPoint] = Field(
        default_factory=list,
        description=f"Od 3 do {MAX_POINTS} spraw, od najważniejszej dla mieszkańca.",
    )
    resolutions: List[Resolution] = Field(
        default_factory=list,
        description="Uchwały, o których mowa w nagraniu. Puste, jeśli żadnej nie omawiano.",
    )
    is_substantive: bool = Field(
        default=True,
        description=(
            "False, gdy sesja była czysto formalna (kilka minut, jedna uchwała porządkowa) "
            "i skrót nie ma czego opowiedzieć."
        ),
    )


@dataclass
class QualityReport:
    """Ile z tego, co model napisał, dało się potwierdzić w transkrypcie."""

    quotes_total: int = 0
    quotes_verified: int = 0
    quotes_dropped: List[str] = field(default_factory=list)
    timestamps_fixed: int = 0
    timestamps_out_of_range: int = 0
    # Zdania opisów bez pokrycia w nagraniu (druga bramka, `verify_descriptions`)
    claims_total: int = 0
    claims_flagged: List[str] = field(default_factory=list)

    @property
    def quote_accuracy(self) -> Optional[float]:
        if not self.quotes_total:
            return None
        return round(self.quotes_verified / self.quotes_total, 3)

    @property
    def publishable(self) -> bool:
        """
        Czy maszyna nie ma do skrótu ŻADNYCH zastrzeżeń.

        Nazwa jest myląca historycznie i celowo zostawiona ostrożna: nawet True
        nie znaczy „opublikuj bez czytania". Znaczy tylko, że ani bramka cytatów,
        ani zakreślacz opisów niczego nie podniosły — a zakreślacz bywa
        niestabilny między przebiegami i nie ocenia doboru tematów.
        """
        return (
            not self.quotes_dropped
            and not self.claims_flagged
            and self.timestamps_out_of_range == 0
        )

    def describe(self) -> str:
        parts = [
            f"cytaty: {self.quotes_verified}/{self.quotes_total} potwierdzonych",
            f"zdania opisów: {self.claims_total - len(self.claims_flagged)}/{self.claims_total} bez zastrzeżeń",
            f"znaczniki poprawione: {self.timestamps_fixed}",
        ]
        if self.quotes_dropped:
            parts.append(f"USUNIĘTE ZMYŚLONE CYTATY: {len(self.quotes_dropped)}")
        if self.claims_flagged:
            parts.append(f"ZDANIA DO SPRAWDZENIA: {len(self.claims_flagged)}")
        if self.timestamps_out_of_range:
            parts.append(f"znaczniki poza nagraniem: {self.timestamps_out_of_range}")
        return " | ".join(parts)


@dataclass
class CouncilSummaryResult:
    """Zweryfikowany skrót + rachunek za wygenerowanie go."""

    summary: CouncilSummaryModel
    quality: QualityReport
    tokens_input: int = 0
    tokens_output: int = 0
    judge_tokens_input: int = 0
    judge_tokens_output: int = 0

    @property
    def cost_usd(self) -> float:
        """
        gpt-4o: $2,50 / $10 za mln tokenów (wejście / wyjście).
        Sędzia opisów chodzi na tym samym gpt-4o (patrz `_build_judge`) i dokłada
        ~$0,06 za sesję — całość zostaje w okolicy $0,65.
        """
        return round(
            (self.tokens_input + self.judge_tokens_input) * 2.5 / 1e6
            + (self.tokens_output + self.judge_tokens_output) * 10 / 1e6,
            4,
        )


_STAMP_RE = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")


def stamp_to_seconds(stamp: Optional[str]) -> Optional[float]:
    """`01:23:45` → 5025.0. None, gdy znacznika nie ma albo jest połamany.

    Publiczne, bo tej samej zamiany potrzebuje link `?t=` pod każdym punktem
    — a znacznik liczony dwa razy różnymi wzorami przestałby wskazywać to samo
    miejsce w nagraniu.
    """
    if not stamp:
        return None
    cleaned = stamp.strip().strip("[]")
    if not _STAMP_RE.match(cleaned):
        return None
    hours, minutes, seconds = (int(p) for p in cleaned.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def _seconds_to_stamp(total: float) -> str:
    value = int(max(total, 0))
    return f"{value // 3600:02d}:{(value % 3600) // 60:02d}:{value % 60:02d}"


def _condense(stamped: str) -> str:
    """
    Przycina transkrypt do okna modelu. Wycina środek, nie koniec: wolne wnioski
    i głosowania — czyli to, co mieszkańca dotyczy najbardziej — są na końcu sesji.
    """
    if len(stamped) <= MAX_TRANSCRIPT_CHARS:
        return stamped
    keep = MAX_TRANSCRIPT_CHARS // 2
    logger.warning(
        "Transkrypt %d zn. przekracza okno modelu — wycinam środek", len(stamped)
    )
    return (
        stamped[:keep]
        + "\n\n[...FRAGMENT POMINIĘTY — nagranie dłuższe niż okno analizy...]\n\n"
        + stamped[-keep:]
    )


def verify_against_transcript(
    summary: CouncilSummaryModel, transcript: Transcript
) -> QualityReport:
    """
    Konfrontuje skrót z transkryptem. Modyfikuje `summary` w miejscu:
    usuwa cytaty, których nie ma w nagraniu, i prostuje znaczniki czasu.

    To jedyny moment, w którym wychodzi na jaw, że model coś dopisał — prompt
    tego nie zagwarantuje, a mieszkaniec kliknie w znacznik i sprawdzi.
    """
    report = QualityReport()
    limit = transcript.duration_s or float("inf")

    def _stamp_to_seconds_safe(stamp: Optional[str]) -> Optional[float]:
        """Znacznik modelu jako wskazówka — poza nagraniem nie naprowadza na nic."""
        seconds = stamp_to_seconds(stamp)
        return seconds if seconds is not None and seconds <= limit else None

    def check_stamp(stamp: Optional[str]) -> Optional[str]:
        seconds = stamp_to_seconds(stamp)
        if seconds is None:
            return None
        if seconds > limit:
            report.timestamps_out_of_range += 1
            return None
        return _seconds_to_stamp(seconds)

    for point in summary.points:
        if point.quote:
            report.quotes_total += 1
            # Znacznik podany przez model jest zgrubny, ale mówi, o KTÓRĄ sprawę
            # chodzi — to on rozstrzyga, które z powtarzalnych głosowań cytujemy.
            located = transcript.locate(point.quote, near_s=_stamp_to_seconds_safe(point.timestamp))
            if located:
                report.quotes_verified += 1
                # Znacznik cytatu jest twardszy niż znacznik podany przez model:
                # wiemy, że w tej sekundzie te słowa naprawdę padły.
                if point.timestamp != located.stamp:
                    report.timestamps_fixed += 1
                point.timestamp = located.stamp
            else:
                report.quotes_dropped.append(point.quote[:120])
                logger.warning("Cytat nie występuje w nagraniu, usuwam: %r", point.quote[:120])
                point.quote = None
                point.speaker = None

        corrected = check_stamp(point.timestamp)
        if corrected is None:
            point.timestamp = "00:00:00"
        else:
            point.timestamp = corrected

    for resolution in summary.resolutions:
        resolution.timestamp = check_stamp(resolution.timestamp)

    return report


# Skróty, po których kropka NIE kończy zdania. Bez tej listy „500 tys. zł"
# rozpada się na dwa zdania, a sędzia dostaje do oceny urwany fragment.
_ABBREVIATIONS = (
    "tys", "mln", "mld", "zł", "gr", "art", "ust", "pkt", "poz", "nr", "r", "ok",
    "godz", "ha", "im", "ul", "tj", "np", "itd", "itp", "m.in", "dot", "woj",
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9])")


def split_sentences(text: str) -> List[str]:
    """
    Opis punktu → zdania do osobnej oceny.

    Jednostką weryfikacji jest zdanie, nie cały opis: gdy trzy zdania mają
    pokrycie, a czwarte jest dopisane, wyrzucenie całego opisu kosztowałoby
    mieszkańca trzy prawdziwe informacje.
    """
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text.strip())

    merged: List[str] = []
    for part in parts:
        tail = part.rstrip().rstrip(".").rsplit(" ", 1)[-1].lower()
        if merged and tail in _ABBREVIATIONS:
            merged[-1] = f"{merged[-1]} {part}"
        elif merged and merged[-1].rstrip().rstrip(".").rsplit(" ", 1)[-1].lower() in _ABBREVIATIONS:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return [s.strip() for s in merged if s.strip()]


class SentenceVerdict(BaseModel):
    """Orzeczenie o jednym zdaniu opisu."""

    index: int = Field(description="Numer zdania z listy wejściowej, licząc od 1.")
    supported: bool = Field(description="Czy zdanie wynika z podanego fragmentu nagrania.")
    missing: Optional[str] = Field(
        default=None, max_length=200,
        description="Gdy brak pokrycia: czego we fragmencie nie ma. Krótko.",
    )


class DescriptionVerdict(BaseModel):
    verdicts: List[SentenceVerdict] = Field(default_factory=list)


def _build_judge() -> Agent:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    # gpt-4o, choć zadanie wygląda na wąskie. Pierwsza wersja szła na
    # gpt-4o-mini i pomyliła się w OBIE strony na tej samej sesji: wycięła
    # „dotacja 60 tys. zł na łódź dla OSP Hartowiec" (fakt padł 48 sekund przed
    # znacznikiem) i przepuściła „cele rekreacyjne", czyli dokładnie tę
    # halucynację, dla której bramka powstała. Bramka, która tnie prawdę i
    # przepuszcza fałsz, jest gorsza niż jej brak — uczy klikać „publikuj"
    # bez czytania. $0,06 za sesję to tania różnica.
    # Lista miejscowości jest tu obowiązkowa, nie ozdobna: bez niej sędzia wyciął
    # prawdziwe zdanie o dotacji dla OSP w Hartowcu, bo Whisper zapisał tę nazwę
    # jako „w Kartowsku" i wyglądała na dopisaną. Jedna lista na projekt —
    # ta sama, po której chodzi bramka miejsca w alertach push.
    from src.services.alert_policy import GMINA_RYBNO_PLACES

    return Agent(
        "openai:gpt-4o",
        output_type=DescriptionVerdict,
        system_prompt=DESCRIPTION_JUDGE_PROMPT.format(
            places=", ".join(GMINA_RYBNO_PLACES)
        ),
        output_retries=2,
    )


# Słowa, które nic nie twierdzą o świecie — nie ma sensu szukać ich w nagraniu.
# Lista jest krótka z rozmysłem: im więcej wyjątków, tym mniej test wykrywa.
_STOPWORDS = frozenset("""
a i w z o u na do od za po pod nad przy przez dla oraz albo lub ale że się to ten ta
te tego tej tych tym temu jest są był była było będzie ma mają mieć zostać zostanie
został została zostały nie tak jak już tylko także również co czym która który które
którego której ich jego jej ich nim nią nich jako gdy oraz między wobec wraz
""".split())

# Ile znaków końcówki odcinamy, szukając rdzenia. Polska fleksja zmienia nie
# tylko sam koniec: „dachem" wobec „dachu", „zgoda" wobec „zgody".
#
# Rdzeń MUSI zależeć od długości słowa, a nie być stały — oba warianty stałe
# przetestowane na sesji XXIII i oba złe: sześć znaków zgłaszało 11 zdań na 14
# (ostrzeżenie, które zapala się zawsze, nie ostrzega przed niczym), cztery
# znaki przepuszczały samą halucynację, bo „rekr" z „rekreacyjne" trafiało
# w „Centrum Rekrutacji" z zupełnie innego miejsca obrad.
_STEM_TRIM = 3
_STEM_MIN = 4

# Słowa, którymi skrót standardowo streszcza przebieg głosowania — w nagraniu
# nie padają, bo przewodniczący czyta liczby („głosowało 12 radnych, nikt nie
# był przeciw"). Zgłaszanie ich to gwarantowany fałszywy alarm w każdym punkcie
# z uchwałą. Lista ma zostać krótka: każdy wpis to dziura w teście.
_PARAPHRASE_STEMS = ("jednog", "popar", "obejm", "sprzec", "wstrzy")


def unsupported_terms(sentence: str, haystack_flat: str) -> List[str]:
    """
    Słowa treściowe ze zdania, których NIE MA w nagraniu w żadnej odmianie.

    Test deterministyczny i darmowy — i to jest jego cała wartość. Sędzia-LLM
    okazał się niestabilny między przebiegami (ten sam materiał, raz zgłasza
    „cele rekreacyjne", raz przepuszcza), a to samo słowo albo w transkrypcie
    jest, albo go nie ma, i odpowiedź nie zmienia się nigdy.

    Nie rozstrzyga o prawdziwości zdania: model ma prawo do synonimu
    („podwyżka" wobec „wzrośnie"). Rozstrzyga o tym, na co warto spojrzeć.
    """
    from src.services.alert_policy import GMINA_RYBNO_PLACES

    # Nazwy miejscowości są tu ślepą plamką i musi tak zostać: Whisper zapisał
    # Hartowiec jako „Kartowsku", a Koszelewy jako „kosze lewy" — rozdzielone
    # na dwa słowa. Żaden test na obecność słowa ich nie dopasuje, więc
    # zgłaszałby prawdziwe zdania. Nazwę weryfikuje człowiek, klikając znacznik.
    places = tuple(p[:_STEM_MIN].lower() for p in GMINA_RYBNO_PLACES)

    flagged: List[str] = []
    for raw in re.findall(r"\w{5,}", (sentence or "").lower(), flags=re.UNICODE):
        if raw in _STOPWORDS or raw.isdigit():
            continue
        stem = raw[:max(_STEM_MIN, len(raw) - _STEM_TRIM)]
        if stem.startswith(_PARAPHRASE_STEMS) or stem[:_STEM_MIN] in places:
            continue
        if stem in haystack_flat:
            continue
        flagged.append(raw)
    return flagged


async def verify_descriptions(
    summary: CouncilSummaryModel,
    transcript: Transcript,
    report: QualityReport,
) -> tuple:
    """
    Druga warstwa kontroli opisów — **zakreślacz, nie kasownik**.

    **Po co, skoro cytaty są już sprawdzane.** Bramka cytatów pilnuje słów
    w cudzysłowie, a halucynacja siedzi w prozie obok. Na sesji XXIII model
    dwukrotnie, w dwóch niezależnych przebiegach, dopisał działce w Koszelewach
    przeznaczenie („cele rekreacyjne"), o którym w nagraniu nie pada ani słowo —
    przy bezbłędnym raporcie cytatów.

    **Dlaczego zdania są oznaczane, a nie usuwane.** Pierwsza wersja usuwała
    i to był błąd. Sędzia (gpt-4o) na tym samym materiale w kolejnych przebiegach
    wskazywał różne zdania: raz złapał „cele rekreacyjne", raz je przepuścił,
    za to wyciął prawdziwą dotację 60 tys. zł dla OSP w Hartowcu (Whisper zapisał
    tę nazwę jako „Kartowsku"). Narzędzie, które kasuje prawdę i przepuszcza fałsz,
    jest gorsze od jego braku — uczy klikać „publikuj" bez czytania. Skoro
    o publikacji i tak decyduje człowiek, zadaniem tej warstwy jest skierować
    jego wzrok, a nie podejmować decyzję za niego.

    Dwa niezależne sygnały: sędzia (kontekstowy, niestabilny) i test leksykalny
    (`unsupported_terms` — deterministyczny). Wystarczy jeden, żeby zdanie
    trafiło na listę do sprawdzenia i żeby `publishable` było False.

    Zwraca (tokeny wejścia, tokeny wyjścia) sędziego. Modyfikuje `report`
    w miejscu; `summary` pozostaje NIETKNIĘTY.
    """
    if not summary.points:
        return 0, 0

    judge = _build_judge()
    haystack_flat = normalize_quote(transcript.text)
    tokens_in = tokens_out = 0

    for point in summary.points:
        sentences = split_sentences(point.description)
        if not sentences:
            continue
        report.claims_total += len(sentences)

        center = stamp_to_seconds(point.timestamp) or 0.0
        window = transcript.window(center)
        suspect: dict = {}

        # 1. Test leksykalny — słowo spoza CAŁEGO nagrania. Zero kosztu, zero wahań.
        for i, sentence in enumerate(sentences, start=1):
            missing = unsupported_terms(sentence, haystack_flat)
            if missing:
                suspect[i] = "słowa nieobecne w nagraniu: " + ", ".join(missing[:5])

        # 2. Sędzia — łapie to, czego lexem nie widać (parafraza dopisanego celu).
        if window:
            numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, start=1))
            try:
                result = await judge.run(
                    f"FRAGMENT NAGRANIA:\n{window}\n\n"
                    f"ZDANIA DO SPRAWDZENIA:\n{numbered}"
                )
                usage = result.usage()
                tokens_in += getattr(usage, "request_tokens", 0) or 0
                tokens_out += getattr(usage, "response_tokens", 0) or 0
                for v in result.output.verdicts:
                    if not v.supported and 1 <= v.index <= len(sentences):
                        suspect.setdefault(v.index, v.missing or "brak pokrycia we fragmencie")
            except Exception as exc:  # noqa: BLE001
                logger.error("Sędzia opisów nie odpowiedział dla %r: %s", point.title[:60], exc)
        else:
            logger.warning("Brak fragmentu nagrania dla znacznika %s", point.timestamp)

        for i in sorted(suspect):
            report.claims_flagged.append(f"{sentences[i - 1][:160]} — [{suspect[i]}]")
            logger.warning("Zdanie do sprawdzenia: %r (%s)", sentences[i - 1][:100], suspect[i])

    return tokens_in, tokens_out


def _build_agent() -> Agent:
    # Pydantic AI czyta klucz ze środowiska (ten sam wzorzec co summary_generator).
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
    return Agent(
        "openai:gpt-4o",
        output_type=CouncilSummaryModel,
        system_prompt=COUNCIL_SUMMARY_PROMPT,
        output_retries=3,
    )


async def summarize_session(
    transcript: Transcript,
    session_title: Optional[str] = None,
) -> CouncilSummaryResult:
    """
    Transkrypt → zweryfikowany skrót sesji.

    Zwrócony skrót jest już po weryfikacji: cytaty, których nie ma w nagraniu,
    zostały usunięte, a `result.quality.publishable` mówi, czy da się to
    opublikować bez zaglądania do nagrania.
    """
    agent = _build_agent()
    header = f"SESJA: {session_title}\n\n" if session_title else ""
    prompt = (
        f"{header}TRANSKRYPT NAGRANIA (znaczniki [HH:MM:SS] od początku nagrania):\n\n"
        f"{_condense(transcript.stamped_text())}"
    )

    logger.info("Generuję skrót sesji (%d zn. transkryptu)", len(transcript.text))
    result = await agent.run(prompt)
    summary = result.output

    if len(summary.points) > MAX_POINTS:
        summary.points = summary.points[:MAX_POINTS]

    # Kolejność jest istotna: najpierw cytaty, bo to one prostują znacznik czasu
    # punktu — a od znacznika zależy, który fragment nagrania dostanie sędzia opisów.
    quality = verify_against_transcript(summary, transcript)
    judge_in, judge_out = await verify_descriptions(summary, transcript, quality)

    logger.info("Skrót gotowy: %d punktów | %s", len(summary.points), quality.describe())

    usage = result.usage()
    return CouncilSummaryResult(
        summary=summary,
        quality=quality,
        tokens_input=getattr(usage, "request_tokens", 0) or 0,
        tokens_output=getattr(usage, "response_tokens", 0) or 0,
        judge_tokens_input=judge_in,
        judge_tokens_output=judge_out,
    )
