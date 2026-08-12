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
import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File
from pydantic import BaseModel
from sqlmodel import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session
from src.database.schema import (
    CEIDGBusiness, CEIDGSyncStats, BusinessProfile, BusinessAnnouncement,
)
from src.auth.dependencies import get_optional_user, get_admin_user, get_current_active_user
from src.utils.logger import setup_logger
from src.integrations.regon_api import RegonService

logger = setup_logger("BusinessAPI")

# Logo wizytówki — lokalny dysk (ten sam wzorzec co uploads/reports), serwowane
# przez StaticFiles("/uploads") zamontowane w main.py
LOGO_UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads" / "business_logos"
LOGO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOGO_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
LOGO_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB — logo, nie zdjęcie reportażowe

router = APIRouter(prefix="/api/business", tags=["business"])


# ==================== Response Models ====================

class BusinessResponse(BaseModel):
    id: int
    ceidg_id: str
    nazwa: str
    nip: str
    regon: Optional[str]
    status: str
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
    # Minimalizacja danych (RODO art. 5): imię i nazwisko właściciela, adres
    # korespondencyjny, spółki, obywatelstwa i kontakt rejestrowy nie są
    # publikowane. Kontakt pojawi się, gdy firma poda go sama przy przejęciu
    # wizytówki (zgoda).

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


class ProfilePublic(BaseModel):
    """Publiczne dane wizytówki (kontakt podany przez firmę = zgoda)"""
    description: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None
    www: Optional[str] = None
    godziny: Optional[str] = None
    logo_url: Optional[str] = None
    is_premium: bool = False


class CatalogCard(BaseModel):
    """Karta katalogu wizytówek (strona główna zakładki Firmy)"""
    id: int
    nazwa: str
    miasto: str
    branza: Optional[str] = None
    status: str
    data_rozpoczecia: Optional[datetime] = None
    profile: ProfilePublic


class ClaimRequest(BaseModel):
    telefon: Optional[str] = None
    email: Optional[str] = None
    www: Optional[str] = None
    note: Optional[str] = None  # jak zweryfikować, że to Twoja firma


class ProfileUpdateRequest(BaseModel):
    description: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None
    www: Optional[str] = None
    godziny: Optional[str] = None
    logo_url: Optional[str] = None


class PendingClaim(BaseModel):
    claim_id: int
    business_id: int
    nazwa: str
    miasto: str
    nip: str
    user_email: str
    note: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime


class AnnouncementCreate(BaseModel):
    type: str = "ogloszenie"  # ogloszenie / okazja
    title: str
    body: str
    valid_until: Optional[datetime] = None


class AnnouncementResponse(BaseModel):
    id: int
    business_id: int
    type: str
    title: str
    body: str
    valid_until: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ActiveAnnouncement(BaseModel):
    """Publiczna reprezentacja ogłoszenia — feed, kafel, newsletter.
    Zawsze prezentowane z oznaczeniem materiału reklamowego."""
    id: int
    business_id: int
    type: str
    title: str
    body: str
    valid_until: Optional[datetime] = None
    created_at: datetime
    nazwa: str
    miasto: str
    branza: Optional[str] = None
    telefon: Optional[str] = None
    logo_url: Optional[str] = None


# Limity publikacji planu Firma lokalna (BusinessPage obiecuje 2 ogłoszenia/mc;
# okazje są krótkotrwałe, więc mają osobny, luźniejszy limit)
ANNOUNCEMENT_MONTHLY_QUOTA = {"ogloszenie": 2, "okazja": 8}
OKAZJA_MAX_DAYS = 7


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


# ==================== Helpers ====================

def apply_public_visibility(query):
    """Filtry widoczności publicznej: bez sprzeciwów (RODO art. 21)
    i bez firm wykreślonych z rejestru (retencja, art. 5)."""
    return query.where(
        CEIDGBusiness.opted_out == False  # noqa: E712
    ).where(CEIDGBusiness.status != "WYKRESLONY")


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
        query = apply_public_visibility(
            select(CEIDGBusiness).where(CEIDGBusiness.powiat == "działdowski")
        )

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
        count_query = apply_public_visibility(
            select(func.count()).select_from(CEIDGBusiness).where(
                CEIDGBusiness.powiat == "działdowski"
            )
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
        localities_query = apply_public_visibility(
            select(CEIDGBusiness.miasto, func.count(CEIDGBusiness.id))
            .where(CEIDGBusiness.powiat == "działdowski")
        ).group_by(CEIDGBusiness.miasto).order_by(func.count(CEIDGBusiness.id).desc())
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
        query = apply_public_visibility(
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
        query = apply_public_visibility(
            select(CEIDGBusiness).where(CEIDGBusiness.powiat == "działdowski")
        )

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
    - by_year: liczba firm zarejestrowanych w danym roku (widocznych publicznie)
    - by_year_suspended: liczba zawieszonych firm wg roku rejestracji
    - by_status: podział wg statusu (pełny, łącznie z wykreślonymi — licznik na górze strony)

    by_year/by_year_suspended przechodzą przez apply_public_visibility(), żeby słupek
    wykresu zgadzał się z liczbą kafelków po kliknięciu roku. Bez tego wykres liczył
    też firmy wykreślone z rejestru, których lista celowo nie pokazuje (RODO art. 5).
    """
    async with async_session() as session:
        # By year: registrations per year (tylko firmy widoczne publicznie)
        year_query = (
            apply_public_visibility(
                select(
                    func.extract("year", CEIDGBusiness.data_rozpoczecia).label("year"),
                    func.count(CEIDGBusiness.id).label("count")
                )
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
            apply_public_visibility(
                select(
                    func.extract("year", CEIDGBusiness.data_rozpoczecia).label("year"),
                    func.count(CEIDGBusiness.id).label("count")
                )
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
        query = apply_public_visibility(
            select(CEIDGBusiness.pkd_main, func.count(CEIDGBusiness.id))
            .where(CEIDGBusiness.powiat == "działdowski")
            .where(CEIDGBusiness.status == "AKTYWNY")
            .where(CEIDGBusiness.pkd_main.is_not(None))
        ).group_by(CEIDGBusiness.pkd_main)
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
        query = apply_public_visibility(
            select(CEIDGBusiness.miasto, func.count(CEIDGBusiness.id))
            .where(CEIDGBusiness.powiat == "działdowski")
            .where(CEIDGBusiness.status == "AKTYWNY")
        ).group_by(CEIDGBusiness.miasto).order_by(func.count(CEIDGBusiness.id).desc())
        result = await session.execute(query)
        localities = [{"name": row[0], "count": row[1]} for row in result.all()]
        return localities


@router.post("/sync")
async def trigger_sync(
    user = Depends(get_admin_user)
):
    """
    Ręczna synchronizacja z API CEIDG (wymaga roli administratora)
    """
    # Import here to avoid circular dependency
    from src.scheduler.ceidg_job import run_ceidg_job_async

    logger.info(f"Manual CEIDG sync triggered by admin: {user.email}")

    try:
        await run_ceidg_job_async()
        return {"status": "success", "message": "Synchronizacja zakończona pomyślnie"}
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Wizytówki (katalog firm — sprint B) ====================

@router.get("/catalog", response_model=List[CatalogCard])
async def get_catalog(limit: int = Query(60, ge=1, le=200)):
    """
    Katalog wizytówek — strona główna zakładki Firmy.
    Tylko firmy ze zweryfikowanym przejęciem; premium („Firma lokalna") na górze.
    """
    from src.utils.pkd_mapping import get_friendly_category

    async with async_session() as session:
        query = apply_public_visibility(
            select(CEIDGBusiness, BusinessProfile)
            .join(BusinessProfile, BusinessProfile.business_id == CEIDGBusiness.id)
            .where(BusinessProfile.claim_status == "verified")
        ).order_by(
            BusinessProfile.is_premium.desc(),
            BusinessProfile.views_count.desc(),
            CEIDGBusiness.nazwa,
        ).limit(limit)

        result = await session.execute(query)
        cards = []
        for business, profile in result.all():
            cards.append(CatalogCard(
                id=business.id,
                nazwa=business.nazwa,
                miasto=business.miasto,
                branza=get_friendly_category(business.pkd_main) if business.pkd_main else None,
                status=business.status,
                data_rozpoczecia=business.data_rozpoczecia,
                profile=ProfilePublic(
                    description=profile.description,
                    telefon=profile.telefon,
                    email=profile.email,
                    www=profile.www,
                    godziny=profile.godziny,
                    logo_url=profile.logo_url,
                    is_premium=profile.is_premium,
                ),
            ))
        return cards


@router.get("/my-claims")
async def get_my_claims(user=Depends(get_current_active_user)):
    """Przejęcia wizytówek zalogowanego użytkownika (status + business_id)."""
    async with async_session() as session:
        result = await session.execute(
            select(BusinessProfile, CEIDGBusiness.nazwa)
            .join(CEIDGBusiness, CEIDGBusiness.id == BusinessProfile.business_id)
            .where(BusinessProfile.user_id == user.id)
        )
        return [
            {
                "claim_id": p.id,
                "business_id": p.business_id,
                "nazwa": nazwa,
                "claim_status": p.claim_status,
                "is_premium": p.is_premium,
                "views_count": p.views_count,
            }
            for p, nazwa in result.all()
        ]


@router.post("/{business_id}/claim", status_code=201)
async def claim_business(
    business_id: int,
    request: ClaimRequest,
    user=Depends(get_current_active_user),
):
    """
    Przejmij wizytówkę — krok 3 flow (konto już istnieje).
    Weryfikacja ręczna przez admina (MVP); kontakt podany przez firmę
    publikowany jest dopiero po zatwierdzeniu (zgoda jako podstawa prawna).
    """
    async with async_session() as session:
        result = await session.execute(
            select(CEIDGBusiness).where(CEIDGBusiness.id == business_id)
        )
        business = result.scalar_one_or_none()
        if not business or business.opted_out:
            raise HTTPException(status_code=404, detail="Firma nie została znaleziona")

        existing = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        profile = existing.scalar_one_or_none()
        if profile and profile.claim_status == "rejected":
            # Wiersze "rejected" sprzed poprawki z 12.08.2026 blokowały firmę
            # bezterminowo. Sprzątamy je przy pierwszej próbie przejęcia, żeby
            # naprawa działała także na danych, które już są w bazie —
            # bez ręcznego SQL-a na produkcji
            logger.info(
                f"Claim: usuwam zalegający odrzucony profil {profile.id} "
                f"dla firmy {business_id}"
            )
            await session.delete(profile)
            await session.flush()
            profile = None
        if profile:
            if profile.user_id == user.id:
                raise HTTPException(status_code=409, detail="Już zgłosiłeś przejęcie tej wizytówki")
            raise HTTPException(status_code=409, detail="Ta wizytówka została już przejęta")

        profile = BusinessProfile(
            business_id=business_id,
            user_id=user.id,
            claim_status="pending",
            claim_note=request.note,
            telefon=request.telefon,
            email=request.email,
            www=request.www,
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

        logger.info(f"Business claim: business={business_id} '{business.nazwa}' by user={user.email}")
        return {"status": "pending", "claim_id": profile.id,
                "message": "Zgłoszenie przyjęte — zweryfikujemy je w ciągu 2 dni roboczych."}


@router.get("/claims/pending", response_model=List[PendingClaim])
async def list_pending_claims(user=Depends(get_admin_user)):
    """Przejęcia wizytówek oczekujące na weryfikację (tylko admin)."""
    from src.database.schema import User
    async with async_session() as session:
        result = await session.execute(
            select(BusinessProfile, CEIDGBusiness, User.email)
            .join(CEIDGBusiness, CEIDGBusiness.id == BusinessProfile.business_id)
            .join(User, User.id == BusinessProfile.user_id)
            .where(BusinessProfile.claim_status == "pending")
            .order_by(BusinessProfile.created_at.asc())
        )
        return [
            PendingClaim(
                claim_id=p.id,
                business_id=b.id,
                nazwa=b.nazwa,
                miasto=b.miasto,
                nip=b.nip,
                user_email=email,
                note=p.claim_note,
                telefon=p.telefon,
                email=p.email,
                created_at=p.created_at,
            )
            for p, b, email in result.all()
        ]


@router.patch("/claims/{claim_id}")
async def moderate_claim(
    claim_id: int,
    action: str = Query(..., regex="^(approve|reject)$"),
    user=Depends(get_admin_user),
):
    """Zatwierdź lub odrzuć przejęcie wizytówki (tylko admin)."""
    async with async_session() as session:
        result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.id == claim_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        if action == "reject":
            # Odrzucenie KASUJE wiersz, nie oznacza go statusem.
            #
            # Dlaczego: `claim_business` blokuje przejęcie, gdy dla firmy istnieje
            # JAKIKOLWIEK profil. Zostawiony wiersz "rejected" blokował więc firmę
            # na zawsze — prawdziwy właściciel dostawał „Ta wizytówka została już
            # przejęta" i nie miał jak tego obejść. Wykryte 12.08.2026 przy
            # sprzątaniu po teście przejęcia.
            #
            # Uboczna korzyść: dane kontaktowe odrzuconego zgłaszającego nie
            # zostają w bazie bezterminowo. Ślad audytowy niesie log poniżej.
            business_id = profile.business_id
            await session.delete(profile)
            await session.commit()
            logger.info(
                f"Claim {claim_id} reject by admin {user.email} — profil skasowany, "
                f"firma {business_id} wraca do puli"
            )
            return {"status": "ok", "claim_status": "rejected", "profile_deleted": True}

        profile.claim_status = "verified"
        profile.verified_at = datetime.utcnow()
        profile.updated_at = datetime.utcnow()
        session.add(profile)
        await session.commit()

        logger.info(f"Claim {claim_id} approve by admin {user.email}")
        return {"status": "ok", "claim_status": profile.claim_status}


@router.patch("/{business_id}/profile")
async def update_business_profile(
    business_id: int,
    request: ProfileUpdateRequest,
    user=Depends(get_current_active_user),
):
    """Edycja wizytówki przez zweryfikowanego właściciela."""
    async with async_session() as session:
        result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        profile = result.scalar_one_or_none()
        if not profile or profile.user_id != user.id:
            raise HTTPException(status_code=404, detail="Wizytówka nie została znaleziona")
        if profile.claim_status != "verified":
            raise HTTPException(status_code=403, detail="Wizytówka czeka na weryfikację")

        for field in ("description", "telefon", "email", "www", "godziny", "logo_url"):
            value = getattr(request, field)
            if value is not None:
                setattr(profile, field, value.strip() or None)
        profile.updated_at = datetime.utcnow()
        session.add(profile)
        await session.commit()
        return {"status": "ok"}


@router.post("/{business_id}/logo")
async def upload_business_logo(
    business_id: int,
    logo: UploadFile = File(...),
    user=Depends(get_current_active_user),
):
    """Upload logo wizytówki przez zweryfikowanego właściciela (max 2MB, jpg/png/webp)."""
    async with async_session() as session:
        result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        profile = result.scalar_one_or_none()
        if not profile or profile.user_id != user.id:
            raise HTTPException(status_code=404, detail="Wizytówka nie została znaleziona")
        if profile.claim_status != "verified":
            raise HTTPException(status_code=403, detail="Wizytówka czeka na weryfikację")

        ext = os.path.splitext(logo.filename or "")[1].lower()
        if ext not in LOGO_ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Niedozwolony format pliku. Dozwolone: {', '.join(LOGO_ALLOWED_EXTENSIONS)}",
            )

        logo_bytes = await logo.read()
        if len(logo_bytes) > LOGO_MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Plik jest za duży. Maksymalny rozmiar: 2MB")

        old_logo_url = profile.logo_url
        filename = f"{business_id}_{uuid.uuid4().hex}{ext}"
        filepath = LOGO_UPLOAD_DIR / filename
        with open(filepath, "wb") as f:
            f.write(logo_bytes)

        profile.logo_url = f"/uploads/business_logos/{filename}"
        profile.updated_at = datetime.utcnow()
        session.add(profile)
        await session.commit()

        # Sprzątanie starego pliku (best-effort — nie blokuje odpowiedzi)
        if old_logo_url and old_logo_url.startswith("/uploads/business_logos/"):
            old_filename = old_logo_url.removeprefix("/uploads/business_logos/")
            try:
                (LOGO_UPLOAD_DIR / old_filename).unlink(missing_ok=True)
            except OSError:
                pass

        logger.info(f"Logo uploaded for business={business_id} by {user.email}")
        return {"status": "ok", "logo_url": profile.logo_url}


@router.patch("/{business_id}/premium")
async def set_business_premium(
    business_id: int,
    enabled: bool = Query(...),
    months: int = Query(1, ge=1, le=24),
    user=Depends(get_admin_user),
):
    """Plan „Firma lokalna" (49 zł/mc) — w MVP włączany przez admina po opłacie
    (faktura/przelew); bramka płatności dojdzie później."""
    from datetime import timedelta
    async with async_session() as session:
        result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Firma nie ma przejętej wizytówki")

        profile.is_premium = enabled
        profile.premium_until = (
            datetime.utcnow() + timedelta(days=30 * months) if enabled else None
        )
        profile.updated_at = datetime.utcnow()
        session.add(profile)
        await session.commit()

        logger.info(f"Premium {'ON' if enabled else 'OFF'} for business={business_id} by {user.email}")
        return {"status": "ok", "is_premium": enabled, "premium_until": profile.premium_until}


@router.post("/{business_id}/view")
async def track_business_view(
    business_id: int,
    kind: str = Query("impression", regex="^(impression|contact)$"),
):
    """
    Licznik wizytówki — DWIE różne miary.

    `impression` — karta pojawiła się na ekranie (katalog, sekcja Reklama).
    `contact`    — ktoś kliknął telefon, www albo e-mail.

    Domyślnie `impression`, i to jest celowe: gdyby domyślną wartością był
    `contact`, każdy nieuaktualniony klient podbijałby liczbę, którą sprzedajemy.
    Zawyżona statystyka kosztuje więcej niż jej brak — do 12.08.2026 katalog
    liczył pokazy jako „wyświetlenia wizytówki" i jedno wejście na zakładkę
    Firmy podbijało wynik wszystkim firmom naraz.
    """
    async with async_session() as session:
        result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            if kind == "contact":
                profile.views_count += 1
            else:
                profile.impressions_count += 1
            session.add(profile)
            await session.commit()
        return {"status": "ok", "kind": kind}


@router.get("/announcements/active", response_model=List[ActiveAnnouncement])
async def get_active_announcements(limit: int = Query(10, ge=1, le=50)):
    """
    Radar Lokalnego Biznesu — aktywne ogłoszenia i okazje firm z planu
    Firma lokalna. Zasila kafel na stronie głównej, feed i newsletter.
    """
    from src.utils.pkd_mapping import get_friendly_category

    now = datetime.utcnow()
    async with async_session() as session:
        query = apply_public_visibility(
            select(BusinessAnnouncement, CEIDGBusiness, BusinessProfile)
            .join(CEIDGBusiness, CEIDGBusiness.id == BusinessAnnouncement.business_id)
            .join(BusinessProfile, BusinessProfile.business_id == CEIDGBusiness.id)
            .where(BusinessAnnouncement.is_active == True)  # noqa: E712
            .where(
                (BusinessAnnouncement.valid_until.is_(None))
                | (BusinessAnnouncement.valid_until > now)
            )
            .where(BusinessProfile.claim_status == "verified")
            .where(BusinessProfile.is_premium == True)  # noqa: E712
        ).order_by(BusinessAnnouncement.created_at.desc()).limit(limit)

        result = await session.execute(query)
        items = []
        for ann, business, profile in result.all():
            items.append(ActiveAnnouncement(
                id=ann.id,
                business_id=business.id,
                type=ann.type,
                title=ann.title,
                body=ann.body,
                valid_until=ann.valid_until,
                created_at=ann.created_at,
                nazwa=business.nazwa,
                miasto=business.miasto,
                branza=get_friendly_category(business.pkd_main) if business.pkd_main else None,
                telefon=profile.telefon,
                logo_url=profile.logo_url,
            ))
        return items


async def _get_owned_premium_profile(session, business_id: int, user) -> BusinessProfile:
    """Wizytówka należąca do usera; publikacja ogłoszeń wymaga planu Firma lokalna."""
    result = await session.execute(
        select(BusinessProfile).where(BusinessProfile.business_id == business_id)
    )
    profile = result.scalar_one_or_none()
    if not profile or profile.user_id != user.id:
        raise HTTPException(status_code=404, detail="Wizytówka nie została znaleziona")
    if profile.claim_status != "verified":
        raise HTTPException(status_code=403, detail="Wizytówka czeka na weryfikację")
    return profile


@router.get("/{business_id}/announcements", response_model=List[AnnouncementResponse])
async def list_my_announcements(
    business_id: int,
    user=Depends(get_current_active_user),
):
    """Ogłoszenia właściciela wizytówki (także nieaktywne i wygasłe)."""
    async with async_session() as session:
        await _get_owned_premium_profile(session, business_id, user)
        result = await session.execute(
            select(BusinessAnnouncement)
            .where(BusinessAnnouncement.business_id == business_id)
            .order_by(BusinessAnnouncement.created_at.desc())
            .limit(50)
        )
        return result.scalars().all()


@router.post("/{business_id}/announcements", response_model=AnnouncementResponse, status_code=201)
async def create_announcement(
    business_id: int,
    request: AnnouncementCreate,
    user=Depends(get_current_active_user),
):
    """
    Publikacja ogłoszenia/okazji (plan Firma lokalna).
    Limity miesięczne: 2 ogłoszenia, 8 okazji; okazja musi mieć
    valid_until maks. 7 dni w przód.
    """
    ann_type = request.type.strip().lower()
    if ann_type not in ANNOUNCEMENT_MONTHLY_QUOTA:
        raise HTTPException(status_code=400, detail="Typ musi być 'ogloszenie' lub 'okazja'")

    title = request.title.strip()
    body = request.body.strip()
    if not title or len(title) > 120:
        raise HTTPException(status_code=400, detail="Tytuł: 1–120 znaków")
    if not body or len(body) > 500:
        raise HTTPException(status_code=400, detail="Treść: 1–500 znaków")

    now = datetime.utcnow()
    valid_until = request.valid_until
    if valid_until is not None and valid_until.tzinfo is not None:
        valid_until = valid_until.astimezone(tz=None).replace(tzinfo=None)
    if ann_type == "okazja":
        if not valid_until:
            raise HTTPException(status_code=400, detail="Okazja wymaga terminu ważności (valid_until)")
        if valid_until <= now:
            raise HTTPException(status_code=400, detail="Termin ważności musi być w przyszłości")
        from datetime import timedelta
        if valid_until > now + timedelta(days=OKAZJA_MAX_DAYS):
            raise HTTPException(status_code=400, detail=f"Okazja może trwać maks. {OKAZJA_MAX_DAYS} dni")

    async with async_session() as session:
        profile = await _get_owned_premium_profile(session, business_id, user)
        if not profile.is_premium:
            raise HTTPException(
                status_code=403,
                detail="Publikacja ogłoszeń dostępna w planie Firma lokalna (49 zł/mc)",
            )

        # Limit miesięczny liczony po dacie utworzenia (wycofane też się liczą —
        # inaczej limit dałoby się obejść kasowaniem)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count()).select_from(BusinessAnnouncement)
            .where(BusinessAnnouncement.business_id == business_id)
            .where(BusinessAnnouncement.type == ann_type)
            .where(BusinessAnnouncement.created_at >= month_start)
        )
        used = result.scalar() or 0
        quota = ANNOUNCEMENT_MONTHLY_QUOTA[ann_type]
        if used >= quota:
            raise HTTPException(
                status_code=429,
                detail=f"Wykorzystano miesięczny limit ({used}/{quota}) dla typu '{ann_type}'",
            )

        ann = BusinessAnnouncement(
            business_id=business_id,
            type=ann_type,
            title=title,
            body=body,
            valid_until=valid_until,
        )
        session.add(ann)
        await session.commit()
        await session.refresh(ann)
        logger.info(f"Announcement created: business={business_id} type={ann_type} by {user.email}")
        return ann


@router.delete("/announcements/{announcement_id}")
async def deactivate_announcement(
    announcement_id: int,
    user=Depends(get_current_active_user),
):
    """Wycofanie ogłoszenia (właściciel wizytówki lub admin). Soft delete."""
    async with async_session() as session:
        result = await session.execute(
            select(BusinessAnnouncement, BusinessProfile)
            .join(BusinessProfile, BusinessProfile.business_id == BusinessAnnouncement.business_id)
            .where(BusinessAnnouncement.id == announcement_id)
        )
        row = result.first()
        if not row:
            raise HTTPException(status_code=404, detail="Ogłoszenie nie zostało znalezione")
        ann, profile = row
        if profile.user_id != user.id and not user.is_admin:
            raise HTTPException(status_code=404, detail="Ogłoszenie nie zostało znalezione")

        ann.is_active = False
        session.add(ann)
        await session.commit()
        return {"status": "ok", "id": announcement_id}


@router.patch("/{business_id}/visibility")
async def set_business_visibility(
    business_id: int,
    hidden: bool = Query(..., description="True = ukryj kartę (sprzeciw RODO art. 21)"),
    user = Depends(get_admin_user),
):
    """
    Obsługa sprzeciwu wobec przetwarzania (RODO art. 21) — zgłoszenia
    przychodzą na biuro@lumargo.pl, admin ukrywa kartę firmy.
    Flaga opted_out przetrwa kolejne synchronizacje CEIDG.
    """
    async with async_session() as session:
        result = await session.execute(
            select(CEIDGBusiness).where(CEIDGBusiness.id == business_id)
        )
        business = result.scalar_one_or_none()
        if not business:
            raise HTTPException(status_code=404, detail="Firma nie została znaleziona")

        business.opted_out = hidden
        business.updated_at = datetime.utcnow()
        session.add(business)
        await session.commit()

        logger.info(
            f"Business visibility changed by admin {user.email}: "
            f"id={business_id} nip={business.nip} opted_out={hidden}"
        )
        return {"status": "ok", "id": business_id, "opted_out": hidden}


@router.get("/regon-search", response_model=List[Dict[str, Any]])
async def regon_search_proxy(
    nip: Optional[str] = None,
    regon: Optional[str] = None,
    nazwa: Optional[str] = None,
    user = Depends(get_current_active_user),
):
    """
    Wyszukiwarka live API REGON (wymaga zalogowania — ochrona przed nadużyciem proxy)
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
