"""
Diagnose Pipeline - Szczegółowa analiza kategoryzacji i dat

Sprawdza:
1. Ile artykułów ma kategorie (per źródło)
2. Czy artykuły mają content i daty
3. Jakie daty artykułów wchodzą do Daily Summary
4. Czy dane nie są za stare
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import Article, Source


async def main():
    print("="*80)
    print("PIPELINE DIAGNOSTICS - Detailed Analysis")
    print("="*80)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Kategoryzacja per źródło
        print("\n" + "="*80)
        print("1. CATEGORIZATION STATUS PER SOURCE")
        print("="*80)

        result = await session.execute(
            select(
                Source.name,
                func.count(Article.id).label('total'),
                func.sum(case((Article.processed == True, 1), else_=0)).label('processed'),
                func.sum(case((Article.category.isnot(None), 1), else_=0)).label('with_category')
            )
            .join(Article, Source.id == Article.source_id)
            .group_by(Source.name)
            .order_by(func.count(Article.id).desc())
        )

        print(f"\n{'Source':<30} {'Total':<10} {'Processed':<12} {'W/ Category':<12} {'%'}")
        print("-"*80)

        for source_name, total, processed, with_cat in result:
            processed = processed or 0
            with_cat = with_cat or 0
            pct = (processed / total * 100) if total > 0 else 0
            print(f"{source_name:<30} {total:<10} {processed:<12} {with_cat:<12} {pct:.1f}%")

        # 2. Content & Date quality per source
        print("\n" + "="*80)
        print("2. DATA QUALITY PER SOURCE")
        print("="*80)

        result = await session.execute(
            select(
                Source.name,
                func.count(Article.id).label('total'),
                func.sum(case((Article.content.isnot(None), 1), else_=0)).label('has_content'),
                func.sum(case((Article.published_at.isnot(None), 1), else_=0)).label('has_date')
            )
            .join(Article, Source.id == Article.source_id)
            .group_by(Source.name)
            .order_by(func.count(Article.id).desc())
        )

        print(f"\n{'Source':<30} {'Total':<10} {'Has Content':<15} {'Has Date':<12}")
        print("-"*80)

        for source_name, total, has_content, has_date in result:
            has_content = has_content or 0
            has_date = has_date or 0
            content_pct = (has_content / total * 100) if total > 0 else 0
            date_pct = (has_date / total * 100) if total > 0 else 0
            print(f"{source_name:<30} {total:<10} {has_content:<5} ({content_pct:>5.1f}%)  {has_date:<5} ({date_pct:>5.1f}%)")

        # 3. Date distribution
        print("\n" + "="*80)
        print("3. ARTICLE DATE DISTRIBUTION (Published At)")
        print("="*80)

        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        for label, date_from in [
            ("Today", today),
            ("Yesterday", yesterday),
            ("Last 7 days", week_ago),
            ("Last 30 days", month_ago)
        ]:
            count = await session.scalar(
                select(func.count(Article.id))
                .where(Article.published_at >= date_from)
            )
            print(f"  {label:<20}: {count} articles")

        # 4. Sample: Articles WITH category
        print("\n" + "="*80)
        print("4. SAMPLE: Articles WITH Category (limit 10)")
        print("="*80)

        result = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.category.isnot(None))
            .order_by(Article.scraped_at.desc())
            .limit(10)
        )

        for article, source_name in result:
            pub_date = article.published_at.strftime('%Y-%m-%d') if article.published_at else 'NO DATE'
            has_content = "✓" if article.content else "✗"
            print(f"\n  [{article.id}] {source_name}")
            print(f"      Title: {article.title[:70]}...")
            print(f"      Category: {article.category} | Date: {pub_date} | Content: {has_content}")
            if article.summary:
                print(f"      Summary: {article.summary[:100]}...")

        # 5. Sample: Articles WITHOUT category (ready for processing)
        print("\n" + "="*80)
        print("5. SAMPLE: Articles WITHOUT Category (ready for AI, limit 10)")
        print("="*80)

        result = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.processed == False)
            .where(Article.content.isnot(None))  # Must have content for AI
            .order_by(Article.scraped_at.desc())
            .limit(10)
        )

        ready_count = 0
        for article, source_name in result:
            ready_count += 1
            pub_date = article.published_at.strftime('%Y-%m-%d') if article.published_at else 'NO DATE'
            content_len = len(article.content) if article.content else 0
            print(f"\n  [{article.id}] {source_name}")
            print(f"      Title: {article.title[:70]}...")
            print(f"      Date: {pub_date} | Content length: {content_len} chars")

        if ready_count == 0:
            print("\n  ⚠️  No articles ready for processing (need content!)")

        # 6. Daily Summary Analysis - What would be included?
        print("\n" + "="*80)
        print("6. DAILY SUMMARY - What articles would be included?")
        print("="*80)

        # Symuluj co Daily Summary Generator robi
        target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        date_start = target_date
        date_end = target_date + timedelta(days=1)

        print(f"\nTarget date: {date_start.date()}")
        print(f"Looking for articles scraped between:")
        print(f"  From: {date_start}")
        print(f"  To:   {date_end}")

        # Articles that WOULD be included
        result = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.scraped_at >= date_start)
            .where(Article.scraped_at < date_end)
            .where(Article.processed == True)
            .order_by(Article.scraped_at.desc())
        )

        articles_for_summary = list(result)
        print(f"\n  📊 Articles matching criteria: {len(articles_for_summary)}")

        if articles_for_summary:
            print("\n  Articles that WOULD be in summary:")
            for article, source_name in articles_for_summary[:5]:
                pub_date = article.published_at.strftime('%Y-%m-%d') if article.published_at else 'NO DATE'
                scraped = article.scraped_at.strftime('%Y-%m-%d %H:%M')
                print(f"\n    [{article.id}] {source_name}")
                print(f"        Title: {article.title[:60]}...")
                print(f"        Published: {pub_date} | Scraped: {scraped}")
                print(f"        Category: {article.category}")
        else:
            print("\n  ⚠️  NO ARTICLES would be included in today's summary!")
            print("     Reasons:")
            print("     - Articles not scraped today, OR")
            print("     - Articles not processed by AI yet")

        # 7. Problem detection
        print("\n" + "="*80)
        print("7. PROBLEM DETECTION")
        print("="*80)

        total_articles = await session.scalar(select(func.count(Article.id)))
        processed_articles = await session.scalar(
            select(func.count(Article.id)).where(Article.processed == True)
        )
        with_content = await session.scalar(
            select(func.count(Article.id)).where(Article.content.isnot(None))
        )
        with_dates = await session.scalar(
            select(func.count(Article.id)).where(Article.published_at.isnot(None))
        )

        print("\n  Issues detected:")
        if processed_articles < 10:
            print(f"  ❌ Very few processed articles: {processed_articles}/{total_articles}")
            print("     → Run: python scripts/test_ai_pipeline.py (multiple times)")

        if with_content < total_articles * 0.7:
            print(f"  ⚠️  Many articles without content: {total_articles - with_content}/{total_articles}")
            print("     → Check scrapers, especially Klikaj.info")

        if with_dates < total_articles * 0.7:
            print(f"  ⚠️  Many articles without dates: {total_articles - with_dates}/{total_articles}")
            print("     → Fix date parsing in scrapers")

        # Recent articles check
        recent = await session.scalar(
            select(func.count(Article.id))
            .where(Article.published_at >= datetime.utcnow() - timedelta(days=2))
        )
        if recent < 5:
            print(f"  ⚠️  Few recent articles: {recent} from last 2 days")
            print("     → Scrapers may not be getting latest content")

        print("\n" + "="*80)

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
