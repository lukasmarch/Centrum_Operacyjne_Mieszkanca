import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.database.connection import async_session
from sqlalchemy import text

async def check():
    async with async_session() as s:
        r = await s.execute(text("""
            SELECT COUNT(*), s.name
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE a.embedded = False
              AND a.processed = True
              AND a.scraped_at >= now() - INTERVAL '24 hours'
            GROUP BY s.name
        """))
        rows = r.all()
        if rows:
            for row in rows:
                print(f"  {row[1]}: {row[0]} artykułów")
        else:
            print("  Brak artykułów z ostatnich 24h gotowych do osadzenia")

asyncio.run(check())
