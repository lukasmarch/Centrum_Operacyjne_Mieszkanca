"""
Pasek „Drogi” — decyzja redakcji o utrudnieniu (2026-10-29).

- GET  /api/roads/review/{token}?d=approve|reject — strona decyzji (NIC nie zmienia)
- POST /api/roads/review/{token}                  — Akceptuj albo Usuń

Wiadomość na Telegramie niesie dwa przyciski-linki. **GET musi być czysty** —
podglądy linków i skanery odwiedzają adresy same; decyzja zapada dopiero
przyciskiem na stronie (POST). Ten sam wzorzec co `/api/council/review`.
Po decyzji pasek zmienia się od razu (`refresh_current_cache`).
"""
import html
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select

from src.database.connection import async_session
from src.database.schema import RoadReport
from src.services.council_store import _page, render_message
from src.services.road_reports import (
    APPROVAL_HOURS,
    REJECT_DAYS,
    apply_decision,
    refresh_current_cache,
)
from src.services.time_span import to_local
from src.utils.logger import setup_logger

logger = setup_logger("RoadsAPI")

router = APIRouter(prefix="/api/roads", tags=["roads"])

_GONE = (
    "Tego zgłoszenia już nie ma",
    "Decyzja już zapadła albo model przestał je zgłaszać — wtedy i tak nie jest na pasku.",
)


async def _pending(session, token: str):
    return (await session.execute(
        select(RoadReport).where(RoadReport.review_token == token, RoadReport.status == "pending")
    )).scalars().first()


@router.get("/review/{token}", response_class=HTMLResponse)
async def review_page(token: str, request: Request, d: str = "approve"):
    async with async_session() as session:
        row = await _pending(session, token)
    if row is None:
        return HTMLResponse(render_message(*_GONE), status_code=404)

    approve = d != "reject"
    if row.origin == "search":
        source = "wyłącznie wynik z Google — w naszym feedzie tego nie ma"
    else:
        when = f", {to_local(row.source_published_at):%d.%m.%Y %H:%M}" if row.source_published_at else ""
        source = f"{row.source_name or 'feed'}{when}"
    primary = (
        f'<button class="go" type="submit" name="action" value="approve">Akceptuj — pokaż na pasku</button>'
        f'<button class="no" type="submit" name="action" value="reject">Usuń</button>'
        if approve else
        f'<button class="no" type="submit" name="action" value="reject" '
        f'style="background:#7f2b2b;color:#fff">Usuń zgłoszenie</button>'
        f'<button class="go" type="submit" name="action" value="approve" '
        f'style="background:transparent;border:1px solid #3a81f6;color:#91c5ff">Jednak akceptuj</button>'
    )
    body = (
        '<div class="card">'
        f'<div class="meta">Utrudnienie do decyzji · {html.escape(row.route.replace("Rybno-", "Rybno → "))}</div>'
        f'<h1>{html.escape(row.note)}</h1>'
        f'<p class="lead">Źródło: {html.escape(source)}</p>'
        f'<p class="lead">Wiarygodność <b>{row.score:.2f}</b> — {html.escape(row.score_reason or "")}</p>'
        f'<form method="post" action="{html.escape(request.url.path)}" class="actions">{primary}</form>'
        f'<p class="foot">Akceptacja: pasek przez {APPROVAL_HOURS} h, potem — jeśli model wciąż '
        f'to zgłasza — zapytamy znowu. Usuń: to zgłoszenie nie wróci przez {REJECT_DAYS} dni.</p>'
        '</div>'
    )
    return HTMLResponse(_page("Drogi — decyzja", body))


@router.post("/review/{token}", response_class=HTMLResponse)
async def review_decide(token: str, request: Request):
    form = await request.form()
    action = (form.get("action") or "").strip()
    if action not in ("approve", "reject"):
        return HTMLResponse(render_message(
            "Nie wiem, co zrobić", "Formularz przyszedł bez decyzji. Otwórz link z Telegramu jeszcze raz.",
        ), status_code=422)

    now = datetime.utcnow()
    async with async_session() as session:
        row = await _pending(session, token)
        if row is None:
            return HTMLResponse(render_message(*_GONE), status_code=404)
        apply_decision(row, action, now)
        await session.flush()
        await refresh_current_cache(session, now)
        await session.commit()
        route = row.route

    logger.info("Utrudnienie %s (%s): %s", row.id, route, action)
    if action == "approve":
        return HTMLResponse(render_message(
            "Na pasku", f"Utrudnienie na trasie {route} jest widoczne na stronie przez {APPROVAL_HOURS} h.",
        ))
    return HTMLResponse(render_message(
        "Usunięte", f"Zgłoszenie zniknęło z kolejki i nie wróci przez {REJECT_DAYS} dni.",
    ))
