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
# Karta dopisana ręcznie w jednym agencie ominęłaby pozostałych, dlatego
# każdy z nich musi sięgać po wspólny helper.
import pathlib  # noqa: E402

agents_dir = pathlib.Path(__file__).resolve().parents[1] / "src" / "ai" / "agents"
for fname in ("gus_analityk.py", "straznik.py", "przewodnik.py", "organizator.py"):
    src = (agents_dir / fname).read_text(encoding="utf-8")
    check("base_context_messages" in src, f"{fname} używa wspólnego kontekstu")

print(f"\n{'=' * 50}")
if failures:
    print(f"NIEPOWODZENIA ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("Wszystko przeszło.")
