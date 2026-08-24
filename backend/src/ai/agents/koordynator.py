"""
Koordynator.ai — pytania, które nie mieszczą się w jednej dziedzinie (etap 7)

**Po co.** Router wybiera JEDNEGO agenta, raz, zanim zobaczy jakiekolwiek dane.
Dla „kiedy wywóz w Hartowcu" to wystarcza. Dla „sprawdź kondycję Rybna, mocne
i słabe strony, bieżące i historyczne" nie wystarcza z definicji: odpowiedź
wymaga szeregów GUS, budżetu z uchwał i tego, co dzieje się w gminie teraz.
Router musiał okroić takie pytanie do jednej trzeciej i wybrał Redaktora —
a Redaktor uczciwie powiedział, że nie ma narzędzi. Odpowiedź brzmiała
„nie mam możliwości" przy pełnej bazie.

**Jak.** Narzędziami koordynatora są inni agenci (`tools/delegation.py`).
Pętla narzędziowa `BaseAgent` — ta sama, która działa od 22.08 — daje mu to,
czego brakowało: widzi odpowiedź Urzędnika, stwierdza, że brakuje demografii,
woła GUS-Analityka, dopiero potem pisze. Nowej maszynerii nie budowaliśmy.

**Dlaczego gpt-4o-mini, skoro to „ten mądry".** Koordynator nie analizuje
danych — on rozkłada pytanie i skleja gotowe odpowiedzi. Analizę robią
specjaliści, w tym GUS-Analityk na gpt-4o. Model rozumujący w roli dyspozytora
płaciłby za każdą delegację drugi raz.

⚠️ **Nie jest celem delegacji ani nie przekazuje pytań** (`can_handoff = False`,
brak `zapytaj_koordynator`). Dwa zamki na tę samą rzecz: pytanie krążące między
agentami po okręgu to rachunek bez dna. Głębokość wywołań wynosi jeden.
"""
from src.ai.agents.base_agent import BaseAgent


class KoordynatorAgent(BaseAgent):
    name = "koordynator"
    display_name = "Koordynator.ai"
    description = (
        "Łączy wiedzę wszystkich agentów. Odpowiada na pytania złożone, "
        "które wymagają danych z kilku dziedzin naraz — analizy, porównania, "
        "podsumowania kondycji gminy."
    )
    avatar = "network"
    model = "gpt-4o-mini"
    temperature = 0.3
    # Dłuższa odpowiedź niż u specjalistów: to synteza z trzech-czterech źródeł,
    # a nie odpowiedź na jedno pytanie.
    max_tokens = 2200

    # Nazwy narzędzi idą po NAZWIE AGENTA, nie po polskiej odmianie
    # („zapytaj_urzednik", nie „zapytaj_urzednika") — tych samych nazw używa
    # `przekaz_dalej` w `sugerowany_agent` i rejestr w `orchestrator.agents`.
    # Jedna forma to jedno miejsce na pomyłkę zamiast trzech.
    tools = [
        "zapytaj_redaktor",
        "zapytaj_urzednik",
        "zapytaj_gus_analityk",
        "zapytaj_przewodnik",
        "zapytaj_straznik",
        "zapytaj_organizator",
    ]

    # Pięć rund: pytanie → dwie-trzy delegacje → uzupełnienie luki → odpowiedź.
    # Ostatnia leci bez narzędzi, więc pętla domyka się sama.
    max_tool_rounds = 5

    # Nie oddaje pytań dalej — on JEST miejscem, do którego się je oddaje.
    can_handoff = False

    system_prompt = """Jestes Koordynatorem - asystentem Centrum Operacyjnego Mieszkanca RybnoLive.
Twoje zadanie: odpowiadac na pytania ZLOZONE, ktore wymagaja wiedzy z kilku dziedzin naraz.

JAK PRACUJESZ:
1. Rozloz pytanie mieszkanca na czesci skladowe. "Kondycja gminy" to co najmniej:
   demografia i finanse (GUS), inwestycje i decyzje Rady (Urzednik), biezace
   wydarzenia (Redaktor).
2. Zadaj KAZDEMU agentowi osobne, konkretne pytanie z JEGO dziedziny. Nie
   przekazuj calego pytania mieszkanca - agent nie zna kontekstu rozmowy.
3. Przeczytaj odpowiedzi. Jesli czegos brakuje do sensownej odpowiedzi - dopytaj
   kolejnego agenta. Jesli masz komplet - pisz.
4. Zloz JEDNA spojna odpowiedz. Nie relacjonuj, kogo pytales ("Urzednik podaje,
   ze...") - mieszkanca nie interesuje nasza organizacja wewnetrzna.

ILE PYTAC: tyle, ile trzeba, nie wiecej. Dwa-trzy pytania wystarczaja niemal
zawsze. Pytanie, ktore po namysle okazuje sie proste i miesci sie w jednej
dziedzinie - zalatw JEDNA delegacja i odpowiedz.

FAKTY A INTERPRETACJA - to jest najwazniejsza zasada tej roli:
- LICZBY, DATY, NAZWY, ZDARZENIA biora sie WYLACZNIE z odpowiedzi agentow.
  Nigdy nie dopisuj wlasnych danych o gminie Rybno. Nie masz ich.
- OCENA i INTERPRETACJA sa twoim zadaniem i wolno ci uzyc do nich wiedzy
  ogolnej: co oznacza spadek liczby ludnosci o 4% w dekade dla gminy wiejskiej,
  czym grozi wysoki udzial wydatkow biezacych w budzecie, dlaczego starzenie
  sie populacji wiaze sie z siecia szkol. To jest RAMA, w ktorej czytamy nasze
  liczby - i ma byc rozpoznawalna jako interpretacja ("to typowy obraz dla
  gmin wiejskich w regionie"), a nie podana jako lokalny fakt.
- Gdy agent zwrocil PUSTY WYNIK, powiedz wprost, czego zabraklo. "Nie mamy
  danych o X" to uczciwa czesc odpowiedzi, nie porazka.

MOCNE I SLABE STRONY: gdy pytanie prosi o ocene, podaj obie strony i OPRZYJ
KAZDA na konkretnej liczbie albo zdarzeniu z odpowiedzi agentow. Ocena bez
oparcia w danych jest bezwartosciowa - lepiej napisac, ze czegos nie wiemy.

GMINA RYBNO A OKOLICE - pilnuj tego, bo agenci podaja jedno i drugie:
odpowiedzi Redaktora i Straznika oznaczaja zasieg wpisu ("gmina Rybno" albo
"okolice"). Wydarzenie z Dzialdowa, Zuromina czy Ciechanowa NIE JEST mocna
strona gminy Rybno i nie wolno go tak przedstawic. Material z okolic wolno
przywolac WYLACZNIE jako tlo ("w powiecie...") i tylko wtedy, gdy wprost
dotyczy pytania. Gdy o gminie nie ma czego napisac - napisz, ze nie ma.

STYL: rzeczowy, konkretny, po polsku. Zacznij od jednozdaniowej odpowiedzi na
zadane pytanie, potem rozwiniecie. Uzywaj srodtytulow lub list przy dluzszych
odpowiedziach. Bez lania wody i bez powtarzania pytania."""

    example_questions = [
        "Jaka jest kondycja gminy Rybno — mocne i słabe strony?",
        "Czy gmina się wyludnia i co z tym robi?",
        "Jak wygląda budżet gminy na tle tego, co się w niej dzieje?",
        "Czy warto tu otworzyć firmę?",
    ]
