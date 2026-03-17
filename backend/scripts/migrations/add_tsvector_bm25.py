"""
Migration: Add tsvector column + GIN index + trigger to document_embeddings for BM25 search.
Idempotent — safe to run multiple times.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.database.connection import async_session
from sqlalchemy import text


MIGRATION_STEPS = [
    "CREATE EXTENSION IF NOT EXISTS unaccent",
    "ALTER TABLE document_embeddings ADD COLUMN IF NOT EXISTS search_vector tsvector",
    "CREATE INDEX IF NOT EXISTS idx_embeddings_fts ON document_embeddings USING GIN (search_vector)",
    """CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('simple', unaccent(NEW.chunk_text));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS tsvector_update ON document_embeddings",
    """CREATE TRIGGER tsvector_update
BEFORE INSERT OR UPDATE OF chunk_text
ON document_embeddings
FOR EACH ROW EXECUTE FUNCTION update_search_vector()""",
]

BACKFILL_SQL = """
UPDATE document_embeddings
SET search_vector = to_tsvector('simple', unaccent(chunk_text))
WHERE search_vector IS NULL
"""


async def run():
    async with async_session() as session:
        print("Running BM25/tsvector migration...")
        for step in MIGRATION_STEPS:
            await session.execute(text(step))
        await session.commit()
        print("Schema updated. Backfilling search_vector for existing rows...")

        result = await session.execute(
            text("SELECT COUNT(*) FROM document_embeddings WHERE search_vector IS NULL")
        )
        null_count = result.scalar()
        print(f"  Rows to backfill: {null_count}")

        if null_count > 0:
            await session.execute(text(BACKFILL_SQL))
            await session.commit()
            print(f"  Backfilled {null_count} rows.")

        result = await session.execute(
            text("SELECT COUNT(*) FROM document_embeddings WHERE search_vector IS NOT NULL")
        )
        total = result.scalar()
        print(f"  Total rows with search_vector: {total}")
        print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run())
