"""
Job wiedzy stałej z BIP — niedziela 4:00 (2026-08-03)

Statut, procedury, podatki i programy środowiskowe zmieniają się kilka razy
w roku, więc przebieg tygodniowy w martwej godzinie w zupełności wystarcza.
Zadanie robi dwie rzeczy pod rząd, bo jedno bez drugiego jest bezużyteczne:
pobiera dokumenty do `bip_documents`, a potem osadza te, które tego wymagają.

O ponownym osadzeniu decyduje `content_hash`, nie sam fakt pobrania. BIP
odświeża strony bez zmiany treści (rośnie licznik wyświetleń, zmienia się
rejestr zmian), a embedding statutu to ~25 chunków — bez porównania hashy
płacilibyśmy co tydzień za ten sam tekst.
"""
import asyncio
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.ai.chunker import chunker
from src.ai.embeddings import embedding_service
from src.config import settings
from src.database.schema import BipDocument
from src.scrapers.bip_knowledge import BipKnowledgeScraper
from src.utils.cost_tracker import log_api_cost
from src.utils.logger import setup_logger

logger = setup_logger("BipKnowledgeJob")

SOURCE_TYPE = "bip_static"


async def _store_documents(session: AsyncSession, documents: list[dict]) -> dict:
    """Zapisuje dokumenty; oznacza do ponownego osadzenia tylko te zmienione."""
    stats = {"nowe": 0, "zmienione": 0, "bez_zmian": 0}

    for doc in documents:
        existing = (await session.execute(
            select(BipDocument).where(BipDocument.url == doc["url"])
        )).scalars().first()

        if existing is None:
            session.add(BipDocument(**doc, embedded=False))
            stats["nowe"] += 1
            continue

        existing.last_checked_at = datetime.utcnow()
        if existing.content_hash == doc["content_hash"]:
            stats["bez_zmian"] += 1
        else:
            existing.title = doc["title"]
            existing.content = doc["content"]
            existing.content_hash = doc["content_hash"]
            existing.pdf_count = doc["pdf_count"]
            existing.section_name = doc["section_name"]
            existing.document_date = doc["document_date"]
            existing.content_changed_at = datetime.utcnow()
            existing.embedded = False
            stats["zmienione"] += 1
        session.add(existing)

    await session.commit()
    return stats


async def _embed_documents(session: AsyncSession) -> int:
    """Osadza dokumenty z `embedded = False`."""
    documents = (await session.execute(
        select(BipDocument).where(BipDocument.embedded == False)  # noqa: E712
    )).scalars().all()

    if not documents:
        logger.info("Brak dokumentów do osadzenia")
        return 0

    logger.info(f"Osadzanie {len(documents)} dokumentów BIP...")
    embedded_count = 0

    for doc in documents:
        try:
            chunks = chunker.chunk_bip_static(
                title=doc.title,
                content=doc.content,
                section_name=doc.section_name,
            )

            # Po skróceniu dokumentu zostałyby chunki-sieroty: upsert nadpisuje
            # tylko indeksy, które istnieją w nowej wersji.
            await session.execute(
                text("""
                    DELETE FROM document_embeddings
                    WHERE source_type = :st AND source_id = :sid AND chunk_index >= :n
                """),
                {"st": SOURCE_TYPE, "sid": doc.id, "n": len(chunks)},
            )

            embeddings = await embedding_service.embed_batch([c["text"] for c in chunks])
            log_api_cost(
                session,
                model="text-embedding-3-small",
                tokens_input=embedding_service.last_usage_tokens,
                tokens_output=0,
                endpoint="scheduler:bip_knowledge",
            )

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                await embedding_service.store_embedding(
                    session=session,
                    source_type=SOURCE_TYPE,
                    source_id=doc.id,
                    chunk_index=i,
                    chunk_text=chunk["text"],
                    embedding=embedding,
                    metadata={
                        **chunk["metadata"],
                        "title": doc.title,
                        "url": doc.url,
                        # Agent pokazuje to jako nazwę źródła pod odpowiedzią
                        "source_name": f"BIP Gminy Rybno — {doc.section_name}",
                        "published_at": doc.document_date.isoformat() if doc.document_date else "",
                    },
                )

            doc.embedded = True
            session.add(doc)
            embedded_count += 1
            logger.info(f"Osadzono [{doc.section_name}] {doc.title[:60]}: {len(chunks)} chunków")

        except Exception as e:
            logger.error(f"Nie udało się osadzić dokumentu {doc.id} ({doc.url}): {e}")

    await session.commit()
    return embedded_count


async def run_bip_knowledge_job_async():
    """Główny przebieg — wywoływany przez scheduler."""
    logger.info("Start job: wiedza stała z BIP")
    start = datetime.utcnow()

    scraper = BipKnowledgeScraper()
    documents = await scraper.scrape_all()
    logger.info(f"Pobrano {len(documents)} dokumentów z {len(scraper.sections)} działów")

    if not documents:
        # Pusty wynik przy działającym BIP oznacza zmianę struktury strony,
        # a nie brak treści — nie ma czego zapisywać, jest co zgłosić.
        # Druga, od 24.08.2026 równie prawdopodobna przyczyna: BIP odrzuca
        # adres IP tej maszyny (403 na wszystko, także na goły curl).
        logger.error(
            "Scraper nie zwrócił żadnego dokumentu. Dwie przyczyny warte "
            "sprawdzenia w tej kolejności: (1) dostęp — "
            "`curl -s -o /dev/null -w '%{http_code}' https://bip.gminarybno.pl/112/` "
            "z TEJ maszyny; 403 znaczy blokadę IP, (2) zmiana struktury strony."
        )
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        stats = await _store_documents(session, documents)
        embedded = await _embed_documents(session)

    await engine.dispose()

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(
        f"Job zakończony: nowe={stats['nowe']} zmienione={stats['zmienione']} "
        f"bez_zmian={stats['bez_zmian']} osadzone={embedded} ({elapsed:.1f}s)"
    )


def run_bip_knowledge_job():
    """Synchroniczna otoczka dla APScheduler."""
    asyncio.run(run_bip_knowledge_job_async())
