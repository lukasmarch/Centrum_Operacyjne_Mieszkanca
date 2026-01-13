"""
Diagnose Summary Dates - Sprawdź jakie daty published_at wzięły udział w summary

Analizuje:
1. Jakie artykuły zostały użyte do Daily Summary dla 2026-01-11
2. Ich daty publikacji (published_at)
3. Czy są faktycznie z 11 stycznia czy starsze
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import Article, DailySummary, Source


async def main():
    print("="*80)
    print("DAILY SUMMARY - Date Analysis for 2026-01-11")
    print("="*80)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Znajdź Daily Summary dla 2026-01-11
        target_date = datetime(2026, 1, 11, 0, 0, 0)

        result = await session.execute(
            select(DailySummary).where(DailySummary.date == target_date)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            print("\n❌ No Daily Summary found for 2026-01-11")
            return

        print(f"\n✅ Found Daily Summary:")
        print(f"   Date: {summary.date}")
        print(f"   Headline: {summary.headline}")
        print(f"   Generated at: {summary.generated_at}")

        # 2. Odtwórz logikę Summary Generator - jakie artykuły POWINNY być użyte
        date_start = target_date
        date_end = target_date + timedelta(days=1)

        print(f"\n" + "="*80)
        print("SUMMARY GENERATOR LOGIC:")
        print("="*80)
        print(f"Looking for articles with:")
        print(f"  published_at >= {date_start}")
        print(f"  published_at < {date_end}")
        print(f"  processed = True")

        # 3. Znajdź artykuły które spełniają warunki
        articles_result = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.published_at >= date_start)
            .where(Article.published_at < date_end)
            .where(Article.processed == True)
            .order_by(Article.published_at.desc())
        )
        articles = list(articles_result)

        print(f"\n📊 Articles matching criteria: {len(articles)}")

        # Analiza źródeł
        if articles:
            sources_count = {}
            for article, source_name in articles:
                sources_count[source_name] = sources_count.get(source_name, 0) + 1

            print(f"\n" + "-"*80)
            print("SOURCES BREAKDOWN:")
            print("-"*80)
            print(f"\nTotal unique sources: {len(sources_count)}")
            print("\nArticles per source:")
            for source_name, count in sorted(sources_count.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(articles) * 100)
                print(f"  • {source_name}: {count} articles ({percentage:.1f}%)")

        if not articles:
            print("\n⚠️ NO ARTICLES found with published_at in range 2026-01-11!")
            print("   This means Summary Generator used DIFFERENT logic or WRONG dates")

            # Sprawdź czy przypadkiem nie użyło scraped_at
            print("\n🔍 Checking if scraped_at was used instead...")
            scraped_result = await session.execute(
                select(Article, Source.name)
                .join(Source, Article.source_id == Source.id)
                .where(Article.scraped_at >= date_start)
                .where(Article.scraped_at < date_end)
                .where(Article.processed == True)
                .order_by(Article.scraped_at.desc())
            )
            scraped_articles = list(scraped_result)

            if scraped_articles:
                print(f"\n⚠️ Found {len(scraped_articles)} articles by SCRAPED_AT (BUG!)")
                print("   This means the fix was NOT applied or code reverted!")

                for article, source_name in scraped_articles[:10]:
                    pub_date = article.published_at.strftime('%Y-%m-%d') if article.published_at else 'NO DATE'
                    scraped = article.scraped_at.strftime('%Y-%m-%d %H:%M')
                    print(f"\n  [{article.id}] {source_name}")
                    print(f"      Title: {article.title[:60]}...")
                    print(f"      Published: {pub_date} ⚠️ (OLD!)")
                    print(f"      Scraped: {scraped} (2026-01-11)")
                    print(f"      Category: {article.category}")

        else:
            print("\n✅ Articles used in summary (by published_at):\n")

            # Grupuj po dacie publikacji
            dates_count = {}
            for article, source_name in articles:
                pub_date = article.published_at.date()
                dates_count[pub_date] = dates_count.get(pub_date, 0) + 1

            print("Date distribution:")
            for date, count in sorted(dates_count.items()):
                print(f"  {date}: {count} articles")

            print("\n" + "-"*80)
            print("Article details:")
            print("-"*80)

            for article, source_name in articles:
                pub_date = article.published_at.strftime('%Y-%m-%d %H:%M') if article.published_at else 'NO DATE'
                scraped = article.scraped_at.strftime('%Y-%m-%d %H:%M')
                print(f"\n  [{article.id}] {source_name}")
                print(f"      Title: {article.title[:70]}...")
                print(f"      Published: {pub_date}")
                print(f"      Scraped: {scraped}")
                print(f"      Category: {article.category}")
                if article.summary:
                    print(f"      Summary: {article.summary[:100]}...")

        # 4. Sprawdź wszystkie przetworzone artykuły (bez filtra daty)
        print("\n" + "="*80)
        print("ALL PROCESSED ARTICLES (for comparison):")
        print("="*80)

        all_processed = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.processed == True)
            .order_by(Article.published_at.desc())
        )
        all_articles = list(all_processed)

        print(f"\nTotal processed: {len(all_articles)}")
        print("\nDate range of all processed articles:")

        if all_articles:
            oldest_pub = min((a.published_at for a, _ in all_articles if a.published_at), default=None)
            newest_pub = max((a.published_at for a, _ in all_articles if a.published_at), default=None)

            if oldest_pub and newest_pub:
                print(f"  Oldest published: {oldest_pub.strftime('%Y-%m-%d')}")
                print(f"  Newest published: {newest_pub.strftime('%Y-%m-%d')}")

        # 5. Analiza per źródło - dlaczego tylko Facebook-Syla?
        print("\n" + "="*80)
        print("SOURCES ANALYSIS - Why only Facebook-Syla today?")
        print("="*80)

        # Pobierz wszystkie źródła (aktywne i nieaktywne)
        sources_result = await session.execute(
            select(Source).order_by(Source.id)
        )
        all_sources = sources_result.scalars().all()

        print(f"\nTotal sources: {len(all_sources)}\n")

        for source in all_sources:
            # Wszystkie artykuły z tego źródła
            total_articles = await session.execute(
                select(Article)
                .where(Article.source_id == source.id)
            )
            total_count = len(list(total_articles.scalars()))

            # Przetworzone artykuły
            processed_articles = await session.execute(
                select(Article)
                .where(Article.source_id == source.id)
                .where(Article.processed == True)
            )
            processed_count = len(list(processed_articles.scalars()))

            # Artykuły z dzisiaj (published_at = 2026-01-11)
            today_articles = await session.execute(
                select(Article)
                .where(Article.source_id == source.id)
                .where(Article.published_at >= target_date)
                .where(Article.published_at < date_end)
            )
            today_count = len(list(today_articles.scalars()))

            # Najnowsza data publikacji
            newest_pub_result = await session.execute(
                select(Article.published_at)
                .where(Article.source_id == source.id)
                .where(Article.published_at.isnot(None))
                .order_by(Article.published_at.desc())
                .limit(1)
            )
            newest_pub = newest_pub_result.scalar_one_or_none()

            # Najnowsza data scrapowania
            newest_scraped_result = await session.execute(
                select(Article.scraped_at)
                .where(Article.source_id == source.id)
                .order_by(Article.scraped_at.desc())
                .limit(1)
            )
            newest_scraped = newest_scraped_result.scalar_one_or_none()

            status_icon = "✅" if source.status == "active" else "❌"
            print(f"📰 {source.name} (ID: {source.id}) {status_icon} [{source.status}]")
            print(f"   Total articles: {total_count}")
            print(f"   Processed: {processed_count} ({processed_count/total_count*100:.1f}%)" if total_count > 0 else "   Processed: 0")
            print(f"   Articles published TODAY (2026-01-11): {today_count} {'✅' if today_count > 0 else '❌'}")
            print(f"   Newest published_at: {newest_pub.strftime('%Y-%m-%d %H:%M') if newest_pub else 'NO DATE'}")
            print(f"   Last scraped: {newest_scraped.strftime('%Y-%m-%d %H:%M') if newest_scraped else 'NEVER'}")

            # Jeśli nie ma artykułów z dzisiaj, sprawdź przykładowe najnowsze
            if today_count == 0 and total_count > 0:
                recent_result = await session.execute(
                    select(Article)
                    .where(Article.source_id == source.id)
                    .order_by(Article.published_at.desc())
                    .limit(3)
                )
                recent_articles = list(recent_result.scalars())

                if recent_articles:
                    print(f"   📋 Latest 3 articles:")
                    for art in recent_articles:
                        pub = art.published_at.strftime('%Y-%m-%d') if art.published_at else 'NO DATE'
                        has_content = "✓" if art.content else "✗"
                        processed = "✓" if art.processed else "✗"
                        print(f"      [{pub}] {art.title[:50]}... (content:{has_content}, proc:{processed})")

            print()

        print("="*80)

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
