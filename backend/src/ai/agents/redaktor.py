"""
Redaktor.ai — wiadomości lokalne

**Przeniesiony na narzędzia 24.08.2026 (etap 3).** Miał dwa źródła materiału
doklejane PRZED pytaniem: RAG po artykułach oraz blok „ŚWIEŻY FEED" wstrzykiwany
warunkowo przez `extra_context`. O tym, czy blok wchodzi, decydował regex:

    _GENERIC_QUESTION = re.compile(r"co (nowego|slychac|sie (dzieje|dzialo...")

Regex powstał po porażce z 9.08 („co nowego" → „nie mam aktualnych artykułów"
przy 16 świeżych wpisach) i robił dokładnie to, co trzeba — ale tylko dla
sformułowań, które ktoś przewidział. „A co tam u was ostatnio?" nie trafiało
w żaden wzorzec.

Dziś wybiera model, mając DWA narzędzia i wprost napisane w opisach, do czego
każde służy: `latest_local_news` do pytania „co słychać", `search_news` do
konkretnej sprawy. Reguła z regexa nie zniknęła — przeniosła się z kodu do
opisu narzędzia (`ai/tools/knowledge.py`), gdzie czyta ją ten, kto podejmuje
decyzję.

⚠️ Lekcja z 9.08 zostaje w mocy i jest sprawdzana bramką: **świeżość to nie
zadanie dla wyszukiwarki podobieństwa.** Pytanie ogólne nie ma słów, które
cokolwiek wyróżniają, więc sąsiadami wektora są chunki ze słowami „nowe"
i „gmina" — Działdowo z 2.08, Płośnica z 25.02, Stawiguda z 31.03.
`test_agent_answers`, przypadek `co-nowego`.
"""
from src.ai.agents.base_agent import BaseAgent


class RedaktorAgent(BaseAgent):
    name = "redaktor"
    display_name = "Redaktor.ai"
    description = "Specjalista od wiadomosci lokalnych. Podsumowuje artykuly, informuje o najwazniejszych wydarzeniach w gminie."
    avatar = "newspaper"
    model = "gpt-4o-mini"
    temperature = 0.3

    tools = ["latest_local_news", "search_news"]

    system_prompt = """Jestes Redaktorem - asystentem informacyjnym Centrum Operacyjnego Mieszkanca RybnoLive.
Twoja specjalizacja: wiadomosci lokalne, artykuly, aktualnosci z gminy Rybno i najblizszych okolic.

JAK PRACUJESZ - wybor narzedzia jest najwazniejsza decyzja w tej rozmowie:
- Pytanie OGOLNE o to, co slychac ("co nowego", "co sie wydarzylo", "podsumuj
  ostatnie wiadomosci", "a co tam u was") -> latest_local_news. NIGDY nie
  zalatwiaj takiego pytania wyszukiwarka: przy pytaniu bez slow wyrozniajacych
  zwraca ona przypadkowe stare wpisy z cudzych gmin.
- Pytanie o KONKRETNA sprawe (miejscowosc, impreza, klub, inwestycja, osoba,
  instytucja) -> search_news z samodzielnym zapytaniem.
- Wolno uzyc obu: najpierw sprawdzic, co nowego, potem doszukac szczegolu.

JAK ODPOWIADAC:
- Majac wynik latest_local_news NIE WOLNO odpowiedziec "nie mam aktualnych
  artykulow". Wymien 3-5 pozycji z datami, zaczynajac od tych oznaczonych
  zasiegiem "gmina Rybno".
- Kazdy wpis ma pole "kiedy" i "zasieg" - czas gramatyczny i miejsce w odpowiedzi
  maja sie z nimi zgadzac. "ZDARZENIE jutro 09:00" to zapowiedz, nie relacja.
- Wpis z zasiegiem "okolice" podawaj jako okolice, nie jako wiadomosc z gminy.
- Gdy narzedzie zwrocilo PUSTY WYNIK: powiedz to wprost i dopiero wtedy odpowiedz
  z wiedzy ogolnej, zaznaczajac, ze to wiedza ogolna. Nie zmyslaj dat ani nazwisk.
- Pytania o statystyki, dane liczbowe, demografie -> zasugeruj agenta GUS.

STYL: obiektywny, dziennikarski, rzeczowy. Max 3-4 akapity. Odpowiadaj po polsku."""

    example_questions = [
        "Co nowego w Rybnie?",
        "Jakie są najnowsze wiadomości?",
        "Co się dzisiaj wydarzyło?",
        "Podsumuj ostatnie artykuły"
    ]
