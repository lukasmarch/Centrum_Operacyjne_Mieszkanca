"""
CEIDG Job - Synchronizacja danych firm z API CEIDG

Uruchamiany raz w tygodniu (dane nie zmieniają się często).
Pobiera firmy z Gminy Rybno (powiat działdowski) i zapisuje do bazy.
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.config import settings
from src.database.schema import CEIDGBusiness, CEIDGSyncStats
from src.integrations.ceidg_api import CEIDGService
from src.utils.logger import setup_logger

logger = setup_logger("CEIDGJob")

# Maks. liczba zapytań o szczegóły w jednym przebiegu (1 request/firmę) —
# ochrona przed rate limitem przy uzupełnianiu braków w istniejącym katalogu.
DETAIL_FETCH_LIMIT = 60

# Minimalne pokrycie listy z API względem bazy, przy którym ufamy, że brak firmy
# w odpowiedzi oznacza wykreślenie z rejestru, a nie awarię/niepełną odpowiedź.
MISSING_SANITY_RATIO = 0.8


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

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # 1. Pobierz wszystkie firmy
            logger.info("📊 Pobieranie firm z API CEIDG...")
            businesses, stats = await service.fetch_rybno_businesses()

            if not businesses:
                logger.warning("⚠️  Brak firm do przetworzenia")
                return

            logger.info(f"✓ Pobrano {len(businesses)} firm")

            # 2. Synchronizacja przyrostowa
            #
            # Lista z API jest tania (1 request / 25 firm), szczegóły kosztują
            # 1 request na firmę — dlatego pobieramy je tylko dla firm nowych
            # i tych, którym brakuje danych szczegółowych (pkd_main). Dzięki temu
            # job może chodzić co tydzień bez ryzyka rate limitu.
            logger.info("💾 Synchronizacja przyrostowa z bazą...")

            # Wpisy ręczne (source='manual') NIE biorą udziału w porównaniu
            # z rejestrem — ani jako kandydaci do wykreślenia, ani w mianowniku
            # pokrycia. To firmy spoza CEIDG (spółki, oddziały, koła gospodyń),
            # więc ich nieobecność w odpowiedzi API jest stanem normalnym,
            # a nie sygnałem, że zniknęły z rejestru.
            result = await session.execute(
                select(CEIDGBusiness).where(CEIDGBusiness.source == "ceidg")
            )
            db_firms = {b.ceidg_id: b for b in result.scalars().all()}

            api_ids = set()
            new_count = 0
            status_changes = []
            details_filled = 0
            now = datetime.utcnow()

            for short_data in businesses:
                ceidg_id = short_data.get("id")
                if not ceidg_id:
                    continue
                api_ids.add(ceidg_id)

                existing = db_firms.get(ceidg_id)
                api_status = short_data.get("status", "AKTYWNY")

                if existing is None:
                    # Nowa firma — pełne dane wymagają zapytania o szczegóły
                    detailed = await service.get_business_details(ceidg_id)
                    data = service.extract_business_data(detailed or short_data)
                    if not data.get("ceidg_id"):
                        data["ceidg_id"] = ceidg_id
                    data["status_changed_at"] = now
                    session.add(CEIDGBusiness(**data))
                    new_count += 1
                    logger.info(f"  ➕ Nowa firma: {data.get('nazwa', ceidg_id)} [{api_status}]")
                    continue

                # Firma znana — reaguj tylko na realną zmianę statusu
                if existing.status != api_status:
                    logger.info(
                        f"  🔄 Zmiana statusu: {existing.nazwa} "
                        f"{existing.status} → {api_status}"
                    )
                    status_changes.append((existing.nazwa, existing.status, api_status))
                    existing.previous_status = existing.status
                    existing.status = api_status
                    existing.status_changed_at = now
                    existing.updated_at = now

                # Uzupełnij braki po firmach zaimportowanych bez szczegółów
                if existing.pkd_main is None and details_filled < DETAIL_FETCH_LIMIT:
                    detailed = await service.get_business_details(ceidg_id)
                    if detailed:
                        data = service.extract_business_data(detailed)
                        for key, value in data.items():
                            # fetched_at = data pierwszego pobrania, nie nadpisujemy;
                            # status obsłużony wyżej (razem ze śledzeniem zmiany)
                            if key not in ("fetched_at", "status", "ceidg_id"):
                                setattr(existing, key, value)
                        existing.updated_at = now
                        details_filled += 1

            # 2b. Firmy obecne w bazie, ale nieobecne w odpowiedzi API.
            # Oznaczamy jako wykreślone tylko gdy API zwróciło wiarygodnie pełną
            # listę — inaczej częściowa awaria API „wykreśliłaby" pół katalogu.
            missing_ids = set(db_firms) - api_ids
            removed_count = 0
            if missing_ids:
                coverage = len(api_ids) / len(db_firms) if db_firms else 0
                if coverage >= MISSING_SANITY_RATIO:
                    for ceidg_id in missing_ids:
                        firm = db_firms[ceidg_id]
                        if firm.status == "WYKRESLONY":
                            continue
                        logger.info(f"  ➖ Zniknęła z rejestru: {firm.nazwa} ({firm.status} → WYKRESLONY)")
                        firm.previous_status = firm.status
                        firm.status = "WYKRESLONY"
                        firm.status_changed_at = now
                        firm.updated_at = now
                        removed_count += 1
                else:
                    logger.warning(
                        f"⚠️  {len(missing_ids)} firm brakuje w odpowiedzi API, ale pokrycie "
                        f"listy to tylko {coverage:.0%} (próg {MISSING_SANITY_RATIO:.0%}) — "
                        f"pomijam oznaczanie wykreśleń, dane mogą być niekompletne"
                    )

            logger.info(
                f"  ✓ Nowych: {new_count}, zmian statusu: {len(status_changes)}, "
                f"wykreślonych: {removed_count}, uzupełnionych szczegółów: {details_filled}"
            )

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
            logger.info(f"   - Nowych w tym przebiegu: {new_count}")
            logger.info(f"   - Zmian statusu: {len(status_changes)}")
            for nazwa, old, new in status_changes[:10]:
                logger.info(f"     · {nazwa}: {old} → {new}")
            
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

    await engine.dispose()


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

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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

    await engine.dispose()


if __name__ == "__main__":
    print("🧪 Test CEIDG Job...\n")
    run_ceidg_job()
