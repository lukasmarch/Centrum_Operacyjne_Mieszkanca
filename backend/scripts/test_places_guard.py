"""
Strażnik list miejscowości (audyt E1, etap B) — reguła sprawdzalna kodem sprawdzana przez kod.

Lista miejscowości gminy Rybno stoi w `services/places.py` i tylko tam. Do 13.10.2026
miała pięć pełnych kopii, które rozjeżdżały się po cichu (22 / 20 / 24 nazwy — trzy
różne pojęcia, patrz docstring `places.py`). Ten test:

  1. skanuje `src/` i pada na każdym literale (krotka, lista, zbiór, napis), który
     zawiera CZTERY LUB WIĘCEJ różnych nazw z gminy — poza `places.py`. Docstringi
     pomijamy. Wyjątek: dopisek `# places-ok: <powód>` w linii literału albo linię wyżej
     (np. lista stemów tras w `traffic_service`, to inne pojęcie niż lista wsi);
  2. sprawdza, że trzy listy nie dryfują: SOLECTWA ⊂ HARMONOGRAM ∪ MIEJSCOWOSCI,
     HARMONOGRAM == lista z frontu (`frontend/types.ts: AVAILABLE_LOCATIONS`),
     mianowniki w prompcie == lista w `places.py`.

Użycie: cd backend && python -m scripts.test_places_guard
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services import places  # noqa: E402

SRC = Path(__file__).resolve().parent.parent / "src"
FRONT_TYPES = Path(__file__).resolve().parents[2] / "frontend" / "types.ts"
THRESHOLD = 4

# Nazwy rozpoznawcze: bez „Rybno" i „Nowa Wieś" (padają wszędzie jako zwykłe słowa).
DISTINCT = {n for n in set(places.GMINA_RYBNO_PLACES) | set(places.SOLECTWA) | set(places.HARMONOGRAM)
            if n not in ("Rybno", "Rybno R1", "Rybno R2", "Nowa Wieś", "Domki letniskowe")}


def _names_in(text: str) -> set[str]:
    return {n for n in DISTINCT if re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", text)}


def _docstring_nodes(tree: ast.AST) -> set[int]:
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def scan() -> list[str]:
    problems: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == SRC / "services" / "places.py":
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        tree = ast.parse(text)
        skip = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                names = set()
                for elt in node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        names |= _names_in(elt.value) if elt.value in DISTINCT else set()
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
                # Napis: liczą się nazwy w oknie TRZECH sąsiednich linii — lista w prompcie to
                # kilka linii, a przykłady rozsiane po długim prompcie („droga Tuczki–Koszelewy")
                # nie są kopią listy.
                parts = node.value.split("\n")
                names = set()
                for i in range(max(1, len(parts) - 2)):
                    here = _names_in("\n".join(parts[i:i + 3]))
                    if len(here) > len(names):
                        names = here
            else:
                continue
            if len(names) < THRESHOLD:
                continue
            first = node.lineno
            window = "\n".join(lines[max(0, first - 3): first])
            if "places-ok:" in window or "places-ok:" in lines[first - 1]:
                continue
            problems.append(f"{path.relative_to(SRC.parent)}:{first}  {len(names)} nazw ({', '.join(sorted(names)[:4])}…)")
    return problems


def front_locations() -> list[str]:
    text = FRONT_TYPES.read_text(encoding="utf-8")
    block = re.search(r"AVAILABLE_LOCATIONS\s*=\s*\[(.*?)\]\s*as const", text, re.DOTALL).group(1)
    return re.findall(r"'([^']+)'", block)


def main() -> int:
    failures: list[str] = []

    for p in scan():
        failures.append(f"KOPIA LISTY POZA places.py: {p}  → użyj services/places.py albo dopisz `# places-ok: powód`")

    if set(places.SOLECTWA) - set(places.HARMONOGRAM) - set(places.GMINA_RYBNO_PLACES):
        failures.append("SOLECTWA zawiera nazwę nieznaną ani w HARMONOGRAM, ani w MIEJSCOWOSCI")
    if front_locations() != list(places.HARMONOGRAM):
        failures.append("frontend/types.ts: AVAILABLE_LOCATIONS != places.HARMONOGRAM (kolejność też się liczy — to kolejność UI)")
    from src.ai.prompts import DAILY_SUMMARY_PROMPT
    if ", ".join(places.PROMPT_NOMINATIVES) + "." not in DAILY_SUMMARY_PROMPT:
        failures.append("prompt briefingu nie niesie listy mianowników z places.py")
    from src.auth.schemas import AVAILABLE_LOCATIONS
    if list(AVAILABLE_LOCATIONS) != list(places.HARMONOGRAM):
        failures.append("auth.schemas.AVAILABLE_LOCATIONS != places.HARMONOGRAM")
    counts = (len(places.GMINA_RYBNO_PLACES), len(places.SOLECTWA), len(places.HARMONOGRAM))
    if counts != (22, 20, 24):
        failures.append(f"liczby list {counts} != (22, 20, 24) — zmiana celowa? zaktualizuj CLAUDE.md i ten test")

    print(f"miejscowości/sołectwa/harmonogram: {counts}")
    for f in failures:
        print("  ✗", f)
    if not failures:
        print("OK — jedna lista miejscowości, front i prompt zgodne")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
