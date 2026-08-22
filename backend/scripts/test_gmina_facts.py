"""
Sprawdza kartę gminy — `python -m scripts.test_gmina_facts`.

Karta idzie do modelu przy KAŻDYM zapytaniu, więc jej rozdęcie jest kosztem
stałym i zaczyna konkurować o uwagę modelu z materiałem źródłowym. Ten test
pilnuje limitu i tego, że karta trafia do wszystkich agentów — także tych
czterech, którzy budują `messages` po swojemu.
"""
import sys

from src.ai.agents.base_agent import base_context_messages
from src.services.gmina_facts import MAX_FACTS_BYTES, SOLECTWA, gmina_facts

failures: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}{f' — {detail}' if detail else ''}")
        failures.append(label)


print("\n== Rozmiar ==")
facts = gmina_facts()
size = len(facts.encode("utf-8"))
check(
    size <= MAX_FACTS_BYTES,
    f"karta mieści się w limicie ({size} B / {MAX_FACTS_BYTES} B)",
    "przenieś fakt do warstwy RAG zamiast podnosić limit",
)

print("\n== Treść ==")
# Odpowiedź na pytanie, od którego cała ta praca się zaczęła (3.08.2026).
check(str(len(SOLECTWA)) in facts, f"liczba sołectw ({len(SOLECTWA)}) jest w karcie")
check(len(SOLECTWA) == len(set(SOLECTWA)), "brak duplikatów na liście sołectw")
for name in ("Tomasz Węgrzynowski", "Lubawska 15", "działdowski", "Rybno"):
    check(name in facts, f"karta zawiera: {name}")
check("KONTEKST" in facts, "karta ustala pierwszeństwo świeższego materiału")

print("\n== Sołectwa a miejscowości ==")
# alert_policy opisuje miejscowości, w których może wypaść awaria — to celowo
# szersza lista. Zrównanie ich oznaczałoby, że ktoś podstawił jedną pod drugą.
from src.services.alert_policy import GMINA_RYBNO_PLACES  # noqa: E402

check(
    set(SOLECTWA) != set(GMINA_RYBNO_PLACES),
    "lista sołectw NIE jest kopią listy miejscowości z alert_policy",
    "sołectwo to jednostka pomocnicza gminy, nie każda miejscowość nią jest",
)

print("\n== Dostarczenie do agentów ==")
msgs = base_context_messages()
check(all(m["role"] == "system" for m in msgs), "wszystkie wiadomości mają rolę system")
check(any("sołect" in m["content"] for m in msgs), "karta jest w kontekście bazowym")
check(any("AKTUALNA DATA" in m["content"] for m in msgs), "data nadal jest w kontekście")

print("\n== Agenci z własnym respond() ==")
# Karta dopisana ręcznie w jednym agencie ominęłaby pozostałych, dlatego każdy,
# kto składa `messages` po swojemu, musi sięgnąć po wspólny helper.
#
# Lista agentów jest WYKRYWANA, nie wpisana: sprawdzamy, którzy nadpisują
# `respond()`. Wpisana ręcznie zaczęła kłamać 22.08, gdy Przewodnik przeszedł
# na narzędzia i przestał mieć własne `respond()` — test wołał o brak czegoś,
# co przestało być potrzebne.
import inspect  # noqa: E402
import pathlib  # noqa: E402

from src.ai.agents.base_agent import BaseAgent  # noqa: E402
from src.ai.agents.gus_analityk import GUSAnalitykAgent  # noqa: E402
from src.ai.agents.organizator import OrganizatorAgent  # noqa: E402
from src.ai.agents.przewodnik import PrzewodnikAgent  # noqa: E402
from src.ai.agents.redaktor import RedaktorAgent  # noqa: E402
from src.ai.agents.straznik import StraznikAgent  # noqa: E402
from src.ai.agents.urzednik import UrzednikAgent  # noqa: E402

ALL_AGENTS = (
    GUSAnalitykAgent, OrganizatorAgent, PrzewodnikAgent,
    RedaktorAgent, StraznikAgent, UrzednikAgent,
)

for cls in ALL_AGENTS:
    fname = pathlib.Path(inspect.getfile(cls)).name
    if cls.respond is BaseAgent.respond:
        # Kontekst bazowy dostaje z `BaseAgent` — obiema ścieżkami, RAG-ową
        # i narzędziową.
        check(True, f"{fname} dziedziczy respond() → kartę dostaje automatycznie")
        continue
    src = pathlib.Path(inspect.getfile(cls)).read_text(encoding="utf-8")
    check("base_context_messages" in src,
          f"{fname} ma własne respond() i używa wspólnego kontekstu")

print(f"\n{'=' * 50}")
if failures:
    print(f"NIEPOWODZENIA ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("Wszystko przeszło.")
