"""
Skład newslettera tygodniowego — strażnik po audycie 11.10.2026 (F-021).

Tygodnik był jedyną ścieżką wyboru treści bez polityki feedu: 20 najnowszych
wpisów jak leci, a model dostawał 10 pierwszych. Wydanie z 10.10 (sobota,
10:00) objęło w praktyce ostatnie 19 godzin, w tym zapychacz (6576) i wpis
przed kategoryzacją (6575). Szło do WSZYSTKICH subskrybentów.

Bez modelu i bez wysyłki — sprawdza wyłącznie SKŁAD (`select_weekly_articles`).
Domyślny moment to wysyłka z 10.10.2026 08:00 UTC; wymaga bazy z danymi z tego
tygodnia (zrzut produkcji z 10.10 — `scripts/sync_prod_do_lokalnej.sh`).
`--now` liczy skład dla innej chwili (np. podgląd przed sobotą).

    cd backend && python -m scripts.test_newsletter_weekly [--now 2026-10-17T08:00]
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlmodel import select

from src.database import Article
from src.database.connection import async_session
from src.newsletter.generator import WEEKLY_WINDOW_DAYS, select_weekly_articles
from src.services.feed_policy import MIN_ARTICLE_LOCALITY, publishable_conditions

AUDIT_SEND = datetime(2026, 10, 10, 8, 0)
results: list[bool] = []


def check(label: str, ok: bool, detail="") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))
    return ok


def describe(articles: list) -> None:
    for a in articles:
        title = (a.display_title or a.title or "")[:70]
        print(f"      {a.id:>5}  loc={a.locality}  {a.published_at:%d.%m %H:%M}  {a.category or '—':<12} {title}")


async def main() -> int:
    now = AUDIT_SEND
    if "--now" in sys.argv:
        now = datetime.fromisoformat(sys.argv[sys.argv.index("--now") + 1])
    since = now - timedelta(days=WEEKLY_WINDOW_DAYS)

    async with async_session() as session:
        # Stara reguła (do 11.10) — tylko jako pomiar „przed"
        old = (await session.execute(
            select(Article)
            .where(Article.published_at >= since)
            .where(Article.published_at <= now)
            .order_by(Article.published_at.desc())
            .limit(10)
        )).scalars().all()
        new = await select_weekly_articles(session, now=now)
        allowed = set((await session.execute(
            select(Article.id)
            .where(Article.published_at >= since)
            .where(Article.processed == True)  # noqa: E712
            .where(*publishable_conditions(Article, now=now))
        )).scalars().all())

    def local(arts):
        return sum(1 for a in arts if (a.locality or 0) >= MIN_ARTICLE_LOCALITY)

    def span_h(arts):
        if not arts:
            return 0
        times = [a.published_at for a in arts]
        return (max(times) - min(times)).total_seconds() / 3600

    print(f"\nWysyłka {now:%d.%m.%Y %H:%M} UTC, okno {WEEKLY_WINDOW_DAYS} dni")
    print(f"\n   PRZED (stara reguła): lokalnych {local(old)}/{len(old)}, rozpiętość {span_h(old):.0f} h")
    describe(old)
    print(f"\n   PO (select_weekly_articles): lokalnych {local(new)}/{len(new)}, rozpiętość {span_h(new):.0f} h")
    describe(new)
    print()

    check("tygodnik ma materiał", len(new) >= 5, len(new))
    check("skład ⊆ publikowalne i przetworzone", {a.id for a in new} <= allowed,
          {a.id for a in new} - allowed)
    check("zapychacze i wpisy przed kategoryzacją poza składem",
          not [a.id for a in new if a.is_filler or not a.processed])
    check("wszystko z okna 7 dni", all(since <= a.published_at <= now for a in new))
    check(f"≥ 8/10 wpisów z gminy (locality ≥ {MIN_ARTICLE_LOCALITY})",
          local(new) >= min(8, len(new)), f"{local(new)}/{len(new)}")
    check("bez powtórek tego samego tytułu",
          len({(a.display_title or a.title) for a in new}) == len(new))
    if now == AUDIT_SEND:
        ids = {a.id for a in new}
        check("6576 (zapychacz z wydania 10.10) poza składem", 6576 not in ids)
        check("6575 (bez kategoryzacji) poza składem", 6575 not in ids)
        check("tydzień, nie ostatnia doba (rozpiętość > 48 h)", span_h(new) > 48, f"{span_h(new):.0f} h")

    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
