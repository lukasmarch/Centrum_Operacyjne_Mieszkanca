"""
Job wiedzy stałej z BIP — co niedzielę 4:00, ćwierć działów na raz (od 12.11.2026)

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
from src.scrapers.polite import HostHeld
from src.utils.cost_tracker import log_api_cost
from src.utils.logger import setup_logger

logger = setup_logger("BipKnowledgeJob")

SOURCE_TYPE = "bip_static"


async def _known_documents(session: AsyncSession) -> dict:
    """url → (page_hash, last_checked_at). `page_hash` czytany surowym SQL-em:
    kolumna z migracji `add_polite_http_state`, modelu nie ruszamy."""
    rows = await session.execute(text("SELECT url, page_hash, last_checked_at FROM bip_documents"))
    return {r[0]: (r[1], r[2]) for r in rows.all()}


async def _store_documents(session: AsyncSession, documents: list[dict]) -> dict:
    """Zapisuje dokumenty; oznacza do ponownego osadzenia tylko te zmienione."""
    stats = {"nowe": 0, "zmienione": 0, "bez_zmian": 0}
    hashes = {d["url"]: d["page_hash"] for d in documents if d.get("page_hash")}

    for doc in documents:
        if doc.get("unchanged"):
            # Strona bez zmian — PDF-ów nie pobieraliśmy, treść zostaje.
            await session.execute(
                text("UPDATE bip_documents SET last_checked_at = :now WHERE url = :url"),
                {"now": datetime.utcnow(), "url": doc["url"]},
            )
            stats["bez_zmian"] += 1
            continue
        doc = {k: v for k, v in doc.items() if k != "page_hash"}

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

    await session.flush()
    for url, h in hashes.items():
        await session.execute(
            text("UPDATE bip_documents SET page_hash = :h WHERE url = :url"), {"h": h, "url": url},
        )
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

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        known = await _known_documents(session)

    scraper = BipKnowledgeScraper(known=known)
    documents = await scraper.scrape_all()
    logger.info(
        f"Działy: {', '.join(n for _, n in scraper.sections)} — "
        f"{len(documents)} pozycji, {scraper.requests} żądań do BIP"
    )

    if scraper.blocked is not None and isinstance(scraper.blocked, HostHeld):
        # Wyłącznik — stan zamierzony. Nic nie poszło do BIP, nie ma czego zgłaszać.
        logger.warning(f"Wiedza stała pominięta: {scraper.blocked}")
        await engine.dispose()
        return

    if not documents:
        await engine.dispose()
        if scraper.blocked is not None:
            raise RuntimeError(f"BIP zamknięty — wiedza stała nie pobrana: {scraper.blocked}")
        # ⚠️ NIE sprawdzaj dostępu ręcznym curl-em z serwera — każde żądanie
        # poza `polite` jest niewidoczne w dzienniku i liczy się dostawcy BIP
        # jako nasz ruch. Stan i dziennik: `python -m scripts.bip_access --status`.
        logger.warning(
            "Scraper nie zwrócił żadnego dokumentu mimo działającego dostępu — "
            "prawdopodobnie zmiana struktury strony BIP. Dziennik żądań: "
            "`python -m scripts.bip_access --log`."
        )
        return

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
