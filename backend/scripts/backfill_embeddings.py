"""
Backfill embeddingów — jednorazowy skrypt naprawczy (2026-07).

Problem: ~2600 artykułów ma embedded=True jako historyczny marker "dontemb",
ale ZERO chunków w document_embeddings — są niewidoczne dla RAG.
Do tego artykuły processed=True, embedded=False spoza dnia scrapowania
(embedding_job osadza tylko z bieżącego dnia).

Skrypt osadza wszystkie artykuły, które NIE mają żadnego chunka w
document_embeddings. Wznawialny — przy przerwaniu można uruchomić ponownie.

Uruchomienie (w kontenerze backendu na prod):
  docker compose -f docker-compose.prod.yml exec -T backend \
      python -u -m scripts.backfill_embeddings

Lokalnie: cd backend && python -u -m scripts.backfill_embeddings
"""
import asyncio
import sys
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.ai.embeddings import embedding_service
from src.ai.chunker import chunker
from src.utils.logger import setup_logger

logger = setup_logger("BackfillEmbeddings")

BATCH_SIZE = 50          # artykułów na jedną transakcję
SLEEP_BETWEEN_BATCHES = 1.0  # sekundy — oddech dla API OpenAI


async def _fetch_missing_batch(session: AsyncSession, limit: int) -> list[dict]:
    """Artykuły bez ŻADNEGO chunka w document_embeddings (article lub bip)."""
    result = await session.execute(
        text("""
            SELECT a.id, a.title, a.content, a.summary, a.url,
                   a.published_at, a.category, s.name AS source_name
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            WHERE a.processed = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM document_embeddings de
                  WHERE de.source_id = a.id
                    AND de.source_type IN ('article', 'bip')
              )
            ORDER BY a.published_at DESC NULLS LAST
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return [dict(row._mapping) for row in result]


async def _embed_one(session: AsyncSession, art: dict) -> int:
    """Chunkuje i osadza jeden artykuł. Zwraca liczbę chunków."""
    source_name = art["source_name"] or ""
    is_bip = "BIP" in source_name
    source_type = "bip" if is_bip else "article"

    if is_bip:
        chunks = chunker.chunk_bip_document(
            title=art["title"], content=art["content"], doc_type="dokument"
        )
    else:
        chunks = chunker.chunk_article(
            title=art["title"],
            content=art["content"],
            summary=art["summary"],
            source_name=source_name,
            category=art["category"] or "",
        )

    texts = [c["text"] for c in chunks]
    embeddings = await embedding_service.embed_batch(texts)

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        metadata = {
            **chunk["metadata"],
            "title": art["title"],
            "url": art["url"],
            "published_at": art["published_at"].isoformat() if art["published_at"] else "",
            "source_name": source_name,
        }
        await embedding_service.store_embedding(
            session=session,
            source_type=source_type,
            source_id=art["id"],
            chunk_index=i,
            chunk_text=chunk["text"],
            embedding=embedding,
            metadata=metadata,
        )

    await session.execute(
        text("UPDATE articles SET embedded = TRUE WHERE id = :id"), {"id": art["id"]}
    )
    return len(chunks)


async def main():
    start = datetime.utcnow()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_articles = 0
    total_chunks = 0
    failed: list[int] = []

    async with async_session() as session:
        count_result = await session.execute(
            text("""
                SELECT COUNT(*) FROM articles a
                WHERE a.processed = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM document_embeddings de
                      WHERE de.source_id = a.id AND de.source_type IN ('article', 'bip')
                  )
            """)
        )
        remaining = count_result.scalar()
        logger.info(f"Do osadzenia: {remaining} artykułów")

    while True:
        async with async_session() as session:
            batch = await _fetch_missing_batch(session, limit=BATCH_SIZE + len(failed))
            # Pomijaj artykuły, które już zawiodły w tej sesji (inaczej pętla nieskończona)
            batch = [a for a in batch if a["id"] not in failed]
            if not batch:
                break

            for art in batch:
                try:
                    n = await _embed_one(session, art)
                    total_articles += 1
                    total_chunks += n
                except Exception as e:
                    failed.append(art["id"])
                    logger.error(f"Artykuł {art['id']} pominięty: {e}")

            await session.commit()
            logger.info(f"Postęp: {total_articles} artykułów, {total_chunks} chunków")

        await asyncio.sleep(SLEEP_BETWEEN_BATCHES)

    await engine.dispose()
    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(
        f"GOTOWE: {total_articles} artykułów, {total_chunks} chunków, "
        f"{len(failed)} błędów, {elapsed:.0f}s"
    )
    if failed:
        logger.warning(f"Pominięte ID: {failed}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
