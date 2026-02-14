"""
Zgłoszenie24 – Reports API Endpoints

Endpointy:
- POST /api/reports              - Nowe zgłoszenie (multipart form)
- GET  /api/reports              - Lista zgłoszeń (paginacja, filtry)
- GET  /api/reports/{id}         - Szczegóły zgłoszenia
- GET  /api/reports/map          - Zgłoszenia z GPS do mapy
- PATCH /api/reports/{id}/upvote - Głosowanie
- PATCH /api/reports/{id}/status - Zmiana statusu (admin)
"""
import os
import uuid
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlmodel import select, func, col
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session
from src.database.schema import Report, ReportStatus, ReportCategory
from src.auth.dependencies import get_optional_user
from src.utils.logger import setup_logger

logger = setup_logger("ReportsAPI")

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Upload directory
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads" / "reports"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# ==================== Response Models ====================

class ReportResponse(BaseModel):
    id: int
    title: str
    description: str
    ai_summary: Optional[str] = None
    category: str
    ai_detected_objects: Optional[Any] = None
    ai_condition_assessment: Optional[str] = None
    ai_severity: Optional[str] = None
    image_url: Optional[str] = None
    generated_image_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    location_name: Optional[str] = None
    status: str
    is_spam: bool = False
    upvotes: int = 0
    views_count: int = 0
    author_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    reports: List[ReportResponse]
    total: int
    page: int
    limit: int


class ReportMapItem(BaseModel):
    id: int
    title: str
    category: str
    ai_severity: Optional[str] = None
    latitude: float
    longitude: float
    status: str
    upvotes: int = 0
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Endpoints ====================

@router.get("/map", response_model=List[ReportMapItem])
async def get_reports_for_map(
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    """
    Zgłoszenia z koordynatami GPS do wyświetlenia na mapie.
    Zwraca tylko te z latitude/longitude.
    """
    async with async_session() as session:
        query = (
            select(Report)
            .where(Report.latitude.isnot(None))
            .where(Report.longitude.isnot(None))
            .where(Report.is_spam == False)
        )

        if category:
            query = query.where(Report.category == category)
        if status:
            query = query.where(Report.status == status)

        query = query.order_by(col(Report.created_at).desc()).limit(limit)
        result = await session.execute(query)
        reports = result.scalars().all()

        return [ReportMapItem.model_validate(r) for r in reports]


@router.get("", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = Query("newest", regex="^(newest|popular|severity)$"),
):
    """
    Lista zgłoszeń z paginacją i filtrami.
    """
    async with async_session() as session:
        # Base query - hide spam
        base_filter = Report.is_spam == False

        query = select(Report).where(base_filter)
        count_query = select(func.count()).select_from(Report).where(base_filter)

        if category:
            query = query.where(Report.category == category)
            count_query = count_query.where(Report.category == category)
        if status:
            query = query.where(Report.status == status)
            count_query = count_query.where(Report.status == status)

        # Sorting
        if sort == "popular":
            query = query.order_by(col(Report.upvotes).desc(), col(Report.created_at).desc())
        elif sort == "severity":
            query = query.order_by(col(Report.created_at).desc())  # TODO: severity ordering
        else:  # newest
            query = query.order_by(col(Report.created_at).desc())

        # Count
        total_result = await session.execute(count_query)
        total = total_result.scalar()

        # Paginate
        query = query.offset((page - 1) * limit).limit(limit)
        result = await session.execute(query)
        reports = result.scalars().all()

        return ReportListResponse(
            reports=[ReportResponse.model_validate(r) for r in reports],
            total=total,
            page=page,
            limit=limit,
        )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int):
    """Szczegóły pojedynczego zgłoszenia."""
    async with async_session() as session:
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        # Increment views
        report.views_count += 1
        session.add(report)
        await session.commit()
        await session.refresh(report)

        return ReportResponse.model_validate(report)


@router.post("", response_model=ReportResponse, status_code=201)
async def create_report(
    title: str = Form(...),
    description: str = Form(...),
    author_name: Optional[str] = Form(None),
    author_email: Optional[str] = Form(None),
    author_phone: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    location_name: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    user=Depends(get_optional_user),
):
    """
    Utwórz nowe zgłoszenie (multipart form).

    - Zdjęcie jest opcjonalne
    - Geolokalizacja dodawana przez przeglądarkę
    - AI Gemini analizuje treść i zdjęcie automatycznie
    """
    image_url = None
    image_bytes = None
    image_mime = "image/jpeg"

    # Handle image upload
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Niedozwolony format pliku. Dozwolone: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        image_bytes = await image.read()

        if len(image_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Plik jest za duży. Maksymalny rozmiar: 10MB"
            )

        # Save file
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = UPLOAD_DIR / filename
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        image_url = f"/uploads/reports/{filename}"
        image_mime = image.content_type or "image/jpeg"
        logger.info(f"Image saved: {filepath}")

    # AI Analysis
    ai_result = {
        "category": "other",
        "detected_objects": [],
        "condition": "",
        "summary": description[:200],
        "severity": "medium",
        "is_spam": False,
        "spam_reason": None,
        "suggested_title": "",
    }

    try:
        from src.ai.report_analyzer import analyze_report
        ai_result = await analyze_report(
            description=description,
            image_bytes=image_bytes,
            image_mime_type=image_mime,
        )
        logger.info(f"AI analysis complete: category={ai_result.get('category')}, spam={ai_result.get('is_spam')}")
    except Exception as e:
        logger.error(f"AI analysis failed, using defaults: {e}")

    # Create report
    report = Report(
        user_id=user.id if user else None,
        author_name=author_name or (user.full_name if user else None),
        author_email=author_email or (user.email if user else None),
        author_phone=author_phone,
        title=title,
        description=description,
        ai_summary=ai_result.get("summary"),
        category=ai_result.get("category", "other"),
        ai_detected_objects=ai_result.get("detected_objects"),
        ai_condition_assessment=ai_result.get("condition"),
        ai_severity=ai_result.get("severity"),
        image_url=image_url,
        latitude=latitude,
        longitude=longitude,
        address=address,
        location_name=location_name,
        status=ReportStatus.REJECTED.value if ai_result.get("is_spam") else ReportStatus.NEW.value,
        is_spam=ai_result.get("is_spam", False),
    )

    async with async_session() as session:
        session.add(report)
        await session.commit()
        await session.refresh(report)

        logger.info(f"Report created: id={report.id}, title='{report.title}', category={report.category}")
        return ReportResponse.model_validate(report)


@router.patch("/{report_id}/upvote", response_model=ReportResponse)
async def upvote_report(report_id: int):
    """Głosuj 'potwierdź problem' na zgłoszeniu."""
    async with async_session() as session:
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        report.upvotes += 1
        session.add(report)
        await session.commit()
        await session.refresh(report)

        return ReportResponse.model_validate(report)


@router.patch("/{report_id}/status")
async def update_report_status(
    report_id: int,
    new_status: str = Query(..., regex="^(new|verified|in_progress|resolved|rejected)$"),
    user=Depends(get_optional_user),
):
    """Zmień status zgłoszenia (admin/moderator)."""
    async with async_session() as session:
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        report.status = new_status
        report.updated_at = datetime.utcnow()

        if new_status == ReportStatus.RESOLVED.value:
            report.resolved_at = datetime.utcnow()

        session.add(report)
        await session.commit()

        return {"status": "ok", "new_status": new_status}


@router.get("/stats/summary")
async def get_reports_stats():
    """Statystyki zgłoszeń – do dashboardu."""
    async with async_session() as session:
        # Total
        total_result = await session.execute(
            select(func.count()).select_from(Report).where(Report.is_spam == False)
        )
        total = total_result.scalar()

        # By status
        status_query = (
            select(Report.status, func.count(Report.id))
            .where(Report.is_spam == False)
            .group_by(Report.status)
        )
        status_result = await session.execute(status_query)
        by_status = {row[0]: row[1] for row in status_result.all()}

        # By category
        category_query = (
            select(Report.category, func.count(Report.id))
            .where(Report.is_spam == False)
            .group_by(Report.category)
        )
        category_result = await session.execute(category_query)
        by_category = {row[0]: row[1] for row in category_result.all()}

        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
        }


@router.post("/reanalyze-all")
async def reanalyze_all_reports():
    """
    Re-analyze ALL existing reports with the current AI prompt.
    Updates category, severity, and summary for each report.
    Use this after updating the AI prompt to fix miscategorized reports.
    """
    from src.ai.report_analyzer import analyze_report

    updated = 0
    errors = 0
    results = []

    async with async_session() as session:
        query = select(Report).where(Report.is_spam == False)
        result = await session.execute(query)
        reports = result.scalars().all()

        for report in reports:
            try:
                # Re-analyze with current prompt
                image_bytes = None
                image_mime = "image/jpeg"

                # Try to load the image if it exists
                if report.image_url:
                    image_path = Path(__file__).parent.parent.parent.parent / report.image_url.lstrip("/")
                    if image_path.exists():
                        with open(image_path, "rb") as f:
                            image_bytes = f.read()
                        if str(image_path).lower().endswith(".png"):
                            image_mime = "image/png"

                ai_result = await analyze_report(
                    description=report.description,
                    image_bytes=image_bytes,
                    image_mime_type=image_mime,
                )

                old_cat = report.category
                old_sev = report.ai_severity

                report.category = ai_result.get("category", "other")
                report.ai_severity = ai_result.get("severity", "medium")
                report.ai_summary = ai_result.get("summary", report.ai_summary)
                report.ai_detected_objects = ai_result.get("detected_objects")
                report.ai_condition_assessment = ai_result.get("condition")
                report.updated_at = datetime.utcnow()

                session.add(report)
                updated += 1

                results.append({
                    "id": report.id,
                    "title": report.title,
                    "old_category": old_cat,
                    "new_category": report.category,
                    "old_severity": old_sev,
                    "new_severity": report.ai_severity,
                    "changed": old_cat != report.category or old_sev != report.ai_severity,
                })

                logger.info(
                    f"Re-analyzed report #{report.id}: "
                    f"{old_cat}→{report.category}, {old_sev}→{report.ai_severity}"
                )

            except Exception as e:
                errors += 1
                logger.error(f"Failed to re-analyze report #{report.id}: {e}")

        await session.commit()

    return {
        "status": "ok",
        "total_reports": updated + errors,
        "updated": updated,
        "errors": errors,
        "results": results,
    }


# ==================== Fix existing reports (no API calls) ====================

LOCALITY_COORDS = {
    'Rybno': (53.3904, 19.8400),
    'Hartowiec': (53.3716, 19.7821),
    'Rumian': (53.4155, 19.8063),
    'Żabiny': (53.3502, 19.8555),
    'Koszelewki': (53.3990, 19.8751),
    'Jeżewo': (53.4056, 19.7635),
    'Dłutowo': (53.3660, 19.8200),
    'Fijewo': (53.3835, 19.8750),
    'Grodziczno': (53.3350, 19.8310),
    'Jamiełnik': (53.3550, 19.8110),
    'Koszelewy': (53.3940, 19.8520),
    'Lewałd Wielki': (53.4100, 19.8380),
    'Litwa': (53.3750, 19.7950),
    'Naguszewo': (53.3615, 19.8660),
    'Olszewko': (53.3450, 19.8400),
    'Ostaszewo': (53.3800, 19.8620),
    'Radomno': (53.3700, 19.8450),
    'Ruda': (53.3560, 19.8290),
    'Słup': (53.3490, 19.8150),
    'Starczówek': (53.3860, 19.7740),
    'Szreńsk': (53.3600, 19.7800),
    'Trzonki': (53.3950, 19.8150),
    'Zwiniarz': (53.4000, 19.7900),
    'Działdowo': (53.2375, 20.1688),
    'Lidzbark': (53.2619, 19.8285),
    'Iłowo-Osada': (53.1979, 20.2618),
    'Płośnica': (53.3180, 20.0670),
    'Kozłowo': (53.5075, 20.4055),
}

EMERGENCY_KEYWORDS = [
    "wypadek", "wypadku", "wypadkiem", "wypadki",
    "tonięcie", "tonie", "tonął", "utonięcie", "utonął", "utonęła",
    "poszkodowany", "poszkodowanych", "poszkodowana",
    "ranny", "ranna", "rannych", "ranni",
    "zawalenie", "zawalił", "zawaliła",
    "karetka", "pogotowie", "reanimacja",
    "kolizja", "kolizji", "zderzenie", "potrącenie", "potrącił",
    "wyciek gazu", "eksplozja", "wybuch",
    "wypadek samochodowy", "wypadek drogowy",
    "wypadek na wodzie", "możliwe utonięcie",
]

FIRE_KEYWORDS = [
    "pożar", "pożaru", "pożarem",
    "pali się", "płonie", "ogień", "ogniem",
    "podpalenie", "podpalono",
    "dym", "dymi się", "dymiło", "zadymienie",
    "wypalanie", "wypalają",
    "pożar lasu", "pożar traw", "pożar budynku",
    "straż pożarna", "strażacy",
]


@router.post("/fix-existing")
async def fix_existing_reports():
    """
    Fix existing reports in-place (NO Gemini API calls).
    - Updates categories based on keyword matching (wypadek→emergency, pożar→fire)
    - Adds GPS coordinates from location_name using built-in lookup table
    - Adjusts severity for emergency/fire categories
    """
    fixed = []

    async with async_session() as session:
        query = select(Report).where(Report.is_spam == False)
        result = await session.execute(query)
        reports = result.scalars().all()

        for report in reports:
            changes = {}
            desc_lower = (report.description or "").lower()
            title_lower = (report.title or "").lower()
            text = f"{desc_lower} {title_lower}"

            old_cat = report.category
            old_sev = report.ai_severity

            # ── Fix category from keywords ──
            if report.category not in ("emergency",):
                for kw in EMERGENCY_KEYWORDS:
                    if kw in text:
                        report.category = "emergency"
                        report.ai_severity = "critical"
                        changes["category"] = f"{old_cat} → emergency"
                        changes["severity"] = f"{old_sev} → critical"
                        changes["keyword"] = kw
                        break

            if report.category not in ("emergency", "fire"):
                for kw in FIRE_KEYWORDS:
                    if kw in text:
                        report.category = "fire"
                        if report.ai_severity not in ("high", "critical"):
                            report.ai_severity = "high"
                        changes["category"] = f"{old_cat} → fire"
                        changes["severity"] = f"{old_sev} → {report.ai_severity}"
                        changes["keyword"] = kw
                        break

            # ── ALWAYS set GPS from location_name (override browser GPS) ──
            if report.location_name:
                coords = LOCALITY_COORDS.get(report.location_name)
                if coords:
                    old_lat = report.latitude
                    old_lng = report.longitude
                    report.latitude = coords[0]
                    report.longitude = coords[1]
                    changes["gps_set"] = f"{report.location_name} → ({coords[0]}, {coords[1]}) [was: ({old_lat}, {old_lng})]"

            # ── If still no GPS or no location_name, try to match from address ──
            if report.address:
                for loc_name, coords in LOCALITY_COORDS.items():
                    if loc_name.lower() in (report.address or "").lower():
                        old_lat = report.latitude
                        old_lng = report.longitude
                        report.latitude = coords[0]
                        report.longitude = coords[1]
                        changes["gps_from_address"] = f"{loc_name} → ({coords[0]}, {coords[1]}) [was: ({old_lat}, {old_lng})]"
                        break

            if changes:
                report.updated_at = datetime.utcnow()
                session.add(report)
                fixed.append({
                    "id": report.id,
                    "title": report.title,
                    **changes,
                })
                logger.info(f"Fixed report #{report.id}: {changes}")

        await session.commit()

    return {
        "status": "ok",
        "total_fixed": len(fixed),
        "fixes": fixed,
    }
