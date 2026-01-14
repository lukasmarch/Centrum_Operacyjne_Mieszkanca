"""
Przetworz wszystkie nieprzetworzone artykuły przez AI
"""
import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.database.connection import async_session
from src.database.schema import Article
from src.ai.article_processor import ArticleProcessor
from src.ai.event_extractor import EventExtractor
from sqlmodel import select


async def process_all_unprocessed():
    """Przetworz wszystkie nieprzetworzone artykuły"""

    async with async_session() as session:
        print("=" * 80)
        print("AI PROCESSING - WSZYSTKIE NIEPRZETWORZONE ARTYKUŁY")
        print("=" * 80)

        # 1. Pobierz nieprzetworzone
        result = await session.execute(
            select(Article).where(Article.processed == False)
        )
        unprocessed = result.scalars().all()

        print(f"\n📊 Nieprzetworzone artykuły: {len(unprocessed)}")

        if len(unprocessed) == 0:
            print("✅ Wszystkie artykuły już przetworzone!")
            return

        # Pokaż breakdown per source
        from collections import Counter
        from src.database.schema import Source

        source_counts = Counter(a.source_id for a in unprocessed)
        result_sources = await session.execute(select(Source))
        sources = {s.id: s.name for s in result_sources.scalars().all()}

        print("\nPer źródło:")
        for source_id, count in source_counts.most_common():
            print(f"  - {sources.get(source_id, f'ID:{source_id}')}: {count} artykułów")

        # 2. Inicjalizuj processory
        print("\n" + "=" * 80)
        print("🤖 URUCHAMIANIE AI PROCESSING...")
        print("=" * 80)

        article_processor = ArticleProcessor()
        event_extractor = EventExtractor()

        # 3. Przetwarzaj w batchach (20 na raz)
        batch_size = 20
        processed_count = 0
        failed_count = 0
        events_found = 0

        for i in range(0, len(unprocessed), batch_size):
            batch = unprocessed[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(unprocessed) + batch_size - 1) // batch_size

            print(f"\n📦 Batch {batch_num}/{total_batches} ({len(batch)} artykułów)...")

            for article in batch:
                try:
                    # Kategoryzacja
                    result = await article_processor.process_article(article, session)

                    if result:
                        # result jest już zaktualizowanym article z bazy
                        # Ekstrakcja wydarzeń
                        event = await event_extractor.extract_event(result, session)
                        if event:
                            events_found += 1

                        processed_count += 1

                        # Pokaż postęp co 10 artykułów
                        if processed_count % 10 == 0:
                            print(f"   ✓ {processed_count}/{len(unprocessed)} przetworzonych...")

                    else:
                        # Artykuł nie ma treści (pominięty)
                        print(f"   ⚠️  Skipped article {article.id} (no content)")
                        failed_count += 1

                except Exception as e:
                    print(f"   ⚠️  Error processing article {article.id}: {str(e)[:100]}")
                    failed_count += 1

            # Commit po każdym batchu
            await session.commit()
            print(f"   ✅ Batch {batch_num} zapisany do bazy")

            # Pauza między batchami (rate limiting OpenAI API)
            if i + batch_size < len(unprocessed):
                print("   ⏱️  Pauza 5s (rate limiting)...")
                await asyncio.sleep(5)

        # 4. Podsumowanie
        print("\n" + "=" * 80)
        print("✅ AI PROCESSING ZAKOŃCZONY!")
        print("=" * 80)

        print(f"\n📊 WYNIKI:")
        print(f"  - Przetworzonych: {processed_count}/{len(unprocessed)}")
        print(f"  - Błędów: {failed_count}")
        print(f"  - Znalezionych wydarzeń: {events_found}")

        # Sprawdź końcowe statystyki
        result = await session.execute(select(Article))
        all_articles = result.scalars().all()
        processed_total = sum(1 for a in all_articles if a.processed)

        print(f"\n📈 STATYSTYKI CAŁKOWITE:")
        print(f"  - Artykuły w bazie: {len(all_articles)}")
        print(f"  - Przetworzone: {processed_total} ({processed_total/len(all_articles)*100:.1f}%)")
        print(f"  - Nieprzetworzone: {len(all_articles) - processed_total}")

        # Breakdown per kategoria
        category_counts = Counter(a.category for a in all_articles if a.category)
        print(f"\n📋 PER KATEGORIA:")
        for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            print(f"  - {category}: {count} ({count/processed_total*100:.1f}%)")


if __name__ == "__main__":
    asyncio.run(process_all_unprocessed())
