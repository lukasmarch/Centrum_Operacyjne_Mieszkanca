"""
Skrypt do sprawdzania zawartości bazy danych
Użycie: python scripts/check_database.py [--table TABLE_NAME] [--limit N]
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from src.database import Source, Article, Event, Weather
from src.config import settings


async def check_sources(session: AsyncSession, limit: int = 100):
    """Sprawdź źródła w bazie"""
    print("\n" + "="*80)
    print("ŹRÓDŁA (SOURCES)")
    print("="*80)

    result = await session.execute(select(Source).limit(limit))
    sources = result.scalars().all()

    if not sources:
        print("❌ Brak źródeł w bazie")
        return

    print(f"✓ Znaleziono {len(sources)} źródeł:\n")

    for source in sources:
        print(f"ID: {source.id}")
        print(f"Nazwa: {source.name}")
        print(f"Typ: {source.type}")
        print(f"URL: {source.url}")
        print(f"Status: {source.status}")
        print(f"Ostatni scraping: {source.last_scraped}")
        print(f"Utworzony: {source.created_at}")
        print("-" * 80)


async def check_articles(session: AsyncSession, limit: int = 10):
    """Sprawdź artykuły w bazie"""
    print("\n" + "="*80)
    print("ARTYKUŁY (ARTICLES)")
    print("="*80)

    # Pobierz artykuły z nazwą źródła
    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .order_by(Article.scraped_at.desc())
        .limit(limit)
    )

    articles_data = result.all()

    if not articles_data:
        print("❌ Brak artykułów w bazie")
        return

    # Statystyki
    total_result = await session.execute(select(Article))
    total_articles = len(total_result.scalars().all())

    print(f"✓ Łącznie artykułów w bazie: {total_articles}")
    print(f"✓ Pokazuję {len(articles_data)} najnowszych:\n")

    for article, source_name in articles_data:
        print(f"ID: {article.id}")
        print(f"Źródło: {source_name} (ID: {article.source_id})")
        print(f"Tytuł: {article.title}")
        print(f"URL: {article.url}")
        print(f"External ID: {article.external_id}")

        # Zawartość
        print(f"Content: {'✓ ' + str(len(article.content)) + ' znaków' if article.content else '❌ NULL'}")
        print(f"Summary: {'✓ ' + str(len(article.summary)) + ' znaków' if article.summary else '❌ NULL'}")

        # Obrazek
        print(f"Image URL: {'✓ ' + article.image_url[:60] + '...' if article.image_url else '❌ NULL'}")

        # Metadane
        print(f"Kategoria: {article.category or 'NULL'}")
        print(f"Tagi: {article.tags or 'NULL'}")
        print(f"Autor: {article.author or 'NULL'}")
        print(f"Opublikowany: {article.published_at or 'NULL'}")
        print(f"Zescrapowany: {article.scraped_at}")
        print(f"Przetworzony: {'✓' if article.processed else '❌'}")

        # Podgląd treści jeśli istnieje
        if article.content:
            preview = article.content[:200].replace('\n', ' ')
            print(f"Podgląd: {preview}...")
        if article.summary:
            preview = article.summary[:200].replace('\n', ' ')
            print(f"Summary: {preview}...")

        print("-" * 80)


async def check_events(session: AsyncSession, limit: int = 10):
    """Sprawdź wydarzenia w bazie"""
    print("\n" + "="*80)
    print("WYDARZENIA (EVENTS)")
    print("="*80)

    result = await session.execute(
        select(Event).order_by(Event.event_date.desc()).limit(limit)
    )
    events = result.scalars().all()

    if not events:
        print("❌ Brak wydarzeń w bazie")
        return

    total_result = await session.execute(select(Event))
    total_events = len(total_result.scalars().all())

    print(f"✓ Łącznie wydarzeń w bazie: {total_events}")
    print(f"✓ Pokazuję {len(events)} najnowszych:\n")

    for event in events:
        print(f"ID: {event.id}")
        print(f"Tytuł: {event.title}")
        print(f"Data wydarzenia: {event.event_date}")
        print(f"Lokalizacja: {event.location or 'NULL'}")
        print(f"Kategoria: {event.category or 'NULL'}")
        print(f"Wyróżnione: {'✓' if event.is_featured else '❌'}")
        print("-" * 80)


async def check_weather(session: AsyncSession, limit: int = 10):
    """Sprawdź dane pogodowe w bazie"""
    print("\n" + "="*80)
    print("POGODA (WEATHER)")
    print("="*80)

    result = await session.execute(
        select(Weather).order_by(Weather.fetched_at.desc()).limit(limit)
    )
    weather_data = result.scalars().all()

    if not weather_data:
        print("❌ Brak danych pogodowych w bazie")
        return

    total_result = await session.execute(select(Weather))
    total_weather = len(total_result.scalars().all())

    print(f"✓ Łącznie wpisów pogodowych: {total_weather}")
    print(f"✓ Pokazuję {len(weather_data)} najnowszych:\n")

    for weather in weather_data:
        print(f"ID: {weather.id}")
        print(f"Lokalizacja: {weather.location}")
        print(f"Temperatura: {weather.temperature}°C (odczuwalna: {weather.feels_like}°C)")
        print(f"Opis: {weather.description} ({weather.main})")
        print(f"Wilgotność: {weather.humidity}% | Ciśnienie: {weather.pressure} hPa")
        print(f"Wiatr: {weather.wind_speed} m/s")
        print(f"Zachmurzenie: {weather.clouds}%")
        print(f"Widoczność: {weather.visibility}m" if weather.visibility else "Widoczność: NULL")
        print(f"Deszcz 1h: {weather.rain_1h}mm" if weather.rain_1h else "")
        print(f"Wschód słońca: {weather.sunrise}")
        print(f"Zachód słońca: {weather.sunset}")
        print(f"Aktualny: {'✓' if weather.is_current else '❌'}")
        print(f"Pobrano: {weather.fetched_at}")
        print("-" * 80)


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Sprawdź zawartość bazy danych')
    parser.add_argument('--table', choices=['sources', 'articles', 'events', 'weather', 'all'],
                       default='all', help='Która tabela do sprawdzenia')
    parser.add_argument('--limit', type=int, default=10,
                       help='Limit wyników (domyślnie 10)')

    args = parser.parse_args()

    # Połącz z bazą
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("\n" + "="*80)
    print(f"SPRAWDZANIE BAZY DANYCH - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print(f"Database URL: {settings.DATABASE_URL.split('@')[1]}")  # Hide password

    async with async_session() as session:
        if args.table == 'all' or args.table == 'sources':
            await check_sources(session, args.limit)

        if args.table == 'all' or args.table == 'articles':
            await check_articles(session, args.limit)

        if args.table == 'all' or args.table == 'events':
            await check_events(session, args.limit)

        if args.table == 'all' or args.table == 'weather':
            await check_weather(session, args.limit)

    print("\n" + "="*80)
    print("KONIEC SPRAWDZANIA")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
