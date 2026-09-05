"""
Migration: ivfflat → HNSW dla `document_embeddings.embedding` (2026-09-05)

**Skąd to się wzięło.** 5.09 mieszkaniec pyta o nocny bieg, który odbywa się
tego samego dnia w Kopaniarzach. Agent podaje mu „Leśny zryw" ze Starych
Jabłonek — bieg z innego powiatu, opisany pół roku wcześniej. Model niczego
nie zmyślił: dostał ten artykuł jako NAJLEPSZE trafienie wyszukiwarki.

Pomiar na produkcji, zapytanie „nocny bieg organizowany przez Nadleśnictwo":

    probes=1 (domyślne):  11 kandydatów, #1 = „Leśny zryw" (0,578)
    probes=10:            96 kandydatów, #1 = bieg w Kopaniarzach (0,582)

Właściwy artykuł miał NAJWYŻSZE podobieństwo w całym korpusie i był dla
wyszukiwarki niewidoczny.

**Dlaczego.** Indeks `idx_embeddings_vector` to ivfflat ze 100 listami, a
`ivfflat.probes` nikt nigdy nie ustawił — wartość domyślna to 1, więc każde
zapytanie ogląda jedną listę, czyli ~1% korpusu. To działa, dopóki wektor
pytania wpada do właściwej listy, i przestaje działać bez ostrzeżenia, gdy
wpadnie obok. Skala na 15 realnych pytaniach mieszkańca: przy probes=1 widać
98 ze 180 dokumentów właściwego top-12, czyli **54%**. Dla „podatek od
nieruchomości stawki" i „GOPS zasiłek rodzinny wniosek" — 0 z 12.

⚠️ To nie jest awaria, którą widać w logu. Zapytanie kończy się sukcesem,
zwraca wyniki, a rerank i progi pracują na materiale, w którym właściwej
odpowiedzi po prostu nie ma. Część porażek retrievalu przypisywanych progom
i rerankowi mogła mieć TĘ przyczynę.

**Dlaczego HNSW, a nie samo `probes`.** Podniesienie probes leczy skutek i
zostawia dwa problemy: wartość trzeba ustawiać przy każdym zapytaniu (GUC
sesji, a sesje bierzemy z puli), a przy rosnącym korpusie trzeba ją stroić.
HNSW ma wysoką trafność z domyślnymi parametrami i nie wymaga strojenia pod
liczbę wierszy. Pomiar czasu zapytania przez tunel SSH (9540 wektorów):

    probes=1 (dziś)      85 ms
    probes=10            50 ms
    bez indeksu (exact)  36 ms

ivfflat był tu WOLNIEJSZY od skanu dokładnego i przy tym gubił wyniki.

**Dlaczego nie zwykły skan dokładny**, skoro dziś jest najszybszy: 9,5 tys.
wektorów rośnie o ~600 miesięcznie i to jedyny parametr, który się zmieni.
Skan dokładny jest liniowy, HNSW logarytmiczny — wybieramy to, co nie wymaga
powrotu do tej decyzji za rok.

⚠️ **`hnsw.ef_search` MUSI być ≥ LIMIT zapytania.** HNSW zwraca najwyżej
`ef_search` wierszy — przy domyślnych 40 zapytanie z `LIMIT 96` dostałoby 40
i wyglądałoby to jak mniejszy korpus, nie jak obcięcie. Ustawia to
`embeddings.hybrid_search` przy każdym zapytaniu (`SET LOCAL`), bo sesje
pochodzą z puli i wartość globalna nie ma jak się utrzymać.

**Kolejność.** Migracja jest bezpieczna PRZED kodem i PO nim: zapytania się nie
zmieniają, zmienia się plan wykonania. Kod dokłada tylko `SET LOCAL`, który na
starej bazie z ivfflat jest nieszkodliwy (ustawia oba GUC-i).

`CREATE INDEX CONCURRENTLY`, bo o 6:50 i 13:45 chodzi job osadzania — zwykłe
`CREATE INDEX` zablokowałoby mu zapis na czas budowy.

Idempotentna. Wycofanie: usuń `idx_embeddings_vector_hnsw` i odtwórz ivfflat
z `add_pgvector.py`.

Użycie:
    cd backend && python -m scripts.migrations.swap_vector_index_to_hnsw
"""
import asyncio
import sys
import time
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from src.config import settings  # noqa: E402

OLD_INDEX = "idx_embeddings_vector"          # ivfflat, lists=100
NEW_INDEX = "idx_embeddings_vector_hnsw"     # hnsw, m=16, ef_construction=64


async def migrate():
    # AUTOCOMMIT: `CREATE INDEX CONCURRENTLY` nie może biec w transakcji.
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")

        version = (await conn.execute(text(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ))).scalar()
        print(f"• pgvector {version}")
        if not version or tuple(int(x) for x in version.split(".")[:2]) < (0, 5):
            print("  ⚠️ HNSW wymaga pgvector ≥ 0.5.0 — przerywam. "
                  "Zamiast tego podnieś `ivfflat.probes` (kod robi to sam).")
            await engine.dispose()
            return

        rows = (await conn.execute(text(
            "SELECT COUNT(*) FROM document_embeddings WHERE embedding IS NOT NULL"
        ))).scalar()
        print(f"• wektorów w tabeli: {rows}")

        existing = {r[0]: r[1] for r in (await conn.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'document_embeddings'"
        ))).all()}

        if NEW_INDEX in existing:
            print(f"• {NEW_INDEX} już istnieje — pomijam budowę")
        else:
            print(f"• buduję {NEW_INDEX} (CONCURRENTLY, bez blokowania zapisu)…")
            started = time.perf_counter()
            await conn.execute(text(f"""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS {NEW_INDEX}
                ON document_embeddings
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """))
            print(f"✓ zbudowany w {time.perf_counter() - started:.1f} s")

        # Indeks zbudowany „CONCURRENTLY" bywa nieważny, gdy budowa się nie
        # powiodła — wtedy planner go nie użyje, a my zdążylibyśmy usunąć stary.
        valid = (await conn.execute(text("""
            SELECT i.indisvalid FROM pg_class c
            JOIN pg_index i ON i.indexrelid = c.oid WHERE c.relname = :n
        """), {"n": NEW_INDEX})).scalar()
        if not valid:
            print(f"  ⚠️ {NEW_INDEX} jest NIEWAŻNY — zostawiam stary indeks. "
                  f"Usuń nowy i powtórz migrację.")
            await engine.dispose()
            return

        if OLD_INDEX in existing:
            print(f"• usuwam stary indeks: {existing[OLD_INDEX][:90]}…")
            await conn.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {OLD_INDEX}"))
            print(f"✓ usunięto {OLD_INDEX}")
        else:
            print(f"• {OLD_INDEX} już nie istnieje")

        final = [r[0] for r in (await conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'document_embeddings' "
            "ORDER BY indexname"
        ))).all()]
        print(f"\n  indeksy na `document_embeddings`: {', '.join(final)}")

        size = (await conn.execute(text(
            f"SELECT pg_size_pretty(pg_relation_size('{NEW_INDEX}'))"
        ))).scalar()
        print(f"  rozmiar {NEW_INDEX}: {size}")

    await engine.dispose()
    print("\n✓ Gotowe. Sprawdź trafność: python -m scripts.test_rag_recall --db")


if __name__ == "__main__":
    asyncio.run(migrate())
