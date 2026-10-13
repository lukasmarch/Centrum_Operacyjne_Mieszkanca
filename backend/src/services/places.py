"""
Miejscowości gminy Rybno — JEDYNE miejsce, w którym stoją ich nazwy (audyt E1, etap B).

Do 13.10.2026 listy były rozsiane po pięciu plikach (`alert_policy`, `gmina_facts`,
`auth/schemas`, `ai/tools/daily`, `ai/prompts`) i rozjeżdżały się: jedne miały 22 nazwy,
inne 20 albo 24. To NIE jest błąd, tylko TRZY RÓŻNE POJĘCIA — dlatego są trzy listy
i nie wolno podstawiać jednej pod drugą:

  MIEJSCOWOSCI (22)  — nazwy, które padają w tekście wiadomości (z odmianą, wzorce regex);
                       zawiera Groszki i Wery, które nie są sołectwami, oraz „Gralewo".
  SOLECTWA (20)      — jednostki pomocnicze gminy wg BIP (zawiera „Gralewo Stacja",
                       nie ma Groszków ani Wer).
  HARMONOGRAM (24)   — pozycje harmonogramu odpadów i lista wyboru w profilu: dwa rejony
                       Rybna (R1/R2), „Domki letniskowe", „Gralewo Stacja".

Nowa miejscowość = wpis TUTAJ. Strażnik `scripts.test_places_guard` czerwieni każdy
plik w `src/`, który wypisuje cztery lub więcej nazw poza tym modułem (wyjątek:
dopisek `# places-ok: powód`). Zmiana list musi zachować golden master
(`python -m scripts.locality_gold --check`).
"""
from __future__ import annotations

import re

# Miejscowości gminy Rybno, które padają w TEKŚCIE (bez „Domki letniskowe" i sufiksów
# stref śmieciowych R1/R2 — to nazwy z harmonogramu odbioru odpadów, w prasie nie padają).
#
# Formy odmienione wypisane wprost, zamiast doklejać dowolną końcówkę do rdzenia.
# Automat brzmi kusząco, ale na tej liście są nazwy, które w dopełniaczu zlewają
# się ze słowami pospolitymi: „Grądy" z gradem, „Wery" z wersją, „Rumian"
# z rumiankiem, „Prusy" z pruskim. Alert ma budzić ludzi w nocy — wolimy przegapić
# egzotyczną odmianę niż wysłać powiadomienie z powodu opadów gradu.
# Wzorce działają na tekście bez ogonków (`_flat`).
MIEJSCOWOSCI_PATTERNS: tuple[tuple[str, str], ...] = (
    ("Rybno", r"rybn(o|a|ie|em)"),
    # „debienie" to BŁĘDNY mianownik, który model tworzy z „w Dębieniu" (znany
    # błąd, opisany w prompcie). Wzorzec ma łapać formy, które realnie padają
    # w tekście i w polu `event_places` — także te utworzone przez model.
    ("Dębień", r"debien(ia|iu|ie)?"),
    ("Grabacz", r"grabacz(a|u|em)?"),
    ("Gralewo", r"gralew(o|a|ie|em)"),
    ("Gronowo", r"gronow(o|a|ie|em)"),
    ("Groszki", r"groszk(i|ach|ow|om|ami)"),
    ("Grądy", r"grad(y|ach|om|ami)"),
    ("Hartowiec", r"hartow(iec|cu|ca|cem)"),
    ("Jeglia", r"jegli(a|ii|i|e)"),
    ("Kopaniarze", r"kopaniarz(e|ach|y|om|ami)"),
    ("Koszelewki", r"koszelewk(i|ach|om|ami)"),
    ("Koszelewy", r"koszelew(y|ach|om|ami)"),
    ("Naguszewo", r"naguszew(o|a|ie|em)"),
    ("Nowa Wieś", r"now(a|ej)\s+w(ies|si)"),
    ("Prusy", r"prus(y|ach|om|ami)"),
    ("Rapaty", r"rapat(y|ach|om|ami)"),
    ("Rumian", r"rumian(ie|a|em|y)?"),
    ("Szczupliny", r"szczuplin(y|ach|om|ami)"),
    ("Truszczyny", r"truszczyn(y|ach|om|ami)"),
    ("Tuczki", r"tuczk(i|ach|om|ami)"),
    ("Wery", r"wer(y|ach|om|ami)"),
    ("Żabiny", r"zabin(y|ach|om|ami)"),
)

GMINA_RYBNO_PLACES: tuple[str, ...] = tuple(place for place, _ in MIEJSCOWOSCI_PATTERNS)

PLACE_RE = tuple(
    (place, re.compile(r"\b" + pattern + r"\b")) for place, pattern in MIEJSCOWOSCI_PATTERNS
)

# Jednostki pomocnicze gminy — BIP /147/, stan na 3.08.2026.
SOLECTWA: tuple[str, ...] = (
    "Dębień", "Grabacz", "Grądy", "Gralewo Stacja", "Gronowo",
    "Hartowiec", "Jeglia", "Kopaniarze", "Koszelewki", "Koszelewy",
    "Naguszewo", "Nowa Wieś", "Prusy", "Rapaty", "Rumian",
    "Rybno", "Szczupliny", "Truszczyny", "Tuczki", "Żabiny",
)

# Kanoniczne nazwy z `waste_schedule` — to samo, co lista wyboru w profilu (kolejność = UI).
# Front trzyma kopię w `frontend/types.ts`; zgodność pilnuje `test_places_guard`.
HARMONOGRAM: tuple[str, ...] = (
    "Rybno R1", "Rybno R2", "Dębień", "Domki letniskowe", "Grabacz", "Gralewo Stacja",
    "Gronowo", "Groszki", "Grądy", "Hartowiec", "Jeglia", "Kopaniarze", "Koszelewki",
    "Koszelewy", "Naguszewo", "Nowa Wieś", "Prusy", "Rapaty", "Rumian", "Szczupliny",
    "Truszczyny", "Tuczki", "Wery", "Żabiny",
)

# Mianowniki podawane modelowi jako zamknięta lista pisowni (prompt briefingu):
# miejscowości z tekstu, „Gralewo" pod nazwą urzędową „Gralewo Stacja".
PROMPT_NOMINATIVES: tuple[str, ...] = tuple(sorted(
    "Gralewo Stacja" if place == "Gralewo" else place for place in GMINA_RYBNO_PLACES
))


def places_text(names: tuple = SOLECTWA) -> str:
    """Lista nazw do wstawienia w tekst (prompt, karta gminy)."""
    return ", ".join(names)
