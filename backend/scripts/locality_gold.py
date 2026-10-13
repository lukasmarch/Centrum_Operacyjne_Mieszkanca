"""
Golden master funkcji lokalności (audyt E1, etap A).

Po co: ocena „czy to nasze" mieszka w kilku funkcjach (`is_local_article`,
`article_scope`, `locality_factor`, `places_in`, `gmina_subject`, `is_foreign_region`)
i regule briefingu (`_mark_local_articles`). Każda zmiana listy miejscowości albo
progu była dotąd mierzona ręcznie na kilku wpisach. Ten moduł zapisuje, CO KAŻDA
funkcja odpowiada na całym korpusie, więc refaktor (etap B: jedna lista
miejscowości) da się zaliczyć warunkiem „0 różnic".

Zapis zawiera WYŁĄCZNIE id artykułu i wyniki funkcji — bez tytułów i treści
(cudze teksty i dane osobowe nie wchodzą do repozytorium).

Użycie (z katalogu backend/, lokalna baza):
    python -m scripts.locality_gold --record     # zapisz wzorzec
    python -m scripts.locality_gold --check      # porównaj z wzorcem (kod wyjścia 1 przy różnicach)
    python -m scripts.locality_gold --check --show 20

⚠️ Wzorzec jest ZDJĘCIEM bieżącego zachowania, nie dowodem, że jest poprawne.
O poprawności mówi `test_locality_gold` (60 przykładów oznaczonych ręcznie).
Zmiana zachowania celowa → `--record` w tym samym commicie, z opisem różnic.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.alert_policy import gmina_subject, is_foreign_region, places_in  # noqa: E402
from src.services.feed_policy import (  # noqa: E402
    MIN_ARTICLE_LOCALITY,
    article_scope,
    is_local_article,
    locality_factor,
)

GOLD_PATH = Path(__file__).resolve().parent / "golden" / "locality_gold.json"

FIELDS = (
    "places",         # places_in(title, content)
    "foreign",        # is_foreign_region
    "subject",        # gmina_subject
    "local_article",  # is_local_article(źródło, tytuł, treść)
    "scope",          # article_scope
    "factor",         # locality_factor z zapisaną oceną
    "factor_nols",    # locality_factor bez oceny (ścieżka sprzed 21.08 / czekające na kategoryzację)
    "briefing_local", # reguła _mark_local_articles
)


def evaluate(source: Optional[str], title: Optional[str], content: Optional[str],
             locality: Optional[int]) -> list[Any]:
    """Wszystkie odpowiedzi funkcji lokalności dla jednego wpisu (kolejność = FIELDS)."""
    briefing_local = (
        locality >= MIN_ARTICLE_LOCALITY
        if locality is not None
        else is_local_article(source, title, content)
    )
    return [
        list(places_in(title, content)),
        is_foreign_region(title, content),
        gmina_subject(title, content),
        is_local_article(source, title, content),
        article_scope(source, title, content),
        locality_factor(locality, source, title, content),
        locality_factor(None, source, title, content),
        briefing_local,
    ]


async def _fetch() -> list[tuple]:
    import asyncpg

    url = os.environ.get("DATABASE_URL")
    if not url:
        env = Path(__file__).resolve().parent.parent / ".env"
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    if not url:
        raise SystemExit("Brak DATABASE_URL (ani w środowisku, ani w backend/.env)")
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        rows = await conn.fetch(
            "SELECT a.id, s.name, a.title, a.content, a.locality "
            "FROM articles a LEFT JOIN sources s ON s.id = a.source_id ORDER BY a.id"
        )
    finally:
        await conn.close()
    return [tuple(r) for r in rows]


def snapshot(rows: list[tuple]) -> dict[str, list[Any]]:
    return {str(i): evaluate(src, title, content, loc) for i, src, title, content, loc in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--show", type=int, default=10, help="ile różnic wypisać")
    args = parser.parse_args()

    rows = asyncio.run(_fetch())
    snap = snapshot(rows)

    if args.record:
        GOLD_PATH.parent.mkdir(exist_ok=True)
        GOLD_PATH.write_text(
            json.dumps({"fields": FIELDS, "n": len(snap), "rows": snap},
                       ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"Zapisano wzorzec: {len(snap)} wpisów → {GOLD_PATH.relative_to(GOLD_PATH.parents[2])}")
        return 0

    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    if tuple(gold["fields"]) != FIELDS:
        print("Wzorzec ma inne pola niż kod — nagraj od nowa (--record).")
        return 1
    ref = gold["rows"]
    by_id = {str(r[0]): r for r in rows}
    diffs: list[tuple[str, int, Any, Any]] = []
    for key, old in ref.items():
        if key not in snap:
            continue  # wpis zniknął z bazy — nie jest różnicą zachowania
        for idx, (a, b) in enumerate(zip(old, snap[key])):
            if a != b:
                diffs.append((key, idx, a, b))
    missing = len(set(snap) - set(ref))
    checked = len(set(ref) & set(snap))
    per_field = {f: sum(1 for d in diffs if d[1] == i) for i, f in enumerate(FIELDS)}
    print(f"Porównano {checked} wpisów wzorca; nowych (poza wzorcem): {missing}")
    print(f"Różnic: {len(diffs)}  " + "  ".join(f"{f}={n}" for f, n in per_field.items() if n))
    for key, idx, a, b in diffs[: args.show]:
        row = by_id[key]
        print(f"  #{key} [{row[1]}] {FIELDS[idx]}: {a!r} → {b!r}  | {(row[2] or '')[:70]}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
