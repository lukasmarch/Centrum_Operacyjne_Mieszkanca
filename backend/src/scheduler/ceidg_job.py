"""
CEIDG Job - Synchronizacja danych firm z API CEIDG

Uruchamiany raz w tygodniu (dane nie zmieniają się często).
Pobiera firmy z Gminy Rybno (powiat działdowski) i zapisuje do bazy.
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from src.database.connection import async_session
from src.database.schema import CEIDGBusiness, CEIDGSyncStats
from src.integrations.ceidg_api import CEIDGService
from src.utils.logger import setup_logger

logger = setup_logger("CEIDGJob")


async def run_ceidg_job_async():
    """
    Async version for calling from within existing event loop.
    """
    await fetch_ceidg_businesses()


def run_ceidg_job():
    """
    Wrapper synchroniczny dla async job
    (APScheduler wymaga funkcji synchronicznej)
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(fetch_ceidg_businesses())
    else:
        loop.run_until_complete(fetch_ceidg_businesses())


async def fetch_ceidg_businesses():
    """
    Pobierz firmy z CEIDG i zapisz do bazy danych

    Proces:
    1. Połącz z API CEIDG
    2. Pobierz wszystkie firmy z Gminy Rybno (powiat działdowski)
    3. Upsert każdej firmy do tabeli ceidg_businesses
    4. Zaktualizuj statystyki w ceidg_sync_stats
    """
    logger.info("=" * 80)
    logger.info("CEIDG JOB - Synchronizacja firm z API CEIDG")
    logger.info("=" * 80)

    try:
        service = CEIDGService()
    except ValueError as e:
        logger.error(f"❌ CEIDG Job failed: {e}")
        return

    async with async_session() as session:
        # Optimization: Check if DB is populated before hitting API
        try:
            result = await session.execute(select(func.count(CEIDGBusiness.id)))
            count = result.scalar() or 0
            if count > 0:
                logger.info(f"🛑 Zabezpieczenie: W bazie jest już {count} firm. Pomijam pobieranie z API CEIDG.")
                return
        except Exception as e:
            logger.error(f"⚠️ Błąd podczas sprawdzania liczby firm: {e}")

        try:
            # 1. Pobierz wszystkie firmy
            logger.info("📊 Pobieranie firm z API CEIDG...")
            businesses, stats = await service.fetch_rybno_businesses()

            if not businesses:
                logger.warning("⚠️  Brak firm do przetworzenia")
                return

            logger.info(f"✓ Pobrano {len(businesses)} firm")

            # 2. Upsert każdej firmy
            logger.info("💾 Zapisywanie firm do bazy danych...")
            upserted = 0
            updated = 0

            total_items = len(businesses)
            for i, short_data in enumerate(businesses, 1):
                ceidg_id = short_data.get("id")
                if not ceidg_id:
                    continue
                
                # Pobierz szczegóły dla każdej firmy
                logger.info(f"[{i}/{total_items}] Fetching details for {ceidg_id}...")
                detailed_data = await service.get_business_details(ceidg_id)
                
                if not detailed_data:
                    logger.warning(f"⏩ Skipping {ceidg_id} - no details found")
                    continue

                data = service.extract_business_data(detailed_data)
                
                # Sprawdź czy firma już istnieje
                result = await session.execute(
                    select(CEIDGBusiness).where(CEIDGBusiness.ceidg_id == ceidg_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update istniejącego rekordu
                    for key, value in data.items():
                        if key != "fetched_at":  # Zachowaj oryginalną datę pobrania
                            setattr(existing, key, value)
                    updated += 1
                else:
                    # Insert nowego rekordu
                    business = CEIDGBusiness(**data)
                    session.add(business)
                    upserted += 1

            logger.info(f"  ✓ Nowych: {upserted}, zaktualizowanych: {updated}")

            # 3. Zaktualizuj statystyki synchronizacji
            logger.info("📈 Aktualizacja statystyk synchronizacji...")
            result = await session.execute(
                select(CEIDGSyncStats).where(CEIDGSyncStats.gmina == service.TARGET_GMINA)
            )
            sync_stats = result.scalar_one_or_none()

            if sync_stats:
                sync_stats.total_count = stats["total_count"]
                sync_stats.active_count = stats["active_count"]
                sync_stats.by_miejscowosc = stats["by_miejscowosc"]
                sync_stats.last_sync = datetime.utcnow()
                sync_stats.sync_status = "success"
            else:
                sync_stats = CEIDGSyncStats(
                    gmina=service.TARGET_GMINA,
                    powiat=service.TARGET_POWIAT,
                    total_count=stats["total_count"],
                    active_count=stats["active_count"],
                    by_miejscowosc=stats["by_miejscowosc"],
                    last_sync=datetime.utcnow(),
                    sync_status="success"
                )
                session.add(sync_stats)

            # 4. Commit
            await session.commit()

            # 5. Podsumowanie
            logger.info("=" * 80)
            logger.info("✅ CEIDG JOB ZAKOŃCZONY POMYŚLNIE!")
            logger.info("=" * 80)
            logger.info(f"📊 Statystyki:")
            logger.info(f"   - Łącznie firm: {stats['total_count']}")
            logger.info(f"   - Aktywnych: {stats['active_count']}")
            logger.info(f"   - Miejscowości: {len(stats['by_miejscowosc'])}")
            
            # Top 5 miejscowości
            top_5 = list(stats['by_miejscowosc'].items())[:5]
            for miasto, count in top_5:
                logger.info(f"   - {miasto}: {count}")

        except Exception as e:
            logger.error(f"❌ CEIDG Job failed: {e}")
            await session.rollback()
            
            # Zapisz status błędu
            try:
                result = await session.execute(
                    select(CEIDGSyncStats).where(CEIDGSyncStats.gmina == "Rybno")
                )
                sync_stats = result.scalar_one_or_none()
                if sync_stats:
                    sync_stats.sync_status = "failed"
                    sync_stats.last_sync = datetime.utcnow()
                    await session.commit()
            except:
                pass
            raise


async def import_from_json(json_path: str):
    """
    Import firm z istniejącego pliku JSON do bazy

    Args:
        json_path: Ścieżka do pliku rybno_businesses.json
    """
    import json
    
    logger.info(f"Importing from {json_path}...")
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    businesses = data.get("businesses", [])
    
    async with async_session() as session:
        imported = 0
        
        for raw in businesses:
            # Filtruj tylko powiat działdowski
            if raw.get("adres", {}).get("powiat", "").lower() != "działdowski":
                continue
            
            # Mapuj format JSON na format bazy
            adres = raw.get("adres", {})
            wlasciciel = raw.get("wlasciciel", {})
            
            data_rozp = raw.get("dataRozpoczecia")
            if data_rozp:
                try:
                    data_rozp = datetime.strptime(data_rozp, "%Y-%m-%d")
                except:
                    data_rozp = None
            
            business = CEIDGBusiness(
                ceidg_id=raw.get("id"),
                nazwa=raw.get("nazwa", ""),
                nip=raw.get("nip", ""),
                regon=raw.get("regon"),
                status=raw.get("status", "AKTYWNY"),
                data_rozpoczecia=data_rozp,
                wlasciciel_imie=wlasciciel.get("imie"),
                wlasciciel_nazwisko=wlasciciel.get("nazwisko"),
                ulica=adres.get("ulica"),
                budynek=adres.get("budynek"),
                lokal=adres.get("lokal"),
                miasto=adres.get("miasto", ""),
                kod_pocztowy=adres.get("kod", ""),
                gmina=adres.get("gmina", ""),
                powiat=adres.get("powiat", ""),
                wojewodztwo=adres.get("wojewodztwo"),
                raw_data=raw,
                ceidg_link=raw.get("link"),
                fetched_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Sprawdź czy istnieje
            result = await session.execute(
                select(CEIDGBusiness).where(CEIDGBusiness.ceidg_id == business.ceidg_id)
            )
            if not result.scalar_one_or_none():
                session.add(business)
                imported += 1
        
        await session.commit()
        logger.info(f"✓ Imported {imported} businesses from JSON")


if __name__ == "__main__":
    print("🧪 Test CEIDG Job...\n")
    run_ceidg_job()
