"""
Quick script to check current database status
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.database.connection import sync_engine
from sqlmodel import Session, select
from src.database.schema import Source, Article, DailySummary

def main():
    session = Session(sync_engine)

    # Sources
    print("=" * 60)
    print("SOURCES")
    print("=" * 60)
    sources = session.exec(select(Source)).all()
    for s in sources:
        print(f"  [{s.id}] {s.name}")
        print(f"      Type: {s.type}, Status: {s.status}")
        print(f"      Last scraped: {s.last_scraped}")
        print()

    # Articles
    print("=" * 60)
    print("ARTICLES")
    print("=" * 60)
    articles = session.exec(select(Article)).all()
    processed = [a for a in articles if a.processed]

    print(f"  Total articles: {len(articles)}")
    print(f"  Processed: {len(processed)} ({len(processed)/len(articles)*100:.1f}%)")
    print()

    # Categories
    categories = {}
    for a in processed:
        if a.category:
            categories[a.category] = categories.get(a.category, 0) + 1

    print("  Categories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    - {cat}: {count} articles")
    print()

    # Sources with article counts
    print("  Articles by source:")
    source_counts = {}
    for a in articles:
        source_counts[a.source_id] = source_counts.get(a.source_id, 0) + 1

    for source_id, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        source = next((s for s in sources if s.id == source_id), None)
        if source:
            print(f"    - {source.name}: {count} articles")
    print()

    # Daily Summaries
    print("=" * 60)
    print("DAILY SUMMARIES")
    print("=" * 60)
    summaries = session.exec(select(DailySummary)).all()
    print(f"  Total summaries: {len(summaries)}")
    if summaries:
        latest = summaries[-1]
        print(f"  Latest: {latest.date.date()}")
        print(f"  Headline: {latest.headline}")
    print()

    session.close()

if __name__ == "__main__":
    main()
