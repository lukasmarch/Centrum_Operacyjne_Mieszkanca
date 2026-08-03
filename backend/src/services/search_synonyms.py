"""
Mowa potoczna → język urzędowy w zapytaniach do RAG (2026-08-03).

Mieszkaniec pyta „czy dostanę dofinansowanie na usunięcie eternitu z dachu".
BIP ma „Program usuwania wyrobów zawierających azbest z terenu Gminy Rybno".
`text-embedding-3-small` tych dwóch rzeczy nie łączy: pomiar na produkcji dał
0,674 dla zapytania z „azbest" i ani jednego trafienia w ten dokument dla
zapytania z „eternit" — zamiast tego wyszły artykuły o dotacjach na zabytki.

Dopisujemy termin urzędowy do zapytania, zamiast podmieniać słowo: „eternit"
też bywa trafny (pada w treści niektórych ogłoszeń), a zapytanie idzie i tak
do wyszukiwania hybrydowego, gdzie oba warianty pracują — semantyczny łapie
sens, BM25 łapie dosłowne wystąpienie.

Dlaczego to kod, a nie zdanie w promptcie: prompt jest prośbą, a retrieval
dzieje się PRZED modelem — model nie ma jak poprawić zapytania, którego nie
widział. Ta sama lekcja co przy bramce miejsca w `alert_policy`.

Słownik ma zostać krótki i pokrywać rzeczy, które ludzie naprawdę mówią inaczej
niż urząd. To nie jest miejsce na tezaurus języka polskiego — każdy dopisany
termin rozmywa zapytanie i psuje trafność pozostałych pytań.
"""
import re
import unicodedata
from typing import Optional

# potoczne (wzorzec rdzenia) → terminy urzędowe dopisywane do zapytania
_SYNONYMS: tuple[tuple[str, str], ...] = (
    (r"eternit\w*", "azbest wyroby zawierające azbest"),
    (r"smiec\w*|smietnik\w*", "odpady komunalne"),
    (r"gruz\w*|wielkogabaryt\w*", "odpady budowlane odpady wielkogabarytowe"),
    (r"szambo\w*|szamb\w*", "nieczystości ciekłe zbiornik bezodpływowy"),
    (r"kopciuch\w*|piec\w+wegl\w*", "wymiana źródła ciepła niska emisja"),
    (r"solar\w*|fotowoltaik\w*|panel\w*\s+sloneczn\w*", "odnawialne źródła energii"),
    (r"psy\w*\s+podatek|podatek\s+od\s+ps\w+", "opłata od posiadania psów"),
    (r"wycink\w*\s+drzew\w*|wycia[cć]\s+drzew\w*", "zezwolenie na usunięcie drzew"),
    (r"dowod\s+osobist\w*", "dowód osobisty sprawy meldunkowe"),
    (r"500\s*\+|800\s*\+", "świadczenie wychowawcze"),
    (r"becikow\w*", "jednorazowa zapomoga z tytułu urodzenia dziecka"),
    # Kolejność słów bywa dowolna („woda jest brudna", „brudna woda w kranie")
    (r"wod\w*.{0,12}(brudn|smierdz|metn)\w*|(brudn|smierdz|metn)\w*.{0,12}wod\w*",
     "ocena jakości wody wodociąg"),
)

_COMPILED = tuple((re.compile(pattern), expansion) for pattern, expansion in _SYNONYMS)


def _flat(text: str) -> str:
    """Bez ogonków i wielkości liter — jak w `alert_policy`, z ręczną podmianą
    „ł", która jako jedyna polska litera nie rozkłada się w NFKD."""
    text = (text or "").lower().replace("ł", "l")
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def expand_query(query: Optional[str]) -> str:
    """Zapytanie wzbogacone o terminy urzędowe. Bez trafienia zwraca oryginał."""
    if not query:
        return query or ""

    flat = _flat(query)
    additions = [
        expansion
        for pattern, expansion in _COMPILED
        if pattern.search(flat) and _flat(expansion) not in flat
    ]
    if not additions:
        return query
    return f"{query} {' '.join(additions)}"
