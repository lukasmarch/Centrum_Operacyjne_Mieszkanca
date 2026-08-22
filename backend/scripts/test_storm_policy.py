"""
Weryfikacja trybu sztormowego (`services/storm_policy.py`).

22.08.2026 przez gminę przeszła nawałnica: Energa zgłosiła wyłączenia w Gralewie,
Grądach i Kopaniarzach, mieszkaniec zgłosił brak wody, a strona milczała — bo
Facebooka poza profilem gminy czytamy raz na dobę, o 6:00. Tryb sztormowy sięga
po płatne źródła TYLKO w dniu, w którym rytm dwóch przebiegów nie wystarcza.

Test pilnuje obu stron naraz, bo ciągną w przeciwne strony: tryb ma się włączyć,
gdy dzieje się coś realnego, i NIE MOŻE włączać się w zwyczajny wtorek — każde
uruchomienie kosztuje przebieg Apify.

  1. PRÓG    — ile wyłączeń przestaje być zbiegiem okoliczności;
  2. HAMULCE — odstęp od ostatniego pobrania i godziny doby;
  3. STAN BAZY (--db) — czy dziś warunek jest spełniony na produkcji.

Użycie:
    cd backend && python -m scripts.test_storm_policy
    cd backend && python -m scripts.test_storm_policy --db
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services import storm_policy

NOW = datetime(2026, 8, 22, 9, 15)          # 11:15 czasu lokalnego
NOW_LOCAL = datetime(2026, 8, 22, 11, 15)


def run_cases() -> int:
    print("=" * 74)
    print("1. PRÓG — kiedy dzień przestaje być zwyczajny")
    print("=" * 74)

    checks = [
        (
            "jedno wyłączenie w gminie to nie sztorm (zdarza się co tydzień)",
            storm_policy.storm_reason(1, False) is None,
            "None",
        ),
        (
            "dwa wyłączenia naraz uruchamiają tryb",
            storm_policy.storm_reason(2, False) is not None,
            storm_policy.storm_reason(2, False),
        ),
        (
            "samo ostrzeżenie meteo wystarczy, bez wyłączeń",
            storm_policy.storm_reason(0, True) is not None,
            storm_policy.storm_reason(0, True),
        ),
        (
            "zwyczajny dzień nie uruchamia niczego",
            storm_policy.storm_reason(0, False) is None,
            "None",
        ),
        (
            "powód jest TEKSTEM — trafia do logu, nie do rekonstrukcji z bazy",
            isinstance(storm_policy.storm_reason(3, False), str),
            storm_policy.storm_reason(3, False),
        ),
    ]

    print()
    print("=" * 74)
    print("2. HAMULCE — żeby tryb sztormowy nie stał się trzecim przebiegiem")
    print("=" * 74)

    checks += [
        (
            "godzina 11:15 mieści się w oknie",
            storm_policy.within_active_hours(NOW_LOCAL),
            f"okno {storm_policy.ACTIVE_HOURS}",
        ),
        (
            "o 4 nad ranem nie płacimy za Apify",
            not storm_policy.within_active_hours(NOW_LOCAL.replace(hour=4)),
            "04:00 poza oknem",
        ),
        (
            "o 23:00 też nie",
            not storm_policy.within_active_hours(NOW_LOCAL.replace(hour=23)),
            "23:00 poza oknem",
        ),
        (
            "pobranie sprzed 30 minut blokuje kolejne",
            not storm_policy.enough_gap(NOW - timedelta(minutes=30), NOW),
            f"odstęp min. {storm_policy.MIN_GAP_H} h",
        ),
        (
            "po trzech godzinach wolno znowu",
            storm_policy.enough_gap(NOW - timedelta(hours=3), NOW),
            "3 h > próg",
        ),
        (
            "źródło nigdy nie pobierane nie ma czego oszczędzać",
            storm_policy.enough_gap(None, NOW),
            "None → True",
        ),
        # Bezpiecznik kosztowy: przy sześciogodzinnej wichurze w oknie 6–22
        # tryb może dołożyć najwyżej tyle przebiegów, ile mieści się w odstępie.
        (
            "sześciogodzinna wichura to najwyżej trzy dodatkowe przebiegi",
            int(6 / storm_policy.MIN_GAP_H) == 3,
            f"6 h / {storm_policy.MIN_GAP_H} h = {int(6 / storm_policy.MIN_GAP_H)}",
        ),

        # --- trwa czy dopiero będzie ------------------------------------------
        # Energa re-scrapuje wpisy planowane co 3 h, więc wyłączenie ogłoszone
        # na 28 sierpnia ma dziś świeży `scraped_at`. Pomiar 22.08 przed tą
        # poprawką: sześć „wyłączeń w gminie", z czego trzy na przyszły tydzień.
        (
            "zapowiedź na przyszły tydzień nie jest sztormem",
            not storm_policy.is_ongoing(NOW + timedelta(days=6),
                                        NOW + timedelta(days=6, hours=5), NOW),
            "28 sierpnia → nie liczy się",
        ),
        (
            "wyłączenie trwające teraz liczy się",
            storm_policy.is_ongoing(NOW - timedelta(hours=1),
                                    NOW + timedelta(hours=3), NOW),
            "trwa → liczy się",
        ),
        (
            "wyłączenie zaczynające się za godzinę też",
            storm_policy.is_ongoing(NOW + timedelta(hours=1),
                                    NOW + timedelta(hours=5), NOW),
            f"margines {storm_policy.ONGOING_MARGIN_H} h",
        ),
        (
            "wyłączenie zakończone przed godziną już nie",
            not storm_policy.is_ongoing(NOW - timedelta(hours=5),
                                        NOW - timedelta(hours=1), NOW),
            "po wszystkim",
        ),
        (
            "awaria bez terminu liczy się jak trwająca (kanał bieżących Energi)",
            storm_policy.is_ongoing(None, None, NOW),
            "brak terminu → trwa",
        ),
    ]

    failed = 0
    for label, ok, detail in checks:
        failed += not ok
        print(f"{'✓' if ok else '✗'} {label:.<62} {detail}")

    print("-" * 74)
    print(f"{len(checks) - failed}/{len(checks)} zgodnych z oczekiwaniem")
    return failed


async def run_db() -> int:
    """Czy warunek sztormowy jest spełniony NA ŻYWO — i czy hamulce puszczają."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.config import settings
    from src.database.schema import Article, Source
    from src.scheduler.article_job import STORM_SOCIAL_SOURCES
    from src.services import weather_alert
    from src.services.feed_policy import LOCAL_TZ, is_local_article

    print()
    print("=" * 74)
    print("3. STAN BAZY — czy teraz jest dzień sztormowy")
    print("=" * 74)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.utcnow()
    now_local = datetime.now(LOCAL_TZ)

    async with async_session() as session:
        since = now - timedelta(hours=storm_policy.LOOKBACK_H)
        rows = (await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.scraped_at >= since)
        )).all()

        outages = [
            (a, src) for a, src in rows
            if (src or "").startswith("Energa")
            and storm_policy.is_ongoing(a.event_at, a.event_until, now)
            and is_local_article(src, a.title, a.content)
        ]
        alerts = [
            (a, src) for a, src in rows
            if weather_alert.is_weather_alert(a.title, a.content)
            and not weather_alert.expired(a.title, a.content, a.published_at,
                                          a.event_until, now)
        ]
        last_scraped = (await session.execute(
            select(Source.last_scraped).where(Source.name.in_(STORM_SOCIAL_SOURCES))
            .order_by(Source.last_scraped.desc()).limit(1)
        )).scalar_one_or_none()

    await engine.dispose()

    reason = storm_policy.storm_reason(len(outages), bool(alerts))
    gap_ok = storm_policy.enough_gap(last_scraped, now)
    hours_ok = storm_policy.within_active_hours(now_local)

    print(f"  wyłączenia w gminie (ostatnie {storm_policy.LOOKBACK_H} h): {len(outages)}")
    for a, _ in outages[:5]:
        print(f"      • {(a.display_title or a.title or '')[:62]}")
    print(f"  ostrzeżenia meteo obowiązujące: {len(alerts)}")
    print(f"  ostatnie pobranie profili FB:   {last_scraped}  → odstęp OK: {gap_ok}")
    print(f"  godzina lokalna {now_local:%H:%M}            → okno OK:   {hours_ok}")
    print()
    if reason and gap_ok and hours_ok:
        print(f"  ⛈  TRYB SZTORMOWY BY SIĘ URUCHOMIŁ — {reason}")
    elif reason:
        print(f"  ⏸  warunek spełniony ({reason}), ale hamulec trzyma")
    else:
        print("  ☀️  dzień zwyczajny — tryb sztormowy śpi")
    return 0


def main() -> int:
    failed = run_cases()
    if "--db" in sys.argv:
        failed += asyncio.run(run_db())
    return failed


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
