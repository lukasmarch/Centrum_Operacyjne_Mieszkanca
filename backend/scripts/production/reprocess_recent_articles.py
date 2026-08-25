"""
Rekategoryzacja artykułów z ostatnich N dni (poprawki przedpremierowe, 2026-07-26)

Przepuszcza artykuły ponownie przez ArticleProcessor po zaostrzeniu
CATEGORIZATION_PROMPT: naprawia fałszywe kategorie AWARIA (zakończone
inwestycje, OSP w Sporcie), generuje display_title (nagłówek AI zamiast
kopii ze źródła) i oznacza posty-zapychacze (is_filler).

Użycie:
    cd backend && python -u -m scripts.production.reprocess_recent_articles [--days 14]

`--only-flagged` zawęża przebieg do artykułów oznaczonych jako Awaria lub filler —
tylko te klasy mogą być fałszywie dodatnie po zaostrzeniu promptu.

`--category NAZWA` zawęża do jednej kategorii. Dopisane 25.08.2026 przy rozbiciu
„Urzędu": zmiana dotyczyła jednego worka, a przebieg po całym oknie przepisałby
przy okazji `display_title` i `summary` wszystkim pozostałym wpisom — tym, których
nikt nie prosił o zmianę. Przebieg jest tani, ale nie jest bez skutków.
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import or_, select

from src.ai.article_processor import ArticleProcessor
from src.database.connection import async_session
from src.database.schema import Article


async def reprocess(days: int, only_flagged: bool = False, category: str = None):
    cutoff = datetime.utcnow() - timedelta(days=days)
    processor = ArticleProcessor()

    async with async_session() as session:
        stmt = select(Article).where(
            or_(
                Article.published_at >= cutoff,
                Article.scraped_at >= cutoff,
            )
        )
        if only_flagged:
            stmt = stmt.where(
                or_(Article.category == "Awaria", Article.is_filler == True)
            )
        if category:
            stmt = stmt.where(Article.category == category)
        result = await session.execute(
            stmt.order_by(Article.published_at.desc().nulls_last())
        )
        articles = result.scalars().all()
        print(f"Artykułów z ostatnich {days} dni: {len(articles)}")

        ok, failed = 0, 0
        for i, article in enumerate(articles, 1):
            old_category = article.category
            try:
                updated = await processor.process_article(article, session)
                if updated is None:
                    continue
                marker = " [FILLER]" if updated.is_filler else ""
                change = (
                    f"{old_category} → {updated.category}"
                    if old_category != updated.category
                    else updated.category
                )
                print(f"[{i}/{len(articles)}] #{updated.id} {change}{marker}: {updated.display_title}")
                ok += 1
            except Exception as e:
                failed += 1
                print(f"[{i}/{len(articles)}] #{article.id} BŁĄD: {e}")

    print(f"\nGotowe: {ok} przetworzonych, {failed} błędów.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--only-flagged", action="store_true")
    parser.add_argument("--category", help="tylko wpisy z tą kategorią, np. Urząd")
    args = parser.parse_args()
    asyncio.run(reprocess(args.days, args.only_flagged, args.category))
