"""
Verify Data Quality - Sprawdź pobrane artykuły

Weryfikuje:
- Ilość artykułów per źródło
- Daty publikacji (czy są najnowsze)
- Przykłady artykułów
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import Article, Source


async def main():
    print("="*80)
    print("DATA QUALITY VERIFICATION")
    print("="*80)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Total articles
        total = await session.scalar(select(func.count(Article.id)))
        print(f"\n📊 Total Articles: {total}")

        # 2. Articles per source
        print("\n" + "-"*80)
        print("ARTICLES PER SOURCE:")
        print("-"*80)

        result = await session.execute(
            select(Source.name, func.count(Article.id))
            .join(Article, Source.id == Article.source_id)
            .group_by(Source.name)
            .order_by(func.count(Article.id).desc())
        )

        for source_name, count in result:
            print(f"  • {source_name}: {count} articles")

        # 3. Date range
        print("\n" + "-"*80)
        print("DATE RANGE:")
        print("-"*80)

        oldest = await session.scalar(
            select(func.min(Article.published_at))
            .where(Article.published_at.isnot(None))
        )
        newest = await session.scalar(
            select(func.max(Article.published_at))
            .where(Article.published_at.isnot(None))
        )
        scraped_newest = await session.scalar(
            select(func.max(Article.scraped_at))
        )

        print(f"  Oldest published: {oldest.date() if oldest else 'N/A'}")
        print(f"  Newest published: {newest.date() if newest else 'N/A'}")
        print(f"  Last scraped: {scraped_newest if scraped_newest else 'N/A'}")

        # 4. Sample articles from each source
        print("\n" + "-"*80)
        print("SAMPLE ARTICLES (3 newest per source):")
        print("-"*80)

        sources_result = await session.execute(select(Source))
        sources = sources_result.scalars().all()

        for source in sources:
            articles_result = await session.execute(
                select(Article)
                .where(Article.source_id == source.id)
                .order_by(Article.scraped_at.desc())
                .limit(3)
            )
            articles = articles_result.scalars().all()

            if articles:
                print(f"\n  📰 {source.name} ({len(articles)} shown):")
                for i, art in enumerate(articles, 1):
                    pub_date = art.published_at.strftime('%Y-%m-%d') if art.published_at else 'No date'
                    print(f"     {i}. [{pub_date}] {art.title[:70]}...")
                    if art.content:
                        print(f"        Content: {art.content[:100]}...")

        # 5. Quality checks
        print("\n" + "-"*80)
        print("QUALITY CHECKS:")
        print("-"*80)

        no_content = await session.scalar(
            select(func.count(Article.id))
            .where(Article.content.is_(None))
        )
        no_date = await session.scalar(
            select(func.count(Article.id))
            .where(Article.published_at.is_(None))
        )
        no_title = await session.scalar(
            select(func.count(Article.id))
            .where(Article.title.is_(None))
        )

        print(f"  Articles without content: {no_content} ({no_content/total*100:.1f}%)")
        print(f"  Articles without date: {no_date} ({no_date/total*100:.1f}%)")
        print(f"  Articles without title: {no_title}")

        # Status
        if no_title == 0 and no_content < total * 0.3:
            print("\n  ✅ Data quality: GOOD")
        elif no_content < total * 0.5:
            print("\n  ⚠️  Data quality: ACCEPTABLE (some missing content)")
        else:
            print("\n  ❌ Data quality: POOR (too much missing data)")

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
