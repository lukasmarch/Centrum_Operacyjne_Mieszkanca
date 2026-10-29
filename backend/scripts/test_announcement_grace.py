"""
Ogłoszenie znika z końcem zdarzenia, relacja ma dobę karencji (2026-10-29). Z BAZĄ — `db-tests` w CI.

**Skąd to.** 29.10.2026 „Ogłoszenie o zebraniu wiejskim sołectwa Żabiny” (zebranie
28.10 o 18:00) stało w feedzie dobę po fakcie z szarym kafelkiem daty. Doba
karencji (`ENDED_EVENT_GRACE_H`) jest dla relacji — post o wczorajszych dożynkach
czyta się jako relację. Zaproszenie na zebranie dzień po zebraniu jest nieprawdą.
Decyzja Łukasza: bez karencji dla sołectw i kategorii „Urząd”.

Reguła żyje w SQL (`feed_policy.publishable_conditions`), z której korzystają feed,
briefing, newsletter, push i agenci — dlatego test idzie na prawdziwym Postgresie.
Zakłada własne wpisy i sprząta po sobie.

Użycie: cd backend && python -m scripts.test_announcement_grace
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select

from src.database.connection import async_session
from src.database.schema import Article, Source
from src.services.feed_policy import publishable_conditions

TAG = "test-announcement-grace"
results: list = []


def check(label, got, expected):
    ok = got == expected
    results.append(ok)
    print(f"{'✓' if ok else '✗'} {label:.<66} {got}" + ("" if ok else f" (oczekiwano {expected})"))


async def run() -> int:
    now = datetime.utcnow()
    ended_2h = now - timedelta(hours=5)       # start 5 h temu, koniec (3 h) 2 h temu
    ended_2d = now - timedelta(hours=60)      # koniec dawno po karencji
    upcoming = now + timedelta(hours=20)

    async with async_session() as session:
        solectwa = (await session.execute(
            select(Source).where(Source.name == "RybnoLive - Sołectwa")
        )).scalars().first()
        other = Source(name=f"Test źródło {TAG}", type="test", status="disabled", created_at=now)
        session.add(other)
        await session.flush()
        if solectwa is None:
            solectwa = Source(name="RybnoLive - Sołectwa", type="community", status="disabled", created_at=now)
            session.add(solectwa)
            await session.flush()
            created_solectwa = solectwa.id
        else:
            created_solectwa = None

        def art(key, source, event_at, category=None):
            return Article(
                source_id=source.id, title=f"Zebranie wiejskie w Żabinach {key}",
                content="Zapraszamy mieszkańców na zebranie wiejskie.",
                url=f"https://example.invalid/{TAG}/{key}", scraped_at=now, published_at=now,
                processed=True, event_at=event_at, category=category, external_id=f"{TAG}:{key}",
            )

        cases = {
            "sol_ended": art("sol_ended", solectwa, ended_2h, "Społeczność"),
            "sol_upcoming": art("sol_upcoming", solectwa, upcoming, "Społeczność"),
            "urzad_ended": art("urzad_ended", other, ended_2h, "Urząd"),
            "relacja_ended": art("relacja_ended", other, ended_2h, "Kultura"),
            "bez_kategorii_ended": art("bez_kategorii_ended", other, ended_2h, None),
            "relacja_old": art("relacja_old", other, ended_2d, "Kultura"),
            "bez_terminu": art("bez_terminu", solectwa, None, "Urząd"),
        }
        session.add_all(cases.values())
        await session.flush()

        try:
            visible = set((await session.execute(
                select(Article.id).where(
                    Article.id.in_([a.id for a in cases.values()]),
                    *publishable_conditions(Article, now=now),
                )
            )).scalars().all())
            seen = {k: a.id in visible for k, a in cases.items()}

            check("STAN 29.10: ogłoszenie sołectwa po zebraniu znika", seen["sol_ended"], False)
            check("ogłoszenie sołectwa przed terminem jest", seen["sol_upcoming"], True)
            check("kategoria „Urząd” po terminie znika (sesja, komisja)", seen["urzad_ended"], False)
            check("relacja (inna kategoria) ma dobę karencji", seen["relacja_ended"], True)
            check("wpis BEZ kategorii nie traci karencji (NULL ≠ ogłoszenie)", seen["bez_kategorii_ended"], True)
            check("relacja po dobie karencji znika jak dotąd", seen["relacja_old"], False)
            check("ogłoszenie bez terminu — reguła go nie dotyczy", seen["bez_terminu"], True)
        finally:
            await session.rollback()

    async with async_session() as session:
        await session.execute(delete(Article).where(Article.url.like(f"https://example.invalid/{TAG}/%")))
        await session.execute(delete(Source).where(Source.name == f"Test źródło {TAG}"))
        if created_solectwa:
            await session.execute(delete(Source).where(Source.id == created_solectwa))
        await session.commit()

    print("-" * 78)
    failures = results.count(False)
    print(f"{len(results) - failures}/{len(results)} zgodnych z oczekiwaniem")
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(run()) else 0)
