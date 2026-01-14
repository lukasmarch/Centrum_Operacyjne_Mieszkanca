"""
Wyświetl szczegóły najnowszego Daily Summary
"""
import sys
import asyncio
from pathlib import Path
import json

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.database.connection import async_session
from src.database.schema import DailySummary
from sqlmodel import select


async def view_latest_summary():
    async with async_session() as session:
        # Pobierz najnowsze
        result = await session.execute(
            select(DailySummary).order_by(DailySummary.date.desc()).limit(1)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            print("❌ Brak podsumowań w bazie")
            return

        print("=" * 80)
        print("NAJNOWSZE DAILY SUMMARY")
        print("=" * 80)

        print(f"\n📅 Data: {summary.date.date()}")
        print(f"🕐 Wygenerowano: {summary.generated_at}")
        print(f"🆔 ID: {summary.id}")

        print(f"\n📰 HEADLINE:")
        print(f'"{summary.headline}"')

        content = summary.content

        print(f"\n⭐ HIGHLIGHTS ({len(content.get('highlights', []))}):")
        for i, highlight in enumerate(content.get('highlights', []), 1):
            print(f"  {i}. {highlight}")

        summaries = content.get('summaries_by_category', {})
        print(f"\n📋 PODSUMOWANIA PER KATEGORIA ({len(summaries)}):")
        for category, text in summaries.items():
            print(f"\n  [{category.upper()}]")
            print(f"  {text}")

        events = content.get('upcoming_events', [])
        print(f"\n🎉 NADCHODZĄCE WYDARZENIA ({len(events)}):")
        for event in events[:5]:
            if isinstance(event, dict):
                print(f"  - {event.get('title')} ({event.get('date')})")
                if event.get('location'):
                    print(f"    Miejsce: {event.get('location')}")
            else:
                print(f"  - {event}")

        weather = content.get('weather_summary')
        if weather:
            print(f"\n🌤️  POGODA:")
            if isinstance(weather, dict):
                print(f"  Temperatura: {weather.get('temperature', 'N/A')}°C")
                print(f"  Warunki: {weather.get('conditions', 'N/A')}")
                print(f"  Opis: {weather.get('description', 'N/A')}")
            else:
                print(f"  {weather}")

        stats = content.get('stats', {})
        print(f"\n📊 STATYSTYKI:")
        print(f"  - Artykuły: {stats.get('total_articles', 0)}")
        print(f"  - Kategorie: {stats.get('categories_count', 0)}")
        print(f"  - Wydarzenia: {stats.get('events_count', 0)}")

        print("\n" + "=" * 80)
        print("PEŁNA STRUKTURA JSON:")
        print("=" * 80)
        print(json.dumps(content, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(view_latest_summary())
