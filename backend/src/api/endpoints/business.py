"""
Business API Endpoints - Katalog firm Gminy Rybno

Endpointy:
- GET /api/business/list - lista firm (z paginacją)
- GET /api/business/by-locality/{miasto} - firmy wg miejscowości
- GET /api/business/search - wyszukiwanie po NIP/nazwie
- GET /api/business/stats - statystyki synchronizacji
- POST /api/business/sync - ręczna synchronizacja
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlmodel import select, func
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
    branza: Optional[str] = None # Calculated field
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
        # Custom validation to compute 'branza' on the fly
        instance = super().model_validate(obj)
        if instance.pkd_main:
            from src.utils.pkd_mapping import get_industry_from_pkd
            instance.branza = get_industry_from_pkd(instance.pkd_main)
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


# ==================== Endpoints ====================

@router.get("/list", response_model=BusinessListResponse)
async def list_businesses(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    miasto: Optional[str] = None,
    status: Optional[str] = "AKTYWNY"
):
    """
    Lista wszystkich firm z Gminy Rybno

    Args:
        page: Numer strony (od 1)
        limit: Liczba wyników na stronę (max 100)
        miasto: Filtruj po miejscowości
        status: Filtruj po statusie (domyślnie: AKTYWNY)
    """
    async with async_session() as session:
        # Base query
        query = select(CEIDGBusiness).where(CEIDGBusiness.powiat == "działdowski")

        if miasto:
            query = query.where(CEIDGBusiness.miasto == miasto)
        if status:
            query = query.where(CEIDGBusiness.status == status)

        # Count total
        count_query = select(func.count()).select_from(CEIDGBusiness).where(
            CEIDGBusiness.powiat == "działdowski"
        )
        if miasto:
            count_query = count_query.where(CEIDGBusiness.miasto == miasto)
        if status:
            count_query = count_query.where(CEIDGBusiness.status == status)

        total_result = await session.execute(count_query)
        total = total_result.scalar()

        # Get businesses with pagination
        query = query.order_by(CEIDGBusiness.nazwa).offset((page - 1) * limit).limit(limit)
        result = await session.execute(query)
        businesses = result.scalars().all()

        # Get localities breakdown
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
    limit: int = Query(20, ge=1, le=50)
):
    """
    Wyszukaj firmy po NIP lub nazwie

    Args:
        nip: Numer NIP (z lub bez myślników)
        nazwa: Fragment nazwy firmy
        limit: Max liczba wyników
    """
    if not nip and not nazwa:
        raise HTTPException(status_code=400, detail="Podaj NIP lub nazwę do wyszukania")

    async with async_session() as session:
        query = select(CEIDGBusiness)

        if nip:
            # Usuń myślniki i spacje
            nip_clean = nip.replace("-", "").replace(" ", "")
            query = query.where(CEIDGBusiness.nip.contains(nip_clean))

        if nazwa:
            query = query.where(CEIDGBusiness.nazwa.ilike(f"%{nazwa}%"))

        query = query.limit(limit)
        result = await session.execute(query)
        businesses = result.scalars().all()

        return [BusinessResponse.model_validate(b) for b in businesses]


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
