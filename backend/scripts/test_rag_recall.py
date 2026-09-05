"""
Trafność wyszukiwarki: czy indeks pokazuje to, co NAPRAWDĘ jest najbliżej (5.09.2026)

**Po co ten test istnieje.** Indeks wektorowy jest przybliżony i nie ma jak
się poskarżyć. Gdy przestaje trafiać, zapytanie nadal kończy się sukcesem,
nadal zwraca dokumenty i nadal wyglądają one sensownie — brakuje wśród nich
tylko właściwego. Żaden istniejący test tego nie widział, bo wszystkie pytają
„czy coś wróciło", a nie „czy wróciło to, co powinno".

5.09.2026 kosztowało to fałszywą odpowiedź dla mieszkańca: na pytanie o nocny
bieg, który odbywał się tego dnia w Kopaniarzach, agent podał bieg z innego
powiatu sprzed pół roku. Artykuł o właściwym biegu miał najwyższe podobieństwo
w całej bazie (0,582) i nie znalazł się w wynikach wcale, bo `ivfflat.probes`
było domyślne (1 ze 100 list).

**Jak mierzymy.** Prawdę liczy SKAN DOKŁADNY (`enable_indexscan = off`) — to
jedyna definicja „najbliższych sąsiadów", która nie zależy od tego, jaki indeks
akurat stoi w bazie. Potem to samo zapytanie idzie ZWYKŁĄ ścieżką produkcyjną
(`hybrid_search`) i sprawdzamy, ile z prawdziwego top-K faktycznie zobaczyła.

⚠️ Nie sprawdzamy „czy odpowiedź jest dobra" — od tego jest `test_agent_answers`.
Tu chodzi o jedną warstwę niżej: czy materiał w ogóle DOTARŁ do agenta.

Użycie:
    cd backend && python -m scripts.test_rag_recall           # potrzebuje bazy
    cd backend && python -m scripts.test_rag_recall --verbose # + rozbieżności

Kod wyjścia 1, gdy trafność spadnie poniżej progu.
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text  # noqa: E402

from src.ai.embeddings import embedding_service  # noqa: E402
from src.database.connection import async_session  # noqa: E402
from src.services.search_synonyms import expand_query  # noqa: E402

# Pytania dobrane tak, żeby pokryć oba korpusy i OBA rodzaje sformułowań:
# takie z mocnym słowem wyróżniającym („azbest") i takie opisowe, w których
# wektor pytania nie wpada w oczywiste miejsce — a to właśnie one wykładały
# indeks przybliżony (5.09: „nocny bieg organizowany przez Nadleśnictwo").
QUERIES: list[tuple[str, list[str]]] = [
    ("nocny bieg organizowany przez Nadleśnictwo", ["article"]),
    ("VI Leśny Nocny Bieg Kopaniarze", ["article"]),
    ("co nowego w gminie Rybno", ["article"]),
    ("spotkanie z mieszkańcami w sprawie planu ogólnego", ["article"]),
    ("dożynki gminne", ["article"]),
    ("turniej piłki nożnej w Tuczkach", ["article"]),
    ("przerwa w dostawie prądu Rybno", ["article"]),
    ("remont drogi Tuczki Koszelewy", ["article"]),
    ("podatek od nieruchomości stawki",
     ["bip_static", "bip", "legal_act", "article"]),
    ("GOPS zasiłek rodzinny wniosek",
     ["bip_static", "bip", "legal_act", "article"]),
    ("dotacja na usunięcie azbestu eternitu",
     ["bip_static", "bip", "legal_act", "article"]),
    ("kiedy sesja rady gminy Rybno",
     ["bip_static", "bip", "legal_act", "article"]),
]

# Ilu najbliższych sąsiadów porównujemy. Tyle, ile realnie trafia do modelu:
# `_search` prosi hybrid_search o 12–16 kandydatów, z których rerank zostawia 8.
TOP_K = 12

# Poniżej tego progu wyszukiwarka gubi materiał na tyle często, że odpowiedzi
# przestają być powtarzalne. 0,90 to nie ideał teoretyczny — to poziom, przy
# którym HNSW z `ef_search` z `embeddings.py` pracuje bez strojenia.
MIN_RECALL = 0.90

# Trafienie #1 jest ważniejsze niż reszta: to ono decyduje, o czym agent napisze.
# Zgubione w pierwszej pozycji = odpowiedź NIE NA TEMAT, nie „uboższa odpowiedź".
MIN_TOP1_HITS = 1.0

THRESHOLD = 0.35


async def _exact_top(session, vec: str, source_types: list[str], k: int) -> list[int]:
    """Prawdziwych K najbliższych — skan dokładny, bez indeksu."""
    placeholders = ", ".join(f":st_{i}" for i in range(len(source_types)))
    params = {f"st_{i}": st for i, st in enumerate(source_types)}
    await session.execute(text("SET LOCAL enable_indexscan = off"))
    await session.execute(text("SET LOCAL enable_bitmapscan = off"))
    rows = (await session.execute(text(f"""
        SELECT id FROM document_embeddings
        WHERE 1 - (embedding <=> '{vec}'::vector) > {THRESHOLD}
          AND source_type IN ({placeholders})
        ORDER BY embedding <=> '{vec}'::vector
        LIMIT {k}
    """), params)).fetchall()
    return [r[0] for r in rows]


async def _index_top(session, vec: str, source_types: list[str], k: int) -> list[int]:
    """K najbliższych tak, jak widzi je PRODUKCJA — z indeksem i z `SET LOCAL`
    z `embeddings.py`. Celowo nie wołamy tu `hybrid_search`: chcemy zmierzyć
    samą gałąź wektorową, bez zaciemniania jej przez BM25 i RRF."""
    await embedding_service._widen_index_scan(session)
    placeholders = ", ".join(f":st_{i}" for i in range(len(source_types)))
    params = {f"st_{i}": st for i, st in enumerate(source_types)}
    rows = (await session.execute(text(f"""
        SELECT id FROM document_embeddings
        WHERE 1 - (embedding <=> '{vec}'::vector) > {THRESHOLD}
          AND source_type IN ({placeholders})
        ORDER BY embedding <=> '{vec}'::vector
        LIMIT {k}
    """), params)).fetchall()
    return [r[0] for r in rows]


async def main(verbose: bool = False) -> int:
    print("=" * 78)
    print("TRAFNOŚĆ WYSZUKIWARKI — indeks kontra skan dokładny")
    print("=" * 78)

    async with async_session() as session:
        idx = (await session.execute(text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'document_embeddings' AND indexdef ILIKE '%USING hnsw%' "
            "   OR (tablename = 'document_embeddings' AND indexdef ILIKE '%USING ivfflat%')"
        ))).scalars().all()
        print("\nIndeks wektorowy w tej bazie:")
        for line in idx or ["  (brak — zapytania idą skanem dokładnym)"]:
            print(f"  {line[:110]}")

        total_hits = total_truth = 0
        top1_ok = 0
        problems: list[str] = []

        print(f"\n{'pytanie':<46}{'recall@' + str(TOP_K):>10}{'#1':>6}")
        print("-" * 78)

        for query, source_types in QUERIES:
            emb = await embedding_service.embed_text(expand_query(query))
            vec = "[" + ",".join(str(x) for x in emb) + "]"

            truth = await _exact_top(session, vec, source_types, TOP_K)
            await session.rollback()
            got = await _index_top(session, vec, source_types, TOP_K)
            await session.rollback()

            if not truth:
                print(f"{query[:46]:<46}{'brak danych':>10}")
                continue

            hits = len(set(truth) & set(got))
            total_hits += hits
            total_truth += len(truth)
            same_first = bool(got) and got[0] == truth[0]
            top1_ok += same_first

            recall = hits / len(truth)
            mark = "" if recall >= MIN_RECALL and same_first else "  ⚠️"
            print(f"{query[:46]:<46}{hits:>5}/{len(truth):<4}"
                  f"{'tak' if same_first else 'NIE':>6}{mark}")

            if not same_first:
                pokazal = got[0] if got else "—"
                problems.append(
                    f"„{query}” — indeks stawia na 1. miejscu fragment {pokazal}, "
                    f"a najbliższy jest {truth[0]}"
                )
            if verbose and recall < 1.0:
                print(f"      zgubione: {sorted(set(truth) - set(got))}")

        recall = total_hits / total_truth if total_truth else 0.0
        top1_rate = top1_ok / len(QUERIES)

        print("-" * 78)
        print(f"\n  recall@{TOP_K}: {total_hits}/{total_truth} = {recall:.0%}  "
              f"(próg {MIN_RECALL:.0%})")
        print(f"  trafiony 1. wynik: {top1_ok}/{len(QUERIES)} = {top1_rate:.0%}  "
              f"(próg {MIN_TOP1_HITS:.0%})")

        if problems:
            print("\n  Rozbieżności — to są pytania, na które agent odpowie NIE NA TEMAT:")
            for p in problems:
                print(f"   • {p}")

        ok = recall >= MIN_RECALL and top1_rate >= MIN_TOP1_HITS
        if ok:
            print("\n✓ Wyszukiwarka widzi to, co powinna.")
        else:
            print("\n✗ Wyszukiwarka GUBI materiał. Sprawdź indeks i `SET LOCAL` "
                  "w `embeddings._widen_index_scan`; migracja: "
                  "`python -m scripts.migrations.swap_vector_index_to_hnsw`")
        return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true",
                        help="pokaż identyfikatory zgubionych fragmentów")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(verbose=args.verbose)))
