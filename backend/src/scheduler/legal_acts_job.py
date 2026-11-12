"""
Job aktów prawnych — niedziela 5:30 (etap 4, 2026-08-24; wolumen 12.11.2026)

Uchwały Rady i zarządzenia Wójta z modułu BIP `/akty/14/`. Godzina po wiedzy
stałej (4:00), bo oba zadania biją w ten sam mały serwer gminy i nie ma powodu,
żeby robiły to jednocześnie.

Zadanie robi dwie rzeczy pod rząd, bo jedno bez drugiego jest bezużyteczne:
zapisuje akty do `legal_acts`, a potem osadza te, które tego wymagają.

**Koszt trzyma `bip_id`, nie hash.** Akt prawny jest niezmienny — uchwała raz
podjęta nie zmienia treści; zmienić się może co najwyżej jej STATUS (uchylona,
zmieniona). Dlatego strony szczegółowe i PDF-y pobieramy WYŁĄCZNIE dla aktów,
których w bazie jeszcze nie ma. Ponowny przebieg to kilkanaście żądań na listę
zamiast kilkuset na pliki — a pełne napełnienie zakresu 2024–2026 to ~440 aktów
i ~20 minut.

`content_hash` zostaje mimo to: gdyby urząd podmienił załącznik, tekst pójdzie
do ponownego osadzenia, a bez porównania hashy płacilibyśmy za ten sam tekst.
"""
import asyncio
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.ai.chunker import chunker
from src.ai.embeddings import embedding_service
from src.config import settings
from src.database.schema import LegalAct
from src.scrapers.legal_acts import (
    DEFAULT_SINCE, LegalActsScraper, ScraperBlocked, content_hash,
)
from src.scrapers.polite import HostHeld
from src.utils.cost_tracker import log_api_cost
from src.utils.logger import setup_logger

logger = setup_logger("LegalActsJob")

SOURCE_TYPE = "legal_act"


async def _known_ids(session: AsyncSession) -> set[int]:
    rows = await session.execute(select(LegalAct.bip_id))
    return set(rows.scalars().all())


async def _store(session: AsyncSession, acts: list[dict]) -> dict:
    """Zapisuje nowe akty i odświeża status znanych.

    Status jest jedynym polem, które realnie się zmienia („Obowiązujący" →
    „Uchylony"), a mieszkaniec pytający o uchwałę MUSI wiedzieć, czy ona wciąż
    obowiązuje. Reszta metadanych aktu jest niezmienna.
    """
    stats = {"nowe": 0, "status": 0, "bez_zmian": 0}

    for act in acts:
        existing = (await session.execute(
            select(LegalAct).where(LegalAct.bip_id == act["bip_id"])
        )).scalar_one_or_none()

        if existing is None:
            session.add(LegalAct(
                bip_id=act["bip_id"],
                act_number=act.get("act_number"),
                act_group=act["act_group"],
                title=act["title"],
                adopted_at=act.get("adopted_at"),
                effective_from=act.get("effective_from"),
                status=act.get("status"),
                url=act["url"],
                pdf_url=act.get("pdf_url"),
                content=act.get("content"),
                content_hash=content_hash(act.get("content")),
                embedded=False,
            ))
            stats["nowe"] += 1
            continue

        existing.last_checked_at = datetime.utcnow()
        if act.get("status") and act["status"] != existing.status:
            logger.info(
                f"Status {existing.act_number}: {existing.status} → {act['status']}"
            )
            existing.status = act["status"]
            stats["status"] += 1
        else:
            stats["bez_zmian"] += 1
        session.add(existing)

    await session.commit()
    return stats


async def _embed(session: AsyncSession) -> int:
    acts = (await session.execute(
        select(LegalAct).where(LegalAct.embedded == False)  # noqa: E712
    )).scalars().all()

    if not acts:
        logger.info("Nic do osadzenia")
        return 0

    logger.info(f"Osadzam {len(acts)} aktów…")
    done = 0
    for act in acts:
        try:
            chunks = chunker.chunk_legal_act(
                title=act.title,
                content=act.content,
                act_number=act.act_number,
                act_group=act.act_group,
                adopted_at=act.adopted_at.isoformat() if act.adopted_at else None,
            )

            # Po skróceniu treści zostałyby chunki-sieroty: upsert nadpisuje
            # istniejące indeksy, ale nie kasuje tych ponad nową długość.
            await session.execute(
                text("""
                    DELETE FROM document_embeddings
                    WHERE source_type = :st AND source_id = :sid AND chunk_index >= :n
                """),
                {"st": SOURCE_TYPE, "sid": act.id, "n": len(chunks)},
            )

            embeddings = await embedding_service.embed_batch([c["text"] for c in chunks])
            log_api_cost(
                session,
                model="text-embedding-3-small",
                tokens_input=embedding_service.last_usage_tokens,
                tokens_output=0,
                endpoint="scheduler:legal_acts",
            )

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                await embedding_service.store_embedding(
                    session=session,
                    source_type=SOURCE_TYPE,
                    source_id=act.id,
                    chunk_index=i,
                    chunk_text=chunk["text"],
                    embedding=embedding,
                    metadata={
                        **chunk["metadata"],
                        "title": act.title,
                        "url": act.url,
                        # To widzi mieszkaniec pod odpowiedzią agenta.
                        "source_name": f"BIP Gminy Rybno — {act.act_group}",
                        "published_at": act.adopted_at.isoformat() if act.adopted_at else "",
                    },
                )

            act.embedded = True
            session.add(act)
            done += 1
        except Exception as e:
            logger.error(f"Nie osadziłem aktu {act.id} ({act.act_number}): {e}")

    await session.commit()
    return done


# Ile NOWYCH aktów dostaje w jednym przebiegu stronę szczegółów i PDF (2 żądania
# na akt). Sesja Rady to 10–20 uchwał; reszta czeka tydzień — nie trafia do bazy,
# więc następny przebieg widzi ją znów jako nową.
MAX_NEW_ACTS_PER_RUN = 20


async def run_legal_acts_async(
    since: date = DEFAULT_SINCE, dry: bool = False, full: bool = False,
    now: Optional[datetime] = None,
) -> dict:
    """Przebieg przyrostowy: tylko NOWE akty (2–3 strony listy + szczegóły nowych).

    Znanych aktów nie pobieramy ponownie i nie odświeżamy ich statusów
    (12.11.2026). `full=True` — wyłącznie ręcznie, cała lista (~45 żądań).
    """
    started = datetime.utcnow()
    logger.info(f"=== Akty prawne START (od {since}, {'pełny' if full else 'przyrostowy'}) ===")

    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        known = await _known_ids(session)

        async with LegalActsScraper() as scraper:
            try:
                listed = await scraper.list_acts(since=since, known_ids=None if full else known)
            except ScraperBlocked as e:
                await engine.dispose()
                if isinstance(e.__cause__, HostHeld):
                    # Wyłącznik — stan zamierzony, żadne żądanie nie wyszło.
                    logger.warning(f"Akty prawne pominięte: {e}")
                    return {"wstrzymane": str(e), "nowe": 0, "embedded": 0}
                # „0 nowych aktów” i „BIP nas nie wpuszcza” to dwie różne wiadomości;
                # wyjątek trafia do job_runs jako `error` i na Telegram.
                raise RuntimeError(f"PRZEBIEG PRZERWANY — {e}") from e

            fresh = [a for a in listed if a["bip_id"] not in known]
            logger.info(
                f"Na liście {len(listed)} aktów, nowych {len(fresh)}, "
                f"znanych {len(listed) - len(fresh)}"
            )

            if dry:
                await engine.dispose()
                logger.info("--dry: nie pobieram szczegółów i nie zapisuję")
                return {"listed": len(listed), "fresh": len(fresh), "dry": True}

            # Szczegóły i PDF-y TYLKO dla nowych — patrz docstring modułu.
            # Akt bez pobranych szczegółów NIE trafia do bazy: inaczej zostałby
            # „znany” bez treści na zawsze. Wróci w następnym przebiegu.
            detailed: list[dict] = []
            blocked: Optional[Exception] = None
            if len(fresh) > MAX_NEW_ACTS_PER_RUN:
                logger.info(f"Nowych {len(fresh)} — szczegóły dla {MAX_NEW_ACTS_PER_RUN}, reszta za tydzień")
            for act in fresh[:MAX_NEW_ACTS_PER_RUN]:
                try:
                    await scraper.fetch_details(act)
                except ScraperBlocked as e:
                    blocked = e
                    break
                if "pdf_url" in act:
                    detailed.append(act)

            # Znane akty z listy przy okazji odświeżają status (strona listy i tak
            # była pobrana) — bez żadnego dodatkowego żądania.
            stats = await _store(session, detailed + [a for a in listed if a["bip_id"] in known])

        embedded = await _embed(session)

    await engine.dispose()
    took = (datetime.utcnow() - started).total_seconds()
    logger.info(
        f"=== Akty prawne KONIEC: nowe={stats['nowe']} status={stats['status']} "
        f"bez_zmian={stats['bez_zmian']} osadzone={embedded} ({took:.1f}s) ==="
    )
    if blocked is not None:
        raise RuntimeError(f"Przebieg przerwany w trakcie szczegółów — {blocked}") from blocked
    return {**stats, "embedded": embedded, "seconds": took}


def run_legal_acts_job():
    """Wrapper synchroniczny dla APSchedulera."""
    asyncio.run(run_legal_acts_async())


if __name__ == "__main__":
    run_legal_acts_job()
