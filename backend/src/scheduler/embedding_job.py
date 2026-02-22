"""
Embedding job - runs daily at 6:20 AM (after AI processing, before summary)
Generates embeddings for new/unembedded articles and events
"""
import asyncio
from datetime import datetime, timedelta
from sqlmodel import select
from sqlalchemy import text

from src.database.connection import async_session
from src.database.schema import Article, Event, Source
from src.ai.embeddings import embedding_service
from src.ai.chunker import chunker
from src.utils.logger import setup_logger

logger = setup_logger("EmbeddingJob")

MAX_BATCH_SIZE = 50  # Max articles per run


async def _embed_articles(session):
    """Embed unembedded articles"""
    # Get articles that haven't been embedded yet
    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .where(Article.embedded == False)
        .where(Article.processed == True)
        .order_by(Article.published_at.desc().nulls_last())
        .limit(MAX_BATCH_SIZE)
    )

    articles = result.all()
    if not articles:
        logger.info("No new articles to embed")
        return 0

    logger.info(f"Embedding {len(articles)} articles...")
    embedded_count = 0

    for article, source_name in articles:
        try:
            # Chunk the article
            chunks = chunker.chunk_article(
                title=article.title,
                content=article.content,
                summary=article.summary,
                source_name=source_name,
                category=article.category or ""
            )

            # Generate embeddings for all chunks
            texts = [c["text"] for c in chunks]
            embeddings = await embedding_service.embed_batch(texts)

            # Store each chunk with its embedding
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                metadata = {
                    **chunk["metadata"],
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at.isoformat() if article.published_at else ""
                }

                await embedding_service.store_embedding(
                    session=session,
                    source_type="article",
                    source_id=article.id,
                    chunk_index=i,
                    chunk_text=chunk["text"],
                    embedding=embedding,
                    metadata=metadata
                )

            # Mark article as embedded
            article.embedded = True
            session.add(article)
            embedded_count += 1

        except Exception as e:
            logger.error(f"Failed to embed article {article.id}: {e}")

    await session.commit()
    return embedded_count


async def _embed_events(session):
    """Embed recent events"""
    cutoff = datetime.utcnow() - timedelta(days=30)

    result = await session.execute(
        select(Event)
        .where(Event.event_date >= cutoff)
        .limit(MAX_BATCH_SIZE)
    )
    events = result.scalars().all()

    if not events:
        return 0

    embedded_count = 0
    for event in events:
        try:
            chunks = chunker.chunk_event(
                title=event.title,
                description=event.description,
                location=event.location,
                date=event.event_date.isoformat() if event.event_date else "",
                category=event.category or ""
            )

            texts = [c["text"] for c in chunks]
            embeddings = await embedding_service.embed_batch(texts)

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                metadata = {
                    **chunk["metadata"],
                    "title": event.title,
                    "event_date": event.event_date.isoformat() if event.event_date else ""
                }

                await embedding_service.store_embedding(
                    session=session,
                    source_type="event",
                    source_id=event.id,
                    chunk_index=i,
                    chunk_text=chunk["text"],
                    embedding=embedding,
                    metadata=metadata
                )

            embedded_count += 1

        except Exception as e:
            logger.error(f"Failed to embed event {event.id}: {e}")

    await session.commit()
    return embedded_count


async def run_embedding_job_async():
    """Main embedding job - called by scheduler"""
    logger.info("Starting embedding job...")
    start = datetime.utcnow()

    async with async_session() as session:
        articles_count = await _embed_articles(session)
        events_count = await _embed_events(session)

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(
        f"Embedding job complete: {articles_count} articles, {events_count} events "
        f"({elapsed:.1f}s)"
    )


def run_embedding_job():
    """Sync wrapper for APScheduler"""
    asyncio.run(run_embedding_job_async())
