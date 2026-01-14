"""
Test Daily Summary Generator z nowymi źródłami RSS i zaktualizowanym promptem

Wygeneruj podsumowanie i zapisz do bazy danych.
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.database.connection import async_session
from src.database.schema import Article, DailySummary, Event, Weather
from src.ai.summary_generator import SummaryGenerator
from sqlmodel import select


async def generate_and_save_summary():
    """Wygeneruj i zapisz Daily Summary"""

    async with async_session() as session:
        print("=" * 80)
        print("DAILY SUMMARY TEST - Nowe źródła RSS + Zaktualizowany Prompt")
        print("=" * 80)

        # 1. Sprawdź dostępne artykuły
        print("\n📊 Sprawdzanie dostępnych artykułów...")

        # Ostatnie 24h
        yesterday = datetime.utcnow() - timedelta(days=1)
        result = await session.execute(
            select(Article)
            .where(Article.scraped_at >= yesterday)
            .where(Article.processed == True)
        )
        recent_articles = result.scalars().all()

        print(f"   Artykułów z ostatnich 24h (przetworzonych): {len(recent_articles)}")

        if len(recent_articles) < 5:
            print("   ⚠️  Za mało artykułów - użyję wszystkich przetworzonych")
            result = await session.execute(
                select(Article).where(Article.processed == True)
            )
            all_articles = result.scalars().all()
            print(f"   Wszystkich przetworzonych artykułów: {len(all_articles)}")

        # Pokaż breakdown per source
        from collections import Counter
        result = await session.execute(
            select(Article).where(Article.processed == True)
        )
        all_articles = result.scalars().all()

        source_counts = Counter(a.source_id for a in all_articles)
        category_counts = Counter(a.category for a in all_articles if a.category)

        print("\n   Artykuły per źródło:")
        # Get source names
        from src.database.schema import Source
        result_sources = await session.execute(select(Source))
        sources = {s.id: s.name for s in result_sources.scalars().all()}

        for source_id, count in source_counts.most_common():
            print(f"     - {sources.get(source_id, f'ID:{source_id}')}: {count} artykułów")

        print("\n   Artykuły per kategoria:")
        for category, count in category_counts.most_common():
            print(f"     - {category}: {count} artykułów")

        # 2. Wygeneruj podsumowanie
        print("\n" + "=" * 80)
        print("🤖 GENEROWANIE PODSUMOWANIA AI...")
        print("=" * 80)

        generator = SummaryGenerator()

        # Użyj dzisiejszej daty
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            summary = await generator.generate_daily_summary(session, target_date=today)

            if summary:
                print("\n✅ Podsumowanie wygenerowane pomyślnie!")
                print("\n" + "=" * 80)
                print("WYNIK DAILY SUMMARY:")
                print("=" * 80)

                print(f"\n📅 Data: {summary.date.date()}")
                print(f"\n📰 HEADLINE:")
                print(f'   "{summary.headline}"')

                print(f"\n⭐ HIGHLIGHTS ({len(summary.content.get('highlights', []))}):")
                for i, highlight in enumerate(summary.content.get('highlights', []), 1):
                    print(f"   {i}. {highlight}")

                print(f"\n📋 PODSUMOWANIA PER KATEGORIA:")
                summaries = summary.content.get('summaries_by_category', {})
                for category, text in summaries.items():
                    print(f"\n   [{category}]")
                    print(f"   {text}")

                print(f"\n🎉 NADCHODZĄCE WYDARZENIA ({len(summary.content.get('upcoming_events', []))}):")
                for event in summary.content.get('upcoming_events', []):
                    print(f"   - {event.get('title')} ({event.get('date')})")

                print(f"\n🌤️  POGODA:")
                weather = summary.content.get('weather_summary', {})
                print(f"   {weather}")

                print(f"\n📊 STATYSTYKI:")
                stats = summary.content.get('stats', {})
                print(f"   - Total articles: {stats.get('total_articles', 0)}")
                print(f"   - Categories: {stats.get('categories_count', 0)}")
                print(f"   - Events: {stats.get('events_count', 0)}")

                print("\n" + "=" * 80)
                print("✅ PODSUMOWANIE ZAPISANE DO BAZY (ID: {})".format(summary.id))
                print("=" * 80)

                return summary
            else:
                print("\n❌ Podsumowanie już istnieje dla tej daty lub brak danych")

                # Sprawdź istniejące
                result = await session.execute(
                    select(DailySummary).where(DailySummary.date == today)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    print(f"\n📝 Istniejące podsumowanie (ID: {existing.id}):")
                    print(f'   Headline: "{existing.headline}"')
                    print(f"   Generated: {existing.generated_at}")

                return existing

        except Exception as e:
            print(f"\n❌ Błąd podczas generowania: {e}")
            import traceback
            traceback.print_exc()
            return None


if __name__ == "__main__":
    asyncio.run(generate_and_save_summary())
