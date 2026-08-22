"""
Scalenie powtórzonych wydarzeń w istniejącej bazie (2026-08-21)

Pipeline od 21.08 nie wpuszcza już powtórek (`ai/event_extractor.py`), ale
w bazie leży to, co weszło wcześniej: 129 wydarzeń z 30 dni pochodziło z 90
artykułów, a jeden turniej w Tuczkach stał w kalendarzu sześć razy.

Dwie reguły, ta sama kolejność co w ekstraktorze:

1. TEN SAM ARTYKUŁ — powtórne przetworzenie tego samego posta. Nie ma tu nic
   do rozstrzygania: zostaje najbogatszy rekord, reszta wskazuje na niego.
2. TEN SAM DZIEŃ I TA SAMA MIEJSCOWOŚĆ — rozstrzyga embedding (próg
   `DUPLICATE_SIMILARITY`, zmierzony na tej właśnie bazie). Wydarzenia bez
   embeddingu są pomijane i wypisane na końcu — dla nich decyzja należy do
   człowieka, bo tekst tych przypadków nie rozstrzyga („Pożegnanie księdza
   Tomasza" = „Msza Święta dziękczynna w Rybnie").

Nic nie kasujemy: powtórka dostaje `canonical_id` i znika z widoków
(`feed_policy.visible_event_conditions`). Cofnięcie to `UPDATE ... SET
canonical_id = NULL`.

Wzorcem grupy zostaje rekord NAJBOGATSZY — z godziną, adresem i opisem — nie
najstarszy: turniej w Tuczkach ma w jednym wpisie godzinę 09:00, w innym nic,
a mieszkańcowi potrzebna jest godzina.

Użycie:
    cd backend && python -m scripts.dedupe_events            # podgląd
    cd backend && python -m scripts.dedupe_events --apply    # zapis
    cd backend && python -m scripts.dedupe_events --days 60  # okno (domyślnie 90)
"""
import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.ai.event_extractor import DUPLICATE_SIMILARITY, _place_key, same_event
from src.config import settings


def _richness(row) -> tuple:
    """Ile ten rekord mówi mieszkańcowi — im więcej, tym lepszy wzorzec grupy."""
    return (
        bool(row.event_time),
        bool(row.address),
        len(row.description or ""),
        -row.id,  # przy remisie starszy wpis, bo do niego mogą już być odwołania
    )


async def _fetch(session: AsyncSession, days: int):
    return (await session.execute(text("""
        SELECT id, title, event_date, event_time, location, address, description,
               source_article_id
        FROM events
        WHERE event_date > now() - make_interval(days => :days)
          AND canonical_id IS NULL
        ORDER BY event_date, id
    """), {"days": days})).all()


async def _similar_pairs(session: AsyncSession, ids: list[int]) -> dict:
    """Podobieństwa par w obrębie jednego dnia — z embeddingów już w bazie."""
    if len(ids) < 2:
        return {}
    rows = (await session.execute(text("""
        SELECT a.source_id, b.source_id, 1 - (a.embedding <=> b.embedding) AS sim
        FROM document_embeddings a
        JOIN document_embeddings b
          ON a.source_type = 'event' AND b.source_type = 'event'
         AND a.source_id < b.source_id
        WHERE a.source_id = ANY(:ids) AND b.source_id = ANY(:ids)
    """), {"ids": ids})).all()
    return {(int(a), int(b)): float(sim) for a, b, sim in rows}


async def dedupe(days: int, apply: bool) -> None:
    print("=" * 72)
    print(f"Scalanie powtórzonych wydarzeń (okno {days} dni, próg {DUPLICATE_SIMILARITY})")
    print("=" * 72)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        rows = await _fetch(session, days)
        by_id = {r.id: r for r in rows}
        merges: dict[int, tuple[int, str]] = {}   # powtórka → (wzorzec, powód)

        # --- 1. ten sam artykuł ------------------------------------------------
        by_article = defaultdict(list)
        for row in rows:
            if row.source_article_id:
                by_article[row.source_article_id].append(row)

        for article_id, group in by_article.items():
            if len(group) < 2:
                continue
            canonical = max(group, key=_richness)
            for row in group:
                if row.id != canonical.id:
                    merges[row.id] = (canonical.id, f"ten sam artykuł #{article_id}")

        # --- 2. ten sam dzień i miejsce, rozstrzyga embedding -------------------
        by_day = defaultdict(list)
        for row in rows:
            by_day[row.event_date.date()].append(row)

        no_embedding: list[int] = []
        for day, group in sorted(by_day.items()):
            candidates = [r for r in group if r.id not in merges]
            if len(candidates) < 2:
                continue
            sims = await _similar_pairs(session, [r.id for r in candidates])
            embedded = {i for pair in sims for i in pair}
            no_embedding.extend(
                r.id for r in candidates if r.id not in embedded and len(candidates) > 1
            )

            # Klastrowanie zachłanne wokół wzorca. Kandydaci idą od NAJBOGATSZEGO,
            # więc pierwszy w grupie jest jednocześnie jej wzorcem i punktem
            # odniesienia — inaczej wpis dołączał do grupy przez podobieństwo do
            # jednego rekordu, a scalany był z innym, wybranym później. Efekt był
            # widoczny na Dniach Rybna: do wzorca trafiały koncerty podobne
            # w 0,50, choć próg wynosi 0,60.
            clusters: list[list] = []
            for row in sorted(candidates, key=_richness, reverse=True):
                for cluster in clusters:
                    head = cluster[0]
                    sim = sims.get((min(row.id, head.id), max(row.id, head.id)), 0.0)
                    # Jedna reguła na projekt — ta sama, którą stosuje ekstraktor
                    if same_event(sim, row.location, head.location):
                        cluster.append(row)
                        break
                else:
                    clusters.append([row])

            for cluster in clusters:
                canonical = cluster[0]
                for row in cluster[1:]:
                    sim = sims.get(
                        (min(row.id, canonical.id), max(row.id, canonical.id)), 0.0
                    )
                    merges[row.id] = (
                        canonical.id,
                        f"{day} / {row.location or '—'} / podobieństwo {sim:.2f}",
                    )

        # Łańcuchy: rekord scalony regułą 1 mógł zostać wzorcem w regule 2.
        # Wskaźnik ma prowadzić do wpisu, który sam nie jest powtórką — inaczej
        # widok filtrujący `canonical_id IS NULL` gubi całą grupę.
        for dup_id in list(merges):
            canonical_id, reason = merges[dup_id]
            seen = {dup_id}
            while canonical_id in merges and canonical_id not in seen:
                seen.add(canonical_id)
                canonical_id = merges[canonical_id][0]
            merges[dup_id] = (canonical_id, reason)

        # --- raport -------------------------------------------------------------
        if not merges:
            print("\n✓ Nie znaleziono powtórek.")
        else:
            grouped = defaultdict(list)
            for dup_id, (canonical_id, reason) in merges.items():
                grouped[canonical_id].append((dup_id, reason))

            print(f"\nDo scalenia: {len(merges)} rekordów w {len(grouped)} grupach\n")
            for canonical_id, dups in sorted(grouped.items()):
                head = by_id[canonical_id]
                when = head.event_date.strftime("%d.%m")
                print(f"  ZOSTAJE #{canonical_id} [{when} {head.event_time or '—'}] "
                      f"{(head.title or '')[:52]}  ({head.location or '—'})")
                for dup_id, reason in sorted(dups):
                    print(f"    ↳ #{dup_id} {(by_id[dup_id].title or '')[:48]:<50} {reason}")

        if no_embedding:
            print(f"\n⚠ Bez embeddingu, nierozstrzygnięte ({len(set(no_embedding))}): "
                  f"{sorted(set(no_embedding))}")
            print("  Uruchom `python -m scripts.run_embedding_job`, potem ten skrypt ponownie.")

        if not apply:
            print("\n(podgląd — nic nie zapisano; dopisz --apply)")
        elif merges:
            for dup_id, (canonical_id, _) in merges.items():
                await session.execute(
                    text("UPDATE events SET canonical_id = :c WHERE id = :d"),
                    {"c": canonical_id, "d": dup_id},
                )
            # Powtórka nie jest materiałem RAG — wydarzenie ma w wyszukiwarce stać raz
            await session.execute(text("""
                DELETE FROM document_embeddings
                WHERE source_type = 'event' AND source_id = ANY(:ids)
            """), {"ids": list(merges.keys())})
            await session.commit()
            print(f"\n✓ Scalono {len(merges)} rekordów, ich embeddingi usunięte.")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scalanie powtórzonych wydarzeń")
    parser.add_argument("--days", type=int, default=90, help="okno wstecz (domyślnie 90)")
    parser.add_argument("--apply", action="store_true", help="zapisz zmiany")
    args = parser.parse_args()
    asyncio.run(dedupe(args.days, args.apply))
