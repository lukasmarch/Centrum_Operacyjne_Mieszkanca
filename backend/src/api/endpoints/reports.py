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

from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File, Form, Request
from pydantic import BaseModel
from sqlmodel import select, func, col
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session
from src.database.schema import Report, ReportStatus, ReportCategory
from src.auth.dependencies import get_optional_user, get_admin_user
from src.utils.logger import setup_logger
from src.services.time_span import to_local

logger = setup_logger("ReportsAPI")

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Statusy niewidoczne publicznie (moderacja przed publikacją)
HIDDEN_STATUSES = (ReportStatus.PENDING.value, ReportStatus.REJECTED.value)

# Upload directory
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads" / "reports"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# ==================== Geocoding Helper ====================

async def geocode_address(address: str, location_name: str = None) -> tuple:
    """
    Geocode address using Nominatim. Returns (lat, lon) or (None, None).
    First checks local LOCALITY_COORDS, then falls back to Nominatim API.
    """
    import httpx

    # First try local lookup
    if location_name and location_name in LOCALITY_COORDS:
        coords = LOCALITY_COORDS[location_name]
        logger.info(f"Geocoded '{location_name}' from local lookup: {coords}")
        return coords

    # Try Nominatim
    search_query = f"{address}, gmina Rybno, Polska" if address else None
    if not search_query:
        return (None, None)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": search_query,
                    "format": "json",
                    "limit": 1,
                    "accept-language": "pl",
                },
                headers={"User-Agent": "CentrumOperacyjneMieszkanca/1.0"},
            )
            data = resp.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                logger.info(f"Geocoded '{search_query}' via Nominatim: ({lat}, {lon})")
                return (lat, lon)
    except Exception as e:
        logger.warning(f"Nominatim geocoding failed for '{search_query}': {e}")

    return (None, None)


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
            .where(col(Report.status).notin_(HIDDEN_STATUSES))
        )

        if category:
            query = query.where(Report.category == category)
        if status and status not in HIDDEN_STATUSES:
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
        # Base query - hide spam and unmoderated/rejected reports
        query = select(Report).where(Report.is_spam == False).where(
            col(Report.status).notin_(HIDDEN_STATUSES)
        )
        count_query = select(func.count()).select_from(Report).where(
            Report.is_spam == False
        ).where(col(Report.status).notin_(HIDDEN_STATUSES))

        if category:
            query = query.where(Report.category == category)
            count_query = count_query.where(Report.category == category)
        if status and status not in HIDDEN_STATUSES:
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
async def get_report(report_id: int, user=Depends(get_optional_user)):
    """Szczegóły pojedynczego zgłoszenia. Zgłoszenia w moderacji widzi tylko admin i autor."""
    async with async_session() as session:
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        if report.status in HIDDEN_STATUSES or report.is_spam:
            is_author = user and report.user_id and report.user_id == user.id
            is_admin = user and user.is_admin
            if not (is_author or is_admin):
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

    # Geocode for precise street-level position
    # Always try Nominatim when address has a street name, even if locality GPS was sent
    if address and address.strip():
        full_address = address.strip()
        if location_name:
            full_address = f"{full_address}, {location_name}"
        geo_lat, geo_lon = await geocode_address(full_address, None)  # skip local lookup, go to Nominatim
        if geo_lat is not None:
            latitude = geo_lat
            longitude = geo_lon
            logger.info(f"Geocoded street address: '{full_address}' -> ({latitude}, {longitude})")
    
    # Fallback: if still no GPS, try locality lookup
    if (latitude is None or longitude is None) and location_name:
        geo_lat, geo_lon = await geocode_address("", location_name)
        if geo_lat is not None:
            latitude = geo_lat
            longitude = geo_lon
            logger.info(f"Geocoded from locality: '{location_name}' -> ({latitude}, {longitude})")

    # Build location context for AI
    location_context = ""
    if address:
        location_context += f"Adres: {address}"
    if location_name:
        location_context += f", Miejscowość: {location_name}"
    if latitude and longitude:
        location_context += f" (GPS: {latitude:.5f}, {longitude:.5f})"

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
            location_info=location_context or None,
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
        # Moderacja przed publikacją: nowe zgłoszenie czeka na zatwierdzenie przez admina.
        # Push o zagrożeniach wysyłany jest dopiero przy zatwierdzeniu (PATCH /status).
        status=ReportStatus.REJECTED.value if ai_result.get("is_spam") else ReportStatus.PENDING.value,
        is_spam=ai_result.get("is_spam", False),
    )

    async with async_session() as session:
        session.add(report)
        await session.commit()
        await session.refresh(report)

        logger.info(f"Report created (pending moderation): id={report.id}, title='{report.title}', category={report.category}")

        # Dzwonek do redakcji — bez niego moderacja jest tylko nazwą (22.08.2026)
        if report.status == ReportStatus.PENDING.value:
            await _notify_admin_new_report(report)

        return ReportResponse.model_validate(report)


# Nazwy kategorii po polsku — mail ma być czytelny na telefonie, bez zaglądania
# do kodu. Front trzyma własną kopię w `reportsApi.ts` (widok mieszkańca).
_CATEGORY_LABELS = {
    "emergency": "ZAGROŻENIE ŻYCIA",
    "fire": "POŻAR",
    "water": "WODA / KANALIZACJA",
    "safety": "BEZPIECZEŃSTWO",
    "infrastructure": "infrastruktura",
    "waste": "odpady",
    "greenery": "zieleń",
    "other": "inne",
}

# Kategorie, przy których cisza kosztuje najwięcej — wołają w temacie maila.
_URGENT_CATEGORIES = {"emergency", "fire", "water", "safety"}


async def _notify_admin_new_report(report: Report) -> None:
    """
    Dzwonek: mail do redakcji w chwili wpłynięcia zgłoszenia.

    22.08.2026, 11:12 — mieszkaniec zgłosił „Brak Wody" w Żabinach w dniu, w którym
    przez gminę szła nawałnica. Zgłoszenie usiadło w `pending` i nie zobaczył go
    NIKT: publikacja wymaga moderacji, a moderator nie miał skąd wiedzieć, że jest
    co moderować. To jedyny kanał działający w czasie rzeczywistym — Facebooka
    czytamy dwa razy na dobę, a awarii wody nie zgłasza żadne źródło automatyczne.
    Od uruchomienia nie dostarczył na stronę ani jednej informacji: zgłoszenie
    z 12.07 („Zalana posesja Żabiny 50") skończyło jako `rejected`, to z 22.08
    czekało w kolejce.

    Powiadomienie AUTORA o zmianie statusu istniało od początku
    (`_notify_report_author`). Brakowało dokładnie tego w drugą stronę.

    Fire-and-forget: błąd wysyłki nie może wywrócić przyjęcia zgłoszenia —
    mieszkaniec ma dostać potwierdzenie nawet wtedy, gdy poczta leży.
    """
    try:
        from src.config import settings
        from src.newsletter.email_service import EmailService

        admin_email = getattr(settings, "ADMIN_ALERT_EMAIL", None)
        if not admin_email:
            logger.warning("Nowe zgłoszenie bez dzwonka — brak ADMIN_ALERT_EMAIL")
            return

        category = (report.category or "other").lower()
        label = _CATEGORY_LABELS.get(category, category)
        pilne = category in _URGENT_CATEGORIES
        kiedy = f"{to_local(report.created_at):%H:%M}" if report.created_at else "teraz"

        kontakt = " · ".join(filter(None, [
            report.author_name,
            report.author_email,
            report.author_phone,
        ])) or "zgłoszenie anonimowe"

        subject = (
            f"{'🔴 PILNE · ' if pilne else ''}Nowe zgłoszenie: {report.title} "
            f"({report.location_name or 'bez lokalizacji'})"
        )
        html = f"""
        <div style="font-family:sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:{'#dc2626' if pilne else '#1d4ed8'};margin-bottom:4px">
            Zgłoszenia 24 · nowe zgłoszenie
          </h2>
          <p style="color:#64748b;font-size:13px;margin-top:0">
            {label} · wpłynęło o {kiedy}
          </p>
          <div style="background:#f1f5f9;padding:16px;border-radius:8px;
                      border-left:4px solid {'#dc2626' if pilne else '#1d4ed8'}">
            <strong style="font-size:16px">{report.title}</strong><br>
            <span style="color:#334155">{report.description or ''}</span><br>
            <span style="color:#64748b;font-size:13px">
              📍 {report.location_name or report.address or 'brak lokalizacji'}
            </span>
          </div>
          <p style="font-size:13px;color:#64748b">Zgłaszający: {kontakt}</p>
          <p style="background:#fef3c7;padding:12px 16px;border-radius:8px;font-size:14px">
            ⚠️ Zgłoszenie jest <strong>niewidoczne na stronie</strong>, dopóki go nie
            zatwierdzisz. Kolejka moderacji: zakładka <strong>Zgłoszenia 24</strong>
            na rybnolive.pl (widoczna po zalogowaniu na konto administratora).
          </p>
          <p><a href="https://rybnolive.pl/zgloszenia"
                style="color:#1d4ed8">Przejdź do moderacji →</a></p>
        </div>
        """
        await EmailService().send_email(
            to_email=admin_email,
            subject=subject,
            html_content=html,
        )
        logger.info(f"Dzwonek: zgłoszenie {report.id} ({category}) → {admin_email}")
    except Exception as e:
        logger.error(f"Dzwonek nie zadzwonił dla zgłoszenia {report.id}: {e}")


def _voter_key(request: Request, user) -> str:
    """Stabilny identyfikator głosującego: id konta albo zahaszowane IP (RODO art. 5)."""
    if user:
        return f"user:{user.id}"
    import hashlib
    from src.config import settings
    raw_ip = request.client.host if request.client else "unknown"
    salt = getattr(settings, "IP_HASH_SALT", "rybnolive-ip-salt")
    return "ip:" + hashlib.sha256(f"{salt}:{raw_ip}".encode()).hexdigest()[:40]


@router.patch("/{report_id}/upvote", response_model=ReportResponse)
async def upvote_report(
    report_id: int,
    request: Request,
    user=Depends(get_optional_user),
):
    """Głosuj 'potwierdź problem' na zgłoszeniu. Jeden głos na zgłoszenie
    na konto / adres IP (deduplikacja w report_upvotes)."""
    voter_key = _voter_key(request, user)

    async with async_session() as session:
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        if report.status in HIDDEN_STATUSES or report.is_spam:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        inserted = await session.execute(
            text("""
                INSERT INTO report_upvotes (report_id, voter_key)
                VALUES (:report_id, :voter_key)
                ON CONFLICT (report_id, voter_key) DO NOTHING
                RETURNING id
            """),
            {"report_id": report_id, "voter_key": voter_key},
        )

        if inserted.fetchone():
            report.upvotes += 1
            session.add(report)

        await session.commit()
        await session.refresh(report)

        return ReportResponse.model_validate(report)


@router.get("/moderation/pending", response_model=ReportListResponse)
async def list_pending_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_admin_user),
):
    """Zgłoszenia oczekujące na moderację (tylko admin)."""
    async with async_session() as session:
        base_filter = Report.status == ReportStatus.PENDING.value

        total_result = await session.execute(
            select(func.count()).select_from(Report).where(base_filter)
        )
        total = total_result.scalar()

        result = await session.execute(
            select(Report)
            .where(base_filter)
            .order_by(col(Report.created_at).asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        reports = result.scalars().all()

        return ReportListResponse(
            reports=[ReportResponse.model_validate(r) for r in reports],
            total=total,
            page=page,
            limit=limit,
        )


# Treści powiadomień dla autora zgłoszenia (pętla zwrotna — model Kontakt 24)
STATUS_NOTIFICATIONS = {
    "new": ("Twoje zgłoszenie jest opublikowane",
            "Redakcja zatwierdziła Twoje zgłoszenie — jest już widoczne na mapie i liście Zgłoszeń 24."),
    "verified": ("Twoje zgłoszenie zostało zweryfikowane",
                 "Redakcja potwierdziła Twoje zgłoszenie — ma teraz odznakę „Zweryfikowane”."),
    "forwarded": ("Twoje zgłoszenie przekazaliśmy do urzędu",
                  "Sprawa trafiła do Urzędu Gminy Rybno. Damy Ci znać, gdy pojawi się odpowiedź."),
    "in_progress": ("Twoja sprawa jest w realizacji",
                    "Służby zajmują się Twoim zgłoszeniem."),
    "resolved": ("Twoja sprawa została rozwiązana ✅",
                 "Zgłoszony problem został oznaczony jako rozwiązany. Dziękujemy, że działasz dla gminy!"),
    "rejected": ("Twoje zgłoszenie nie zostało opublikowane",
                 "Redakcja nie mogła zatwierdzić tego zgłoszenia (np. brak możliwości weryfikacji "
                 "lub treści niedozwolone). Możesz wysłać je ponownie z dokładniejszym opisem."),
}


async def _notify_report_author(report: Report, new_status: str) -> None:
    """E-mail do autora przy zmianie statusu — buduje nawyk wracania.
    Fire-and-forget: błąd wysyłki nigdy nie blokuje moderacji."""
    if not report.author_email or new_status not in STATUS_NOTIFICATIONS:
        return
    try:
        from src.newsletter.email_service import EmailService
        subject, body = STATUS_NOTIFICATIONS[new_status]
        html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto">
          <h2 style="color:#1d4ed8">Zgłoszenia 24 · RybnoLive</h2>
          <p>Cześć{f" {report.author_name}" if report.author_name else ""}!</p>
          <p><strong>{subject}</strong></p>
          <p>{body}</p>
          <p style="background:#f1f5f9;padding:12px 16px;border-radius:8px">
            📋 <strong>{report.title}</strong><br>
            <span style="color:#64748b;font-size:13px">{report.location_name or ""}</span>
          </p>
          <p><a href="https://rybnolive.pl" style="color:#1d4ed8">Zobacz na rybnolive.pl →</a></p>
          <p style="color:#94a3b8;font-size:12px">Otrzymujesz tę wiadomość, bo podałeś adres
          e-mail przy zgłoszeniu. Odpowiedz na tego maila, jeśli chcesz coś dodać do sprawy.</p>
        </div>
        """
        await EmailService().send_email(
            to_email=report.author_email,
            subject=f"{subject} — Zgłoszenia 24",
            html_content=html,
        )
        logger.info(f"Author notified: report={report.id} status={new_status} -> {report.author_email}")
    except Exception as e:
        logger.error(f"Author notification failed for report {report.id}: {e}")


@router.patch("/{report_id}/status")
async def update_report_status(
    report_id: int,
    new_status: str = Query(..., regex="^(new|verified|forwarded|in_progress|resolved|rejected)$"),
    user=Depends(get_admin_user),
):
    """Zmień status zgłoszenia (moderacja). Wymaga roli administratora.

    Zatwierdzenie zgłoszenia pending (→ new/verified) publikuje je;
    dla kategorii zagrożeń wysyła wtedy push do subskrybentów.
    Autor zgłoszenia (jeśli podał e-mail) dostaje powiadomienie o każdej zmianie.
    """
    async with async_session() as session:
        result = await session.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Zgłoszenie nie zostało znalezione")

        was_pending = report.status == ReportStatus.PENDING.value

        report.status = new_status
        report.updated_at = datetime.utcnow()

        if new_status == ReportStatus.RESOLVED.value:
            report.resolved_at = datetime.utcnow()

        session.add(report)
        await session.commit()
        await session.refresh(report)

        # Push o zagrożeniu dopiero po zatwierdzeniu przez moderatora
        if was_pending and new_status in (
            ReportStatus.NEW.value, ReportStatus.VERIFIED.value
        ) and report.category in [
            ReportCategory.EMERGENCY.value, ReportCategory.FIRE.value
        ]:
            try:
                from src.services.push_service import push_service
                sent = await push_service.send_emergency_alert(session, report)
                logger.info(f"Emergency push sent to {sent} subscribers for report {report.id}")
            except Exception as push_err:
                logger.error(f"Emergency push failed for report {report.id}: {push_err}")

        # Pętla zwrotna: powiadom autora o zmianie statusu
        await _notify_report_author(report, new_status)

        return {"status": "ok", "new_status": new_status}


@router.get("/stats/summary")
async def get_reports_stats():
    """Statystyki zgłoszeń – do dashboardu. Liczy tylko opublikowane zgłoszenia."""
    async with async_session() as session:
        public_filter = (Report.is_spam == False) & col(Report.status).notin_(HIDDEN_STATUSES)

        # Total
        total_result = await session.execute(
            select(func.count()).select_from(Report).where(public_filter)
        )
        total = total_result.scalar()

        # By status
        status_query = (
            select(Report.status, func.count(Report.id))
            .where(public_filter)
            .group_by(Report.status)
        )
        status_result = await session.execute(status_query)
        by_status = {row[0]: row[1] for row in status_result.all()}

        # By category
        category_query = (
            select(Report.category, func.count(Report.id))
            .where(public_filter)
            .group_by(Report.category)
        )
        category_result = await session.execute(category_query)
        by_category = {row[0]: row[1] for row in category_result.all()}

        # Licznik skuteczności: sprawy rozwiązane w ostatnich 30 dniach
        from datetime import timedelta
        resolved_result = await session.execute(
            select(func.count()).select_from(Report)
            .where(Report.status == ReportStatus.RESOLVED.value)
            .where(Report.resolved_at.isnot(None))
            .where(Report.resolved_at >= datetime.utcnow() - timedelta(days=30))
        )
        resolved_last_30d = resolved_result.scalar()

        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
            "resolved_last_30d": resolved_last_30d,
        }


@router.post("/reanalyze-all")
async def reanalyze_all_reports(user=Depends(get_admin_user)):
    """
    Re-analyze ALL existing reports with the current AI prompt.
    Updates category, severity, and summary for each report.
    Use this after updating the AI prompt to fix miscategorized reports.

    Requires Business subscription (admin only).
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
async def fix_existing_reports(user=Depends(get_admin_user)):
    """
    Fix existing reports in-place (NO Gemini API calls).
    - Updates categories based on keyword matching (wypadek→emergency, pożar→fire)
    - Adds GPS coordinates from location_name using built-in lookup table
    - Adjusts severity for emergency/fire categories

    Requires Business subscription (admin only).
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
