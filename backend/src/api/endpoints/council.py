"""
Sesje Rady Gminy — skróty obrad i bramka akceptacji.

Endpointy:
- GET  /api/council/sessions          — lista zatwierdzonych skrótów (publiczne)
- GET  /api/council/sessions/{id}     — jeden skrót z punktami i linkami `?t=`
- GET  /api/council/review/{token}    — strona akceptacji (NIC nie zmienia)
- POST /api/council/review/{token}    — publikuj albo odrzuć (przycisk ze strony)
- GET  /api/council/admin/queue       — co czeka i co się wysypało (admin JWT)
- POST /api/council/admin/{id}/{act}  — to samo co token, dla panelu (admin JWT)

**Publiczne widzą wyłącznie `status = published`.** Skrót obrad powstaje
automatycznie i do momentu akceptacji nie istnieje dla nikogo poza adminem —
powód w `scheduler/council_job.py`.

**GET na `/review/{token}` musi być czysty.** Klienty pocztowe i skanery
antyspamowe odwiedzają linki z wiadomości; gdyby publikacja siedziała pod GET-em,
skrót wyszedłby w świat, zanim ktokolwiek go przeczytał. Ta sama lekcja co przy
wypisie z newslettera.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import select

from src.auth.dependencies import get_admin_user
from src.config import settings
from src.database.connection import async_session
from src.database.schema import CouncilSession, CouncilSessionStatus
from src.services.council_store import (
    public_payload,
    render_message,
    render_review_page,
    summary_dict,
)
from src.utils.logger import setup_logger

logger = setup_logger("CouncilAPI")

router = APIRouter(prefix="/api/council", tags=["council"])

PUBLISHED = CouncilSessionStatus.PUBLISHED.value
PENDING = CouncilSessionStatus.PENDING.value


# ============================================================ publiczne

@router.get("/sessions")
async def list_sessions(limit: int = Query(12, ge=1, le=50)):
    """Zatwierdzone skróty obrad, od najnowszej sesji."""
    async with async_session() as session:
        rows = (await session.execute(
            select(CouncilSession)
            .where(CouncilSession.status == PUBLISHED)
            .order_by(CouncilSession.session_date.desc().nullslast(), CouncilSession.id.desc())
            .limit(limit)
        )).scalars().all()

    return {
        "sessions": [
            # Lista dostaje sam nagłówek i lead — punkty potrafią mieć kilka
            # kilobajtów, a na liście i tak się nie mieszczą.
            {
                **public_payload(row, with_summary=False),
                "headline": summary_dict(row).get("headline"),
                "lead": summary_dict(row).get("lead"),
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/sessions/{session_id}")
async def get_session_summary(session_id: int):
    """Pełny skrót jednej sesji: punkty, uchwały, linki do minuty w nagraniu."""
    async with async_session() as session:
        row = await session.get(CouncilSession, session_id)

    if not row or row.status != PUBLISHED:
        raise HTTPException(status_code=404, detail="Nie ma takiego skrótu sesji")
    return public_payload(row)


# ==================================================== bramka akceptacji

async def _by_token(token: str) -> Optional[CouncilSession]:
    async with async_session() as session:
        return (await session.execute(
            select(CouncilSession).where(CouncilSession.review_token == token)
        )).scalars().first()


@router.get("/review/{token}", response_class=HTMLResponse)
async def review_page(token: str, request: Request):
    """
    Strona akceptacji otwierana z maila. Sam GET niczego nie zmienia —
    decyzja zapada dopiero po kliknięciu przycisku (POST).
    """
    row = await _by_token(token)
    if not row:
        return HTMLResponse(render_message(
            "Nie znaleźliśmy tego skrótu",
            "Link jest nieprawidłowy albo skrót został już usunięty.",
        ), status_code=404)

    if row.status == PUBLISHED:
        when = (
            f" {row.published_at.strftime('%d.%m.%Y o %H:%M')}" if row.published_at else ""
        )
        return HTMLResponse(render_message(
            "Ten skrót jest już opublikowany",
            f'Sesja „{row.title}” trafiła do serwisu{when}.',
        ))
    if row.status == CouncilSessionStatus.REJECTED.value:
        return HTMLResponse(render_message(
            "Ten skrót został odrzucony",
            "Nagranie zostaje w bazie, ale skrót nie pojawi się w serwisie.",
        ))
    if row.status != PENDING or not row.summary_json:
        return HTMLResponse(render_message(
            "Skrót jeszcze nie jest gotowy",
            f"Stan przetwarzania: {row.status}. Spróbuj po następnym przebiegu joba.",
        ))

    return HTMLResponse(render_review_page(row, action_url=str(request.url)))


@router.post("/review/{token}", response_class=HTMLResponse)
async def review_decide(token: str, request: Request):
    """Publikuj albo odrzuć — wywoływane przyciskiem ze strony akceptacji."""
    form = await request.form()
    action = (form.get("action") or "").strip()
    if action not in ("publish", "reject"):
        return HTMLResponse(render_message(
            "Nie wiem, co zrobić",
            "Formularz przyszedł bez decyzji. Otwórz link z maila jeszcze raz.",
        ), status_code=422)

    async with async_session() as session:
        row = (await session.execute(
            select(CouncilSession).where(CouncilSession.review_token == token)
        )).scalars().first()

        if not row:
            return HTMLResponse(render_message(
                "Nie znaleźliśmy tego skrótu",
                "Link jest nieprawidłowy albo skrót został już usunięty.",
            ), status_code=404)
        if row.status != PENDING:
            return HTMLResponse(render_message(
                "Decyzja już zapadła",
                f'Ten skrót ma stan „{row.status}” i nie czeka na akceptację.',
            ))

        _apply_decision(row, action, reviewed_by=None)
        session.add(row)
        await session.commit()

    logger.info("Skrót sesji %s: %s (token)", row.external_id, action)

    if action == "publish":
        return HTMLResponse(render_message(
            "Opublikowane",
            "Skrót obrad jest widoczny w serwisie. Dziękujemy — to była ta minuta, "
            "która dzieli automat od redakcji.",
        ))
    return HTMLResponse(render_message(
        "Odrzucone",
        "Skrót nie pojawi się w serwisie. Nagranie i transkrypt zostają w bazie.",
    ))


def _apply_decision(row: CouncilSession, action: str, reviewed_by: Optional[int]) -> None:
    """Wspólne dla drogi tokenowej i panelu admina — jeden zestaw skutków."""
    now = datetime.utcnow()
    row.reviewed_at = now
    row.reviewed_by = reviewed_by
    if action == "publish":
        row.status = PUBLISHED
        row.published_at = now
    else:
        row.status = CouncilSessionStatus.REJECTED.value
    # Token jest jednorazowy: po decyzji przestaje otwierać cokolwiek.
    row.review_token = None


# ============================================================ panel admina

@router.get("/admin/queue")
async def admin_queue(user=Depends(get_admin_user)):
    """
    Co czeka na akceptację i co się wysypało. Do panelu administracyjnego —
    droga równoległa do linku z maila, ta sama tabela.
    """
    async with async_session() as session:
        rows = (await session.execute(
            select(CouncilSession)
            .where(CouncilSession.status.in_([PENDING, CouncilSessionStatus.ERROR.value]))
            .order_by(CouncilSession.session_date.desc().nullslast())
        )).scalars().all()

    return {
        "queue": [
            {
                **public_payload(row),
                "status": row.status,
                "quality": {
                    "quotes_total": row.quotes_total,
                    "quotes_verified": row.quotes_verified,
                    "quotes_dropped": row.quotes_dropped,
                    "timestamps_fixed": row.timestamps_fixed,
                    # Świadomie NIE nazywa się „publishable": mówi tylko tyle,
                    # że bramka nie znalazła zmyślonego cytatu. Opisy punktów
                    # nie są weryfikowane wcale.
                    "quotes_clean": row.quotes_clean,
                },
                "cost_usd": row.cost_usd,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "review_url": (
                    f"{settings.API_URL}/api/council/review/{row.review_token}"
                    if row.review_token else None
                ),
            }
            for row in rows
        ]
    }


@router.post("/admin/{session_id}/{action}")
async def admin_decide(
    session_id: int,
    action: str,
    note: Optional[str] = Query(default=None, max_length=1000),
    user=Depends(get_admin_user),
):
    """Publikacja albo odrzucenie skrótu z panelu (JWT zamiast tokenu z maila)."""
    if action not in ("publish", "reject"):
        raise HTTPException(status_code=400, detail="Dozwolone akcje: publish, reject")

    async with async_session() as session:
        row = await session.get(CouncilSession, session_id)
        if not row:
            raise HTTPException(status_code=404, detail="Nie ma takiej sesji")
        if row.status != PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sesja ma stan '{row.status}', nie czeka na akceptację",
            )

        _apply_decision(row, action, reviewed_by=user.id)
        row.review_note = note
        session.add(row)
        await session.commit()

    logger.info("Skrót sesji %s: %s (admin %s)", row.external_id, action, user.email)
    return {"id": session_id, "status": row.status}
