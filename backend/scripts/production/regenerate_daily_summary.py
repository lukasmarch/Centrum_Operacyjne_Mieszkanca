"""
Usuń stare podsumowanie i wygeneruj nowe z zaktualizowanym promptem
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


async def regenerate_summary():
    """Usuń stare i wygeneruj nowe"""

    async with async_session() as session:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        print("=" * 80)
        print("REGENERACJA DAILY SUMMARY")
        print("=" * 80)

        # 1. Usuń istniejące
        print(f"\n🗑️  Usuwanie starego podsumowania dla {today.date()}...")
        result = await session.execute(
            select(DailySummary).where(DailySummary.date == today)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"   Znaleziono: ID {existing.id}")
            print(f'   Stary headline: "{existing.headline}"')
            await session.delete(existing)
            await session.commit()
            print("   ✅ Usunięto")
        else:
            print("   ℹ️  Brak starego podsumowania")

        # 2. Pokaż statystyki artykułów
        print(f"\n📊 Artykuły dostępne do podsumowania:")

        result = await session.execute(
            select(Article).where(Article.processed == True)
        )
        articles = result.scalars().all()

        from collections import Counter
        category_counts = Counter(a.category for a in articles if a.category)

        print(f"   Łącznie przetworzonych: {len(articles)}")
        print(f"\n   Per kategoria:")
        for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"     - {category}: {count} ({count/len(articles)*100:.1f}%)")

        # 3. Wygeneruj nowe
        print("\n" + "=" * 80)
        print("🤖 GENEROWANIE NOWEGO PODSUMOWANIA...")
        print("   (z zaktualizowanym promptem AI - priorytet: PILNE i PRAKTYCZNE)")
        print("=" * 80)

        generator = SummaryGenerator()
        summary = await generator.generate_daily_summary(session, target_date=today)

        if summary:
            print("\n✅ NOWE PODSUMOWANIE WYGENEROWANE!")
            print("\n" + "=" * 80)
            print("WYNIK:")
            print("=" * 80)

            print(f"\n📰 HEADLINE:")
            print(f'   "{summary.headline}"')

            highlights = summary.content.get('highlights', [])
            print(f"\n⭐ HIGHLIGHTS ({len(highlights)}):")
            for i, highlight in enumerate(highlights, 1):
                print(f"   {i}. {highlight}")

            print(f"\n📋 PODSUMOWANIA PER KATEGORIA:")
            summaries = summary.content.get('summaries_by_category', {})
            for category, text in summaries.items():
                print(f"\n   [{category}]")
                print(f"   {text}")

            events = summary.content.get('upcoming_events', [])
            print(f"\n🎉 WYDARZENIA ({len(events)}):")
            for event in events[:3]:
                if isinstance(event, dict):
                    print(f"   - {event.get('title')} ({event.get('date')})")
                else:
                    print(f"   - {event}")

            weather = summary.content.get('weather_summary')
            if weather:
                print(f"\n🌤️  POGODA:")
                print(f"   {weather}")

            stats = summary.content.get('stats', {})
            print(f"\n📊 STATYSTYKI:")
            print(f"   - Artykuły: {stats.get('total_articles', 0)}")
            print(f"   - Kategorie: {stats.get('categories_count', 0)}")
            print(f"   - Wydarzenia: {stats.get('events_count', 0)}")

            print("\n" + "=" * 80)
            print(f"✅ ZAPISANO DO BAZY (ID: {summary.id})")
            print("=" * 80)

            # Porównanie z poprzednim
            if existing:
                print("\n📊 PORÓWNANIE:")
                print(f"   Stary headline: \"{existing.headline}\"")
                print(f"   Nowy headline:  \"{summary.headline}\"")

                old_highlights = existing.content.get('highlights', [])
                new_highlights = summary.content.get('highlights', [])
                print(f"\n   Stare highlights: {len(old_highlights)}")
                print(f"   Nowe highlights:  {len(new_highlights)}")

                old_categories = set(existing.content.get('summaries_by_category', {}).keys())
                new_categories = set(summary.content.get('summaries_by_category', {}).keys())
                print(f"\n   Stare kategorie: {', '.join(sorted(old_categories))}")
                print(f"   Nowe kategorie:  {', '.join(sorted(new_categories))}")

            return summary
        else:
            print("\n❌ Nie udało się wygenerować podsumowania")
            return None


if __name__ == "__main__":
    asyncio.run(regenerate_summary())
