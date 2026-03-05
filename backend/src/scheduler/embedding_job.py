"""
Embedding job - runs daily at 6:20 AM (after AI processing, before summary)
Generates embeddings for new/unembedded articles and events
"""
import asyncio
from datetime import datetime, timedelta
from sqlmodel import select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import Article, Event, Source
from src.ai.embeddings import embedding_service
from src.ai.chunker import chunker
from src.utils.logger import setup_logger

logger = setup_logger("EmbeddingJob")

MAX_BATCH_SIZE = 200  # Max articles per run


async def _embed_articles(session):
    """Embed unembedded articles scraped today"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .where(Article.embedded == False)
        .where(Article.processed == True)
        .where(Article.scraped_at >= today_start)   # only today's articles
        .order_by(Article.scraped_at.desc())
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
            # Detect BIP source by name (Source.type="html" for all HTML scrapers)
            is_bip = "BIP" in source_name
            actual_source_type = "bip" if is_bip else "article"

            if is_bip:
                chunks = chunker.chunk_bip_document(
                    title=article.title,
                    content=article.content,
                    doc_type="dokument"
                )
            else:
                chunks = chunker.chunk_article(
                    title=article.title,
                    content=article.content,
                    summary=article.summary,
                    source_name=source_name,
                    category=article.category or ""
                )

            texts = [c["text"] for c in chunks]
            embeddings = await embedding_service.embed_batch(texts)

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                metadata = {
                    **chunk["metadata"],
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at.isoformat() if article.published_at else "",
                    "source_name": source_name
                }

                await embedding_service.store_embedding(
                    session=session,
                    source_type=actual_source_type,
                    source_id=article.id,
                    chunk_index=i,
                    chunk_text=chunk["text"],
                    embedding=embedding,
                    metadata=metadata
                )

            article.embedded = True
            session.add(article)
            embedded_count += 1
            logger.info(f"Embedded {actual_source_type} article {article.id} ({source_name}): {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Failed to embed article {article.id}: {e}")

    await session.commit()
    return embedded_count


async def _embed_events(session):
    """Embed unembedded events"""
    result = await session.execute(
        select(Event)
        .where(Event.embedded == False)
        .limit(MAX_BATCH_SIZE)
    )
    events = result.scalars().all()

    if not events:
        logger.info("No new events to embed")
        return 0

    logger.info(f"Embedding {len(events)} events...")
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

            event.embedded = True
            session.add(event)
            embedded_count += 1
            logger.info(f"Embedded event {event.id}: {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Failed to embed event {event.id}: {e}")

    await session.commit()
    return embedded_count


async def run_embedding_job_async():
    """Main embedding job - called by scheduler"""
    logger.info("Starting embedding job...")
    start = datetime.utcnow()

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        articles_count = await _embed_articles(session)
        events_count = await _embed_events(session)

    await engine.dispose()

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(
        f"Embedding job complete: {articles_count} articles, {events_count} events "
        f"({elapsed:.1f}s)"
    )


def run_embedding_job():
    """Sync wrapper for APScheduler"""
    asyncio.run(run_embedding_job_async())
