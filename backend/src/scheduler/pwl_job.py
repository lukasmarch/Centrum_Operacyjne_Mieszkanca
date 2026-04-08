"""
PwL Job - Quarterly scraping of polska-w-liczbach.pl

Uruchamiany kwartalnie (1,4,7,10 miesiąc o 5:00 AM) przez scheduler.
Scrapuje dane gminne z polskawliczbach.pl przez Firecrawl API,
importuje do pwl_gmina_stats z is_verified=False.

Dane wymagają ręcznej weryfikacji przez endpoint:
    POST /api/stats/pwl/verify/{log_id}

Wymaga: FIRECRAWL_API_KEY w zmiennych środowiskowych.
"""

import asyncio
import json
import logging
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.database.connection import async_session
from src.integrations.pwl_integration import (
    PWL_UNIT_ID,
    PWL_URL,
    PWL_DATA_YEAR,
    scrape_pwl_async,
    parse_pwl_markdown,
    flatten_pwl_data,
    generate_comparison_report,
    import_to_db,
)

logger = logging.getLogger("Scheduler.PwL")


async def run_pwl_scrape_async():
    """
    Async: Scrapuje polskawliczbach.pl i importuje dane do DB.
    Dane trafiają z is_verified=False — wymagają ręcznego zatwierdzenia.
    """
    logger.info("PwL Scrape: Start kwartalnego scrapowania")
    started_at = datetime.utcnow()

    # Utwórz log wpis
    async with async_session() as db:
        log_result = await db.execute(
            text("""
                INSERT INTO pwl_scrape_log
                    (unit_id, scraped_at, status, records_imported, records_updated)
                VALUES
                    (:uid, :now, 'running', 0, 0)
                RETURNING id

            """),
            {"uid": PWL_UNIT_ID, "now": started_at}
        )
        log_id = log_result.fetchone()[0]
        await db.commit()

    logger.info(f"PwL Scrape: Log ID={log_id}")

    try:
        # 1. Scrapuj przez Firecrawl
        logger.info(f"PwL Scrape: Scrapowanie {PWL_URL}")
        markdown = await scrape_pwl_async(PWL_URL)

        # 2. Parsuj markdown → dict
        logger.info("PwL Scrape: Parsowanie danych")
        pwl_data = parse_pwl_markdown(markdown)

        # 3. Generuj raport weryfikacyjny
        logger.info("PwL Scrape: Generowanie raportu weryfikacyjnego")
        async with async_session() as db:
            try:
                report = await generate_comparison_report(pwl_data, db)
            except Exception as e:
                logger.warning(f"PwL Scrape: Błąd generowania raportu: {e}")
                report = []

        # Sprawdź czy są duże różnice (>5%)
        big_diffs = [r for r in report if r.get("diff_pct") and r["diff_pct"] > 5]
        if big_diffs:
            logger.warning(
                f"PwL Scrape: Wykryto {len(big_diffs)} pól z różnicą >5% vs GUS: "
                + ", ".join(f"{r['field']}={r['diff_pct']:.1f}%" for r in big_diffs)
            )

        # 4. Spłaszcz dane do rekordów
        records = flatten_pwl_data(pwl_data, year=PWL_DATA_YEAR)
        logger.info(f"PwL Scrape: Przygotowano {len(records)} rekordów do importu")

        # 5. Import do DB (is_verified=False)
        async with async_session() as db:
            imported, updated = await import_to_db(
                records=records,
                db=db,
                log_id=log_id,
                is_verified=False,
            )

        # 6. Zaktualizuj log
        async with async_session() as db:
            await db.execute(
                text("""
                    UPDATE pwl_scrape_log
                    SET status = 'pending_verification',
                        records_imported = :imported,
                        records_updated = :updated,
                        verification_report = CAST(:report AS jsonb)
                    WHERE id = :id
                """),
                {
                    "imported": imported,
                    "updated": updated,
                    "report": json.dumps(report, ensure_ascii=False),
                    "id": log_id,
                }
            )
            await db.commit()

        logger.info(
            f"PwL Scrape: Zakończono. Zaimportowano={imported}, Zaktualizowano={updated}, Log={log_id}. "
            f"Dane wymagają weryfikacji: POST /api/stats/pwl/verify/{log_id}"
        )

        if big_diffs:
            logger.warning(
                f"PwL Scrape: UWAGA — dane wymagają ręcznej weryfikacji z powodu różnic vs GUS!"
            )

    except Exception as e:
        logger.error(f"PwL Scrape: Błąd podczas scrapowania: {e}", exc_info=True)

        async with async_session() as db:
            await db.execute(
                text("""
                    UPDATE pwl_scrape_log
                    SET status = 'failed',
                        error_message = :err
                    WHERE id = :id
                """),
                {"err": str(e)[:500], "id": log_id}
            )
            await db.commit()


def run_pwl_job():
    """
    Wrapper synchroniczny dla APScheduler.
    Kwartalny job — scrapuje polskawliczbach.pl i importuje do DB.
    Wymaga FIRECRAWL_API_KEY w .env.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(run_pwl_scrape_async())
    else:
        loop.run_until_complete(run_pwl_scrape_async())


if __name__ == "__main__":
    import os
    if not os.getenv("FIRECRAWL_API_KEY"):
        print("FIRECRAWL_API_KEY nie ustawiony — ustaw w .env przed uruchomieniem")
    else:
        asyncio.run(run_pwl_scrape_async())
