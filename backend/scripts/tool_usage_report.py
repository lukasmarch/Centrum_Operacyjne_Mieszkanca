"""
Raport wywołań narzędzi agentów (etap 6, 2026-08-24)

Powstało z pytania, na które do 22.08 umieliśmy odpowiedzieć wyłącznie
anegdotą: **na czym agenci przestają dawać radę?** 21.08 Przewodnik
powiedział „nie mam prognozy w bazie", mając ją od godziny — i dowiedzieliśmy
się o tym dlatego, że ktoś przypadkiem kliknął podpowiedź.

Trzy warstwy, bo to trzy różne problemy i trzy różne naprawy:

1. UŻYCIE     — czy narzędzie jest w ogóle wołane. Narzędzie z zerem wywołań
                to zły OPIS: model nie wie, że ma po nie sięgnąć. Naprawa
                idzie w `Tool.description`, nie w dane.
2. PUSTKA     — narzędzie zawołane, wynik pusty. Tu mieszkaniec dostaje
                „nie znalazłem" i to jest jedyna warstwa, która mówi o BRAKU
                DANYCH. Naprawa idzie w źródło albo w zakres zapytania.
3. AWARIE     — timeout, złe argumenty, wyjątek. Nasz kod, nie dane.
                `bad_arguments` szczególnie: to nie awaria bazy, tylko dowód,
                że opis parametru wprowadza model w błąd (patrz `days=1`
                na pytanie o jutro, 22.08).

Pustka NIE jest błędem i nie wolno ich mieszać. „Nie ma dziś awarii prądu"
to poprawna odpowiedź na poprawne wywołanie — dopiero pustka POWTARZALNA
na to samo pytanie znaczy, że czegoś nie mamy.

Użycie:
    cd backend && python -m scripts.tool_usage_report [--days 7] [--agent nazwa]

Na produkcji (przez tunel, jak `test_agent_answers`):
    ssh -f -N -L 55432:<IP kontenera db>:5432 root@91.99.142.30
    DATABASE_URL='postgresql://centrum_user:HASLO@localhost:55432/centrum_operacyjne' \\
        python -u -m scripts.tool_usage_report --days 14

Skrypt wyłącznie czyta bazę.

⚠️ CZEGO TU NIE ZOBACZYSZ: pytań, przy których model NIE zawołał żadnego
narzędzia. Wiersz powstaje dopiero przy wywołaniu, więc „Przewodnik nie
sprawdził pogody, choć powinien" nie zostawia tu śladu — zostawia go w
`chat_messages`. To pomiar narzędzi, nie pomiar trafności routingu.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from src.ai import tools as agent_tools  # noqa: E402
from src.config import settings  # noqa: E402


# Poniżej tylu wywołań w oknie „narzędzie ani razu nie zawołane" mówi o tym,
# że nikt nie rozmawiał — a nie o tym, że opis narzędzia jest zły.
MIN_CALLS_FOR_UNUSED = 30


def _pct(part: int, total: int) -> str:
    return f"{100 * part / total:5.1f}%" if total else "    —"


async def report(days: int, agent: str | None) -> int:
    since = datetime.utcnow() - timedelta(days=days)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    where = "created_at >= :since"
    params: dict = {"since": since}
    if agent:
        where += " AND agent_name = :agent"
        params["agent"] = agent

    async with engine.connect() as conn:
        rows = (await conn.execute(text(f"""
            SELECT agent_name, tool_name, state, error, args, duration_ms,
                   question, created_at
            FROM agent_tool_calls
            WHERE {where}
            ORDER BY created_at
        """), params)).mappings().all()
    await engine.dispose()

    label = f"ostatnie {days} dni" + (f" · agent {agent}" if agent else "")
    print("=" * 74)
    print(f"RAPORT NARZĘDZI AGENTÓW — {label}")
    print(f"od {since:%Y-%m-%d %H:%M} UTC")
    print("=" * 74)

    if not rows:
        # Pusta tabela znaczy jedno z dwóch i warto to powiedzieć wprost,
        # zamiast pozwolić czytać ją jako „wszystko działa".
        print("\nBrak wywołań w tym oknie.")
        print("  → albo nikt nie rozmawiał z agentem mającym narzędzia,")
        print("  → albo log nie zbiera (migracja `add_agent_tool_calls`?).")
        return 0

    # ---------------------------------------------------------------- 1. UŻYCIE
    per_tool: dict[str, Counter] = defaultdict(Counter)
    durations: dict[str, list[int]] = defaultdict(list)
    per_agent: Counter = Counter()

    for r in rows:
        per_tool[r["tool_name"]][r["state"]] += 1
        per_tool[r["tool_name"]]["total"] += 1
        durations[r["tool_name"]].append(r["duration_ms"] or 0)
        per_agent[r["agent_name"]] += 1

    print(f"\n1. UŻYCIE — {len(rows)} wywołań, {len(per_tool)} narzędzi\n")
    print(f"   {'narzędzie':<24} {'razem':>6} {'ok':>5} {'pusto':>6} {'błąd':>5} "
          f"{'%pusto':>7} {'med.ms':>7}")
    print("   " + "-" * 65)
    for name, c in sorted(per_tool.items(), key=lambda kv: -kv[1]["total"]):
        ms = sorted(durations[name])
        median = ms[len(ms) // 2] if ms else 0
        print(f"   {name:<24} {c['total']:>6} {c['done']:>5} {c['empty']:>6} "
              f"{c['error']:>5} {_pct(c['empty'], c['total']):>7} {median:>7}")

    # Narzędzie w rejestrze, którego model nigdy nie zawołał, to problem
    # opisu — i jedyny sposób, żeby go zobaczyć, to porównać z rejestrem.
    # ⚠️ Ale tylko przy próbie, która coś znaczy: w oknie z pięcioma rozmowami
    # „nie zawołane" opisuje ruch, nie narzędzia, i wskazałoby na naprawę
    # czegoś, co jest sprawne.
    unused = sorted(set(agent_tools.TOOL_REGISTRY) - set(per_tool))
    if unused and len(rows) >= MIN_CALLS_FOR_UNUSED:
        print(f"\n   ⚠️  ANI RAZU nie zawołane ({len(unused)}): {', '.join(unused)}")
        print("      Sprawdź `Tool.description` — model nie wie, kiedy po nie sięgnąć.")
    elif unused:
        print(f"\n   ({len(unused)} narzędzi bez wywołań, ale próba za mała "
              f"— potrzeba {MIN_CALLS_FOR_UNUSED}+ wywołań, żeby to coś znaczyło)")

    print(f"\n   agenci: " + " · ".join(f"{a} {n}" for a, n in per_agent.most_common()))

    # ---------------------------------------------------------------- 2. PUSTKA
    empties = [r for r in rows if r["state"] == "empty"]
    print(f"\n2. PUSTKA — {len(empties)} wywołań ({_pct(len(empties), len(rows)).strip()})\n")
    if not empties:
        print("   Żadne narzędzie nie wróciło z pustymi rękami.")
    else:
        # Grupujemy po (narzędzie, pytanie): pojedyncza pustka bywa poprawna
        # („nie ma dziś awarii”), powtarzalna oznacza brak w danych.
        grouped: Counter = Counter()
        for r in empties:
            q = (r["question"] or "—").strip()
            grouped[(r["tool_name"], q[:70])] += 1
        for (tool, q), n in grouped.most_common(20):
            mark = "‼️" if n > 1 else "  "
            print(f"   {mark} {n:>2}× {tool:<22} „{q}”")
        if len(grouped) > 20:
            print(f"      … i {len(grouped) - 20} innych")
        if any(n > 1 for n in grouped.values()):
            print("\n   ‼️ = to samo pytanie wróciło puste więcej niż raz "
                  "— sprawdź źródło danych.")
        else:
            print("\n   Każda pustka wystąpiła raz — na razie to mogą być poprawne "
                  "odpowiedzi („nie ma dziś awarii”).")

    # ---------------------------------------------------------------- 3. AWARIE
    errors = [r for r in rows if r["state"] == "error"]
    print(f"\n3. AWARIE — {len(errors)} wywołań ({_pct(len(errors), len(rows)).strip()})\n")
    if not errors:
        print("   Żadne narzędzie nie padło.")
    else:
        by_kind: Counter = Counter(r["error"] or "?" for r in errors)
        for kind, n in by_kind.most_common():
            print(f"   {n:>4}× {kind}")
        print()
        for r in errors[-10:]:
            print(f"   {r['created_at']:%m-%d %H:%M} {r['tool_name']:<22} "
                  f"{r['error']:<14} args={r['args']}")
        hint = {
            "bad_arguments": "opis parametru w schemacie wprowadza model w błąd",
            "timeout": f"zapytanie przekracza limit — sprawdź indeksy",
            "unknown_tool": "agent ma w `tools` nazwę spoza rejestru",
            "exception": "wyjątek w kodzie narzędzia — szukaj w logach backendu",
        }
        print()
        for kind in by_kind:
            if kind in hint:
                print(f"   → {kind}: {hint[kind]}")

    # ------------------------------------------------------------- 4. ARGUMENTY
    # Wywołanie zakończone sukcesem z bezsensownym argumentem wygląda
    # w statystykach dokładnie tak samo jak poprawne. Widać je tylko tutaj.
    print("\n4. ARGUMENTY — najczęstsze wywołania (kontrola, czy model dobiera dobrze)\n")
    combos: Counter = Counter()
    for r in rows:
        args = r["args"] or {}
        sig = ", ".join(f"{k}={v}" for k, v in sorted(args.items()))
        combos[(r["tool_name"], sig or "bez argumentów")] += 1
    for (tool, sig), n in combos.most_common(15):
        print(f"   {n:>4}× {tool:<22} {sig[:44]}")

    print("\n" + "=" * 74)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Raport wywołań narzędzi agentów")
    ap.add_argument("--days", type=int, default=7, help="okno w dniach (domyślnie 7)")
    ap.add_argument("--agent", help="tylko ten agent (np. przewodnik)")
    args = ap.parse_args()
    return asyncio.run(report(args.days, args.agent))


if __name__ == "__main__":
    sys.exit(main())
