"""
Business API Endpoints - Katalog firm Gminy Rybno

Endpointy:
- GET /api/business/list - lista firm (z paginacją, filtry: miasto, category)
- GET /api/business/by-locality/{miasto} - firmy wg miejscowości
- GET /api/business/search - wyszukiwanie po nazwie (lub NIP)
- GET /api/business/stats - statystyki synchronizacji
- GET /api/business/analytics - statystyki historyczne (rok rejestracji, statusy)
- GET /api/business/categories - kategorie branżowe z liczbą firm
- GET /api/business/localities - lista miejscowości z liczbą firm
- POST /api/business/sync - ręczna synchronizacja
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlmodel import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session
from src.database.schema import CEIDGBusiness, CEIDGSyncStats
from src.auth.dependencies import get_optional_user
from src.utils.logger import setup_logger
from src.integrations.regon_api import RegonService

logger = setup_logger("BusinessAPI")

router = APIRouter(prefix="/api/business", tags=["business"])


# ==================== Response Models ====================

class BusinessResponse(BaseModel):
    id: int
    ceidg_id: str
    nazwa: str
    nip: str
    regon: Optional[str]
    status: str
    wlasciciel_imie: Optional[str]
    wlasciciel_nazwisko: Optional[str]
    ulica: Optional[str]
    budynek: Optional[str]
    miasto: str
    kod_pocztowy: str
    gmina: str
    powiat: str
    ceidg_link: Optional[str]
    pkd_main: Optional[str]
    pkd_list: Optional[List[dict]]
    branza: Optional[str] = None  # UI-friendly category (from PKD_FRIENDLY_NAMES)
    data_rozpoczecia: Optional[datetime] = None  # Year founded
    adres_korespondencyjny: Optional[Dict[str, Any]]
    spolki: Optional[List[Dict[str, Any]]]
    obywatelstwa: Optional[List[Dict[str, Any]]]
    email: Optional[str]
    www: Optional[str]
    telefon: Optional[str]

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj: Any) -> "BusinessResponse":
        # Custom validation to compute 'branza' using friendly names
        instance = super().model_validate(obj)
        if instance.pkd_main:
            from src.utils.pkd_mapping import get_friendly_category
            instance.branza = get_friendly_category(instance.pkd_main)
        return instance


class BusinessListResponse(BaseModel):
    businesses: List[BusinessResponse]
    total: int
    page: int
    limit: int
    localities: List[dict]  # Lista miejscowości z liczbą firm


class SyncStatsResponse(BaseModel):
    gmina: str
    powiat: str
    total_count: int
    active_count: int
    by_miejscowosc: dict
    last_sync: datetime
    sync_status: str


class AnalyticsResponse(BaseModel):
    by_year: Dict[str, int]           # {"2018": 12, ...} — total registrations per year
    by_year_suspended: Dict[str, int] # {"2018": 3, ...} — suspended businesses per registration year
    by_status: Dict[str, int]         # {"AKTYWNY": 450, "ZAWIESZONY": 30, ...}
    total: int


class CategoryItem(BaseModel):
    category: str
    count: int


# ==================== Endpoints ====================

@router.get("/list", response_model=BusinessListResponse)
async def list_businesses(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    miasto: Optional[str] = None,
    category: Optional[str] = None,  # Friendly category name filter (e.g. "Handel i naprawy")
    year: Optional[int] = None,       # Filter by registration year (data_rozpoczecia)
    status: Optional[str] = "AKTYWNY"
):
    """
    Lista wszystkich firm z Gminy Rybno

    Args:
        page: Numer strony (od 1)
        limit: Liczba wyników na stronę (max 100)
        miasto: Filtruj po miejscowości
        category: Filtruj po kategorii branżowej (przyjazna nazwa)
        status: Filtruj po statusie (domyślnie: AKTYWNY)
    """
    from src.utils.pkd_mapping import PKD_FRIENDLY_NAMES, PKD_DIVISION_MAP

    async with async_session() as session:
        # Base query
        query = select(CEIDGBusiness).where(CEIDGBusiness.powiat == "działdowski")

        if miasto:
            query = query.where(CEIDGBusiness.miasto == miasto)
        if status:
            query = query.where(CEIDGBusiness.status == status)

        # Category filter: find PKD division prefixes that map to this category
        matching_divisions: list = []
        if category:
            # Build list of 2-digit division codes whose section maps to this friendly name
            matching_divisions = [
                div for div, sec in PKD_DIVISION_MAP.items()
                if PKD_FRIENDLY_NAMES.get(sec) == category
            ]
            if matching_divisions:
                # Filter businesses whose pkd_main starts with any matching division
                from sqlalchemy import or_
                category_filters = [
                    CEIDGBusiness.pkd_main.startswith(div) for div in matching_divisions
                ]
                query = query.where(or_(*category_filters))

        # Year filter (data_rozpoczecia)
        if year:
            query = query.where(
                func.extract("year", CEIDGBusiness.data_rozpoczecia) == year
            )

        # Count total (with same filters)
        count_query = select(func.count()).select_from(CEIDGBusiness).where(
            CEIDGBusiness.powiat == "działdowski"
        )
        if miasto:
            count_query = count_query.where(CEIDGBusiness.miasto == miasto)
        if status:
            count_query = count_query.where(CEIDGBusiness.status == status)
        if category and matching_divisions:
            from sqlalchemy import or_
            count_query = count_query.where(or_(*[
                CEIDGBusiness.pkd_main.startswith(div) for div in matching_divisions
            ]))
        if year:
            count_query = count_query.where(
                func.extract("year", CEIDGBusiness.data_rozpoczecia) == year
            )

        total_result = await session.execute(count_query)
        total = total_result.scalar()

        # Get businesses with pagination
        query = query.order_by(CEIDGBusiness.nazwa).offset((page - 1) * limit).limit(limit)
        result = await session.execute(query)
        businesses = result.scalars().all()

        # Get localities breakdown (always all localities, no filters applied)
        localities_query = (
            select(CEIDGBusiness.miasto, func.count(CEIDGBusiness.id))
            .where(CEIDGBusiness.powiat == "działdowski")
            .group_by(CEIDGBusiness.miasto)
            .order_by(func.count(CEIDGBusiness.id).desc())
        )
        localities_result = await session.execute(localities_query)
        localities = [{"name": row[0], "count": row[1]} for row in localities_result.all()]

        return BusinessListResponse(
            businesses=[BusinessResponse.model_validate(b) for b in businesses],
            total=total,
            page=page,
            limit=limit,
            localities=localities
        )


@router.get("/by-locality/{miasto}", response_model=List[BusinessResponse])
async def get_businesses_by_locality(
    miasto: str,
    status: Optional[str] = "AKTYWNY"
):
    """
    Pobierz firmy z konkretnej miejscowości

    Args:
        miasto: Nazwa miejscowości
        status: Filtruj po statusie
    """
    async with async_session() as session:
        query = (
            select(CEIDGBusiness)
            .where(CEIDGBusiness.powiat == "działdowski")
            .where(CEIDGBusiness.miasto == miasto)
        )

        if status:
            query = query.where(CEIDGBusiness.status == status)

        query = query.order_by(CEIDGBusiness.nazwa)
        result = await session.execute(query)
        businesses = result.scalars().all()

        return [BusinessResponse.model_validate(b) for b in businesses]


@router.get("/search", response_model=List[BusinessResponse])
async def search_businesses(
    nip: Optional[str] = None,
    nazwa: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    status: Optional[str] = "AKTYWNY"
):
    """
    Wyszukaj firmy po nazwie (lub NIP)

    Args:
        nip: Numer NIP (z lub bez myślników) - opcjonalny
        nazwa: Fragment nazwy firmy - główny parametr wyszukiwania
        limit: Max liczba wyników
        status: Filtruj po statusie (domyślnie: AKTYWNY); przekaż pusty string aby wyłączyć filtr
    """
    if not nip and not nazwa:
        raise HTTPException(status_code=400, detail="Podaj nazwę firmy do wyszukania")

    async with async_session() as session:
        # Wyszukujemy tylko w gminie Rybno / powiecie działdowskim
        query = select(CEIDGBusiness).where(CEIDGBusiness.powiat == "działdowski")

        if status:
            query = query.where(CEIDGBusiness.status == status)

        if nip:
            # Usuń myślniki i spacje
            nip_clean = nip.replace("-", "").replace(" ", "")
            query = query.where(CEIDGBusiness.nip.contains(nip_clean))

        if nazwa:
            query = query.where(CEIDGBusiness.nazwa.ilike(f"%{nazwa}%"))

        query = query.order_by(CEIDGBusiness.nazwa).limit(limit)
        result = await session.execute(query)
        businesses = result.scalars().all()

        return [BusinessResponse.model_validate(b) for b in businesses]


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_business_analytics():
    """
    Statystyki historyczne firm:
    - by_year: liczba firm zarejestrowanych w danym roku (wszystkie statusy)
    - by_year_suspended: liczba zawieszonych firm wg roku rejestracji
    - by_status: podział wg statusu
    """
    async with async_session() as session:
        # By year: total registrations per year (all statuses)
        year_query = (
            select(
                func.extract("year", CEIDGBusiness.data_rozpoczecia).label("year"),
                func.count(CEIDGBusiness.id).label("count")
            )
            .where(CEIDGBusiness.powiat == "działdowski")
            .where(CEIDGBusiness.data_rozpoczecia.is_not(None))
            .group_by(func.extract("year", CEIDGBusiness.data_rozpoczecia))
            .order_by(func.extract("year", CEIDGBusiness.data_rozpoczecia))
        )
        year_result = await session.execute(year_query)
        by_year = {str(int(row[0])): row[1] for row in year_result.all()}

        # By year suspended: count businesses with ZAWIESZONY status per registration year
        year_suspended_query = (
            select(
                func.extract("year", CEIDGBusiness.data_rozpoczecia).label("year"),
                func.count(CEIDGBusiness.id).label("count")
            )
            .where(CEIDGBusiness.powiat == "działdowski")
            .where(CEIDGBusiness.data_rozpoczecia.is_not(None))
            .where(CEIDGBusiness.status == "ZAWIESZONY")
            .group_by(func.extract("year", CEIDGBusiness.data_rozpoczecia))
            .order_by(func.extract("year", CEIDGBusiness.data_rozpoczecia))
        )
        suspended_result = await session.execute(year_suspended_query)
        by_year_suspended = {str(int(row[0])): row[1] for row in suspended_result.all()}

        # By status: count businesses by status
        status_query = (
            select(CEIDGBusiness.status, func.count(CEIDGBusiness.id))
            .where(CEIDGBusiness.powiat == "działdowski")
            .group_by(CEIDGBusiness.status)
            .order_by(func.count(CEIDGBusiness.id).desc())
        )
        status_result = await session.execute(status_query)
        by_status = {row[0]: row[1] for row in status_result.all()}

        total = sum(by_status.values())

        return AnalyticsResponse(
            by_year=by_year,
            by_year_suspended=by_year_suspended,
            by_status=by_status,
            total=total
        )


@router.get("/categories", response_model=List[CategoryItem])
async def get_business_categories():
    """
    Pobierz listę kategorii branżowych z liczbą firm.
    Kategoryzacja oparta na kodach PKD (przyjazne nazwy).
    """
    from src.utils.pkd_mapping import get_friendly_category

    async with async_session() as session:
        # Fetch all active businesses' PKD main codes
        query = (
            select(CEIDGBusiness.pkd_main, func.count(CEIDGBusiness.id))
            .where(CEIDGBusiness.powiat == "działdowski")
            .where(CEIDGBusiness.status == "AKTYWNY")
            .where(CEIDGBusiness.pkd_main.is_not(None))
            .group_by(CEIDGBusiness.pkd_main)
        )
        result = await session.execute(query)
        rows = result.all()

        # Aggregate by friendly category name
        category_counts: Dict[str, int] = {}
        for pkd_main, count in rows:
            friendly = get_friendly_category(pkd_main)
            if friendly:
                category_counts[friendly] = category_counts.get(friendly, 0) + count

        # Sort by count descending
        sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        return [CategoryItem(category=cat, count=cnt) for cat, cnt in sorted_cats]


@router.get("/stats", response_model=Optional[SyncStatsResponse])
async def get_sync_stats():
    """
    Pobierz statystyki synchronizacji CEIDG
    """
    async with async_session() as session:
        result = await session.execute(
            select(CEIDGSyncStats).where(CEIDGSyncStats.gmina == "Rybno")
        )
        stats = result.scalar_one_or_none()

        if not stats:
            return None

        return SyncStatsResponse(
            gmina=stats.gmina,
            powiat=stats.powiat,
            total_count=stats.total_count,
            active_count=stats.active_count,
            by_miejscowosc=stats.by_miejscowosc,
            last_sync=stats.last_sync,
            sync_status=stats.sync_status
        )


@router.get("/localities", response_model=List[dict])
async def get_localities():
    """
    Pobierz listę miejscowości z liczbą firm
    """
    async with async_session() as session:
        query = (
            select(CEIDGBusiness.miasto, func.count(CEIDGBusiness.id))
            .where(CEIDGBusiness.powiat == "działdowski")
            .where(CEIDGBusiness.status == "AKTYWNY")
            .group_by(CEIDGBusiness.miasto)
            .order_by(func.count(CEIDGBusiness.id).desc())
        )
        result = await session.execute(query)
        localities = [{"name": row[0], "count": row[1]} for row in result.all()]
        return localities


@router.post("/sync")
async def trigger_sync(
    user = Depends(get_optional_user)
):
    """
    Ręczna synchronizacja z API CEIDG (wymaga zalogowania)
    """
    # Import here to avoid circular dependency
    from src.scheduler.ceidg_job import run_ceidg_job_async

    logger.info(f"Manual CEIDG sync triggered by user: {user.email if user else 'anonymous'}")

    try:
        await run_ceidg_job_async()
        return {"status": "success", "message": "Synchronizacja zakończona pomyślnie"}
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/regon-search", response_model=List[Dict[str, Any]])
async def regon_search_proxy(
    nip: Optional[str] = None,
    regon: Optional[str] = None,
    nazwa: Optional[str] = None
):
    """
    Wyszukiwarka live API REGON
    """
    if not any([nip, regon, nazwa]):
        raise HTTPException(status_code=400, detail="Podaj NIP, REGON lub nazwę")
    
    try:
        service = RegonService()
        results = await service.search(nip=nip, regon=regon, name=nazwa)
        return results
    except Exception as e:
        logger.error(f"Regon search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
