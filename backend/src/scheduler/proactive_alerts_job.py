"""
Proaktywny AI Asystent — job schedulera (codziennie o 6:50)

ZASADA KANAŁÓW (brak duplikatów):
- Newsletter dzienny (email 6:30) = pełny briefing: newsy, śmietnik, BIP, pogoda
- Push proaktywny = TYLKO rzeczy pilne i nieplanowane, których newsletter nie obejmuje:
    1. Mróz < -5°C (pogoda tej nocy — pilna, time-sensitive)
    2. Nowa awaria z artykułów (ostatnie 2h — pilna, nie czeka do rana)

Śmietnik i BIP NIE są wysyłane push jeśli user ma newsletter dzienny (duplikat).
Śmietnik push → tylko dla Premium bez newslettera dziennego.

Odbiorca: Premium/Business userzy z aktywną subskrypcją push.
"""
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Set

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.core.config import settings
from src.database.schema import User, UserTier, WasteSchedule
from src.services.push_service import push_service
from src.utils.logger import setup_logger

logger = setup_logger("ProactiveAlertsJob")


async def _get_premium_user_ids(session) -> List[int]:
    """Premium/Business userzy z aktywnym kontem."""
    result = await session.execute(
        select(User.id).where(
            User.tier.in_([UserTier.PREMIUM.value, UserTier.BUSINESS.value]),
            User.is_active == True,
        )
    )
    return list(result.scalars().all())


async def _get_daily_newsletter_user_ids(session) -> Set[int]:
    """
    Userzy którzy mają aktywny newsletter dzienny (pon-pt 6:30).
    Oni już dostają briefing emailem — nie dublujemy śmietnik/BIP pushem.
    """
    from src.database.schema import NewsletterSubscriber

    result = await session.execute(
        select(NewsletterSubscriber.user_id).where(
            NewsletterSubscriber.frequency == "daily",
            NewsletterSubscriber.status == "active",
            NewsletterSubscriber.confirmed_at != None,
            NewsletterSubscriber.user_id != None,
        )
    )
    return set(result.scalars().all())


async def _send_frost_alert(session, premium_ids: List[int]) -> int:
    """
    Alert mrozowy gdy prognoza < -5°C — PILNE, time-sensitive.
    Newsletter nie obejmuje alertów pogodowych na daną noc → wysyłamy push.
    """
    from src.database.schema import Weather

    result = await session.execute(
        select(Weather).order_by(Weather.recorded_at.desc()).limit(1)
    )
    weather = result.scalar_one_or_none()
    if not weather:
        return 0

    temp = getattr(weather, 'temp_min', None) or getattr(weather, 'temperature', None)
    if temp is None or temp >= -5:
        return 0

    logger.info(f"Frost alert: temp={temp}°C → sending to {len(premium_ids)} Premium users")
    return await push_service.send_proactive_reminder(
        session=session,
        user_ids=premium_ids,
        title=f"Uwaga: mróz {temp:.0f}°C tej nocy",
        body="Możliwe silne oblodzenie dróg i chodników. Jedź ostrożnie.",
        url="/pogoda",
        icon="/icon-192.png",
    )


async def _send_emergency_article_alert(session, premium_ids: List[int]) -> int:
    """
    Nowa awaria/alert z ostatnich 2h — PILNE, nie czeka do rana.
    Newsletter wysyłany jest o 6:30 — awaria z 5:00 dotrze dopiero za 90 min.
    Push wypełnia tę lukę.
    """
    from src.database.schema import Article

    two_hours_ago = datetime.utcnow() - timedelta(hours=2)
    result = await session.execute(
        select(Article).where(
            Article.primary_category == "Awaria",
            Article.published_at >= two_hours_ago,
            Article.is_processed == True,
        ).order_by(Article.published_at.desc()).limit(1)
    )
    article = result.scalar_one_or_none()
    if not article:
        return 0

    logger.info(f"Emergency article push: {article.title[:50]}")
    return await push_service.send_proactive_reminder(
        session=session,
        user_ids=premium_ids,
        title="Nowy alert w gminie",
        body=article.title[:100],
        url="/",
        icon="/icon-alert-192.png",
    )


async def _send_waste_reminder_no_newsletter(session, premium_ids: List[int], newsletter_ids: Set[int]) -> int:
    """
    Przypomnienie o wywozię śmieci — TYLKO dla Premium bez newslettera dziennego.
    Użytkownicy z newsletterem dostają tę info w emailu → bez duplikatu.
    """
    # Odfiltruj userów mających newsletter dzienny
    target_ids = [uid for uid in premium_ids if uid not in newsletter_ids]
    if not target_ids:
        return 0

    tomorrow = date.today() + timedelta(days=1)
    day_names = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
    tomorrow_name = day_names[tomorrow.weekday()]

    result = await session.execute(
        select(WasteSchedule).where(WasteSchedule.collection_date == tomorrow)
    )
    schedules = result.scalars().all()
    if not schedules:
        return 0

    # Grupuj typy per miejscowość
    by_town: dict[str, list[str]] = {}
    for s in schedules:
        by_town.setdefault(s.town, []).append(s.waste_type)

    result2 = await session.execute(
        select(User.id, User.location).where(User.id.in_(target_ids))
    )
    users_loc = result2.all()

    total = 0
    for town, waste_types in by_town.items():
        town_lower = town.lower().strip()
        matching = [
            uid for uid, loc in users_loc
            if loc and (town_lower in loc.lower() or loc.lower() in town_lower)
        ]
        if not matching:
            continue
        types_str = " i ".join(waste_types)
        sent = await push_service.send_proactive_reminder(
            session=session,
            user_ids=matching,
            title=f"Jutro ({tomorrow_name}) wywóz śmieci",
            body=f"{types_str} — {town}",
            url="/",
            icon="/icon-192.png",
        )
        total += sent

    return total


async def run_proactive_alerts_async():
    """Główna funkcja jobu."""
    logger.info("=== Proactive Alerts Job START ===")
    start = datetime.utcnow()
    total_sent = 0

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        premium_ids = await _get_premium_user_ids(session)
        if not premium_ids:
            logger.info("Proactive: brak Premium userów")
            return

        newsletter_ids = await _get_daily_newsletter_user_ids(session)
        logger.info(f"Proactive: {len(premium_ids)} Premium, {len(newsletter_ids)} mają newsletter dzienny")

        # 1. Mróz — push do WSZYSTKICH Premium (newsletter tego nie obejmuje)
        sent = await _send_frost_alert(session, premium_ids)
        total_sent += sent

        # 2. Nowa awaria z ostatnich 2h — push do WSZYSTKICH Premium
        sent = await _send_emergency_article_alert(session, premium_ids)
        total_sent += sent

        # 3. Śmietnik jutro — TYLKO Premium bez newslettera dziennego (reszta dostaje w emailu)
        sent = await _send_waste_reminder_no_newsletter(session, premium_ids, newsletter_ids)
        total_sent += sent

    await engine.dispose()
    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"=== Proactive Alerts Job DONE: {total_sent} total, {elapsed:.1f}s ===")


def run_proactive_alerts():
    """Wrapper synchroniczny dla APScheduler."""
    asyncio.run(run_proactive_alerts_async())
