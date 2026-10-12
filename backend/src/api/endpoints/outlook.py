"""
`/api/alerts/outlook` — przegląd awarii dla belki „Prąd i woda” na pulpicie.

Logika wyboru mieszka w `services/outage_outlook.py`; tutaj tylko zapytanie
o kandydatów i kształt odpowiedzi.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import Article, get_session
from src.services import outage_outlook
from src.services.feed_policy import publishable_conditions

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Pula kandydatów: wszystko, co mogłoby jeszcze być zapowiedzią na najbliższy
# tydzień albo świeżym zgłoszeniem. Energa ogłasza planowe wyłączenia do
# dwóch tygodni wcześniej, więc okno publikacji jest szersze niż okno terminu.
CANDIDATE_DAYS = 21
CANDIDATE_LIMIT = 400


def _iso(value: Optional[datetime]) -> Optional[str]:
    # Naiwny UTC z bazy → jawne `Z`, inaczej przeglądarka czyta to jako czas lokalny
    return f"{value.isoformat()}Z" if value else None


class OutlookEntry(BaseModel):
    id: int
    title: str
    kind: str
    label: str
    places: list[str]
    start: Optional[str]
    end: Optional[str]
    ongoing: bool
    reported_at: Optional[str]
    concerns_village: bool


class OutlookResponse(BaseModel):
    village: Optional[str]
    checked_at: str
    window_days: int
    items: list[OutlookEntry]


@router.get("/outlook", response_model=OutlookResponse)
async def get_outlook(
    village: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Awarie w gminie Rybno: trwające i zapowiedziane na najbliższe
    `OUTLOOK_DAYS` dni, z flagą „dotyczy Twojej wsi”.

    Pusta lista znaczy „w komunikatach nic nie zapowiedziano” — i tylko tyle
    wolno z niej wywnioskować. Pulpit tak to formułuje.
    """
    now = datetime.utcnow()
    since = now - timedelta(days=CANDIDATE_DAYS)
    result = await session.execute(
        select(Article)
        .where(*publishable_conditions(Article, now))
        .where(or_(Article.published_at >= since, Article.event_at >= now - timedelta(days=1)))
        .order_by(Article.published_at.desc())
        .limit(CANDIDATE_LIMIT)
    )
    articles = result.scalars().all()

    items = outage_outlook.build_outlook(articles, now)
    return OutlookResponse(
        village=village,
        checked_at=_iso(now),
        window_days=outage_outlook.OUTLOOK_DAYS,
        items=[
            OutlookEntry(
                id=item.article_id,
                title=item.title,
                kind=item.kind,
                label=item.label,
                places=list(item.places),
                start=_iso(item.start),
                end=_iso(item.end),
                ongoing=item.ongoing,
                reported_at=_iso(item.reported_at),
                concerns_village=outage_outlook.concerns_village(item, village),
            )
            for item in items
        ],
    )
