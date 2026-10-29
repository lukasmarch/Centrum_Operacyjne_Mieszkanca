"""
Traffic Cache Update Job - Database-First Architecture

Uruchamiany co 4 godziny (6:00, 10:00, 14:00, 18:00, 22:00, 2:00).

Od 29.10.2026 Gemini jest WYSZUKIWACZEM KANDYDATÓW, nie sędzią: jego utrudnienia
dostają wynik wiarygodności w `services/road_reports.py` (źródło × wiek
+ potwierdzenie). Wysoki → pasek, średni → Telegram z „Akceptuj / Usuń”,
niski → nigdzie. Pasek w `traffic_cache` buduje się z zapisanych zgłoszeń.
"""
import asyncio
from datetime import datetime
from typing import List

from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.integrations.traffic_service import TrafficService
from src.services.road_context import RoadItem, fetch_road_context, format_road_context
from src.services.road_reports import (
    Candidate,
    canonical_route,
    drop_multi_route,
    notify_pending,
    score_candidates,
    sync_reports,
    visible_roads,
)
from src.config import settings
from src.database.schema import TrafficCache
from src.utils.logger import setup_logger

logger = setup_logger("TrafficJob")


def build_candidates(roads, road_items: List[RoadItem]) -> List[Candidate]:
    """Utrudnienia z odpowiedzi modelu → kandydaci. Nadawcę i wiek bierzemy
    z pozycji materiału wskazanej przez REF, nie z opisu modelu."""
    candidates: List[Candidate] = []
    for road in roads:
        if road.status == "Płynnie":
            continue
        route = canonical_route(road.name)
        if route is None:
            logger.warning(f"  Nieznana trasa w odpowiedzi modelu: {road.name}")
            continue
        item = None
        if road.ref and road.ref.startswith("M"):
            n = int(road.ref[1:])
            if 1 <= n <= len(road_items):
                item = road_items[n - 1]
        if item is not None:
            candidates.append(Candidate(
                route=route, note=road.description or "", origin="feed",
                kind=item.get("kind", "works"), article_id=item.get("article_id"),
                source_name=item.get("source"), published_at=item.get("published_at"),
                has_term=bool(item.get("has_term")),
            ))
        else:
            candidates.append(Candidate(route=route, note=road.description or "", origin="search"))
    return candidates


async def run_traffic_job_async():
    """
    Async version of traffic job - fetches fresh traffic data and saves to cache.
    """
    logger.info("=" * 80)
    logger.info("TRAFFIC CACHE UPDATE - Gemini Grounding API")
    logger.info("=" * 80)

    # Create fresh engine per run (avoids "attached to different loop" error)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    service = TrafficService()

    try:
        # 1. Materiał źródłowy z własnego feedu — model ma pracować na naszych
        #    zweryfikowanych wpisach z datami, a nie rekonstruować stan dróg
        #    z przypadkowych wyników wyszukiwania.
        async with async_session() as session:
            road_items = await fetch_road_context(session)
        logger.info(f"Materiał źródłowy o drogach: {len(road_items)} wpisów lokalnych")
        for item in road_items[:5]:
            logger.info(f"    [{item['date']}] {item['title'][:70]}")

        # 2. Fetch fresh data from Gemini (kosztowne API call)
        logger.info("Fetching fresh traffic data from Gemini Grounding API...")
        traffic_data = await service.get_traffic_data(
            road_context=format_road_context(road_items)
        )

        if not traffic_data or not traffic_data.roads:
            logger.warning("  ⚠️  No roads data returned - using fallback")
            return

        # Atrapa (typowe czasy przejazdu) nie jest danymi — nie nadpisuj nią cache'u.
        # Stary, ale prawdziwy odczyt jest wart więcej niż świeży wpis "Brak danych",
        # a ERROR w logu sprawia, że awaria Gemini nie przeleży znowu trzech tygodni.
        if traffic_data.is_fallback:
            logger.error(
                "  ✗ Gemini nie zwrócił danych — zachowuję poprzedni wpis w cache. "
                'Sprawdź KREDYTY konta (402 "prepayment credits are depleted"), '
                "limit (429) i dostępność modelu (503). 24.09.2026 log pokazywał "
                "wyłącznie 503, a klucz odpowiadał 402 — komunikat kierował więc "
                "w złą stronę przez cały dzień."
            )
            return

        # 3. Werdykt liczy kod: kandydaci → wynik → zapis zgłoszeń
        now = datetime.utcnow()
        candidates = build_candidates(traffic_data.roads, road_items)
        candidates, multi = drop_multi_route(candidates)
        for c in multi:
            logger.warning(f"  Jedno zdarzenie na kilku trasach — pomijam ({c.route}): {c.note[:100]}")
        candidates = score_candidates(candidates, now)
        for c in candidates:
            logger.info(f"  Kandydat {c.route} [{c.origin}] wynik {c.score:.2f}: {c.note[:80]}")

        async with async_session() as session:
            to_notify = await sync_reports(session, candidates, now)
            for row in to_notify:
                if notify_pending(row):
                    row.notified_at = now
            roads = await visible_roads(session, now)

            await session.execute(
                update(TrafficCache).values(is_current=False)
            )
            session.add(TrafficCache(
                data={
                    "roads": roads,
                    "sources": [src.dict() for src in traffic_data.sources],
                    "is_fallback": False,
                },
                fetched_at=now,
                is_current=True,
                ttl_seconds=14400  # 4 hours
            ))
            await session.commit()

            shown = sum(r["status"] != "Płynnie" for r in roads)
            logger.info(f"  ✓ Pasek: {shown} tras z utrudnieniem, do redakcji: {len(to_notify)}")

        logger.info("=" * 80)
        logger.info("Traffic job finished")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"  ✗ Error in traffic job: {e}", exc_info=True)
    finally:
        await engine.dispose()


def run_traffic_job():
    """
    Wrapper synchroniczny dla async job.
    (APScheduler wymaga funkcji synchronicznej)
    """
    asyncio.run(run_traffic_job_async())


if __name__ == "__main__":
    # Test job ręcznie
    print("🧪 Test Traffic Cache Job...\n")
    run_traffic_job()
