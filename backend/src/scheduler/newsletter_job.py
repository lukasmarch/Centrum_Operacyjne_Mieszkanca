"""
Newsletter scheduler jobs - Weekly (Saturday 10:00) and Daily (Mon-Fri 7:15)
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.database import (
    NewsletterSubscriber, NewsletterLog, User,
    NewsletterFrequency, NewsletterStatus, UserTier
)
from src.newsletter.generator import NewsletterGenerator
from src.newsletter.email_service import EmailService
from src.config import settings

logger = logging.getLogger("Scheduler.Newsletter")


async def _marketing_consent(session, subscriber) -> bool:
    """Czy odbiorca ma dostać blok „Polecane firmy".

    Dwa warunki, nie jeden:
    - **zgoda** — anonimowy zapis bez konta nigdy jej nie zbiera, więc domyślnie brak;
    - **plan darmowy** — cennik sprzedaje Premium m.in. hasłem „Brak reklam",
      a do 21.08.2026 blok zależał wyłącznie od zgody. Płacący klient z zaznaczonym
      checkboxem dostałby reklamę, za której brak zapłacił.
    """
    if not subscriber.user_id:
        return False
    result = await session.execute(select(User).where(User.id == subscriber.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.consent_marketing:
        return False
    return user.tier == UserTier.FREE.value


async def send_weekly_newsletter():
    """
    Send weekly newsletter to all active 'weekly' subscribers.
    Runs every Saturday at 10:00 AM.
    """
    logger.info("Starting weekly newsletter job...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    generator = NewsletterGenerator()
    email_service = EmailService()

    stats = {
        "total": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0
    }

    try:
        async with async_session() as session:
            # Newsletter tygodniowy jest bazowy dla WSZYSTKICH subskrybentów.
            # Częstotliwość 'daily' to dodatek premium (poranny briefing Pn-Pt)
            # nakładany NA tygodniowy, nie zamiast niego — dlatego weekly wysyłamy
            # także do subskrybentów 'daily' (UI: "Newsletter tygodniowy zawsze aktywny").
            result = await session.execute(
                select(NewsletterSubscriber)
                .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
                .where(NewsletterSubscriber.confirmed_at.isnot(None))
            )
            subscribers = result.scalars().all()

            stats["total"] = len(subscribers)
            logger.info(f"Found {len(subscribers)} active confirmed subscribers for weekly newsletter")

            if not subscribers:
                logger.info("No weekly subscribers to send to")
                return stats

            # Generate newsletter content once (same for all)
            try:
                content = await generator.generate_weekly(session)
            except Exception as e:
                logger.error(f"Failed to generate weekly newsletter: {str(e)}")
                return stats

            # Sekcja „Polecane firmy" (plan Firma lokalna) — reklama w newsletterze.
            # Wyłączona flagą do czasu pierwszej sprzedaży planu.
            if settings.NEWSLETTER_ADS_ENABLED:
                from src.newsletter.promo import get_newsletter_promo
                content.update(await get_newsletter_promo(session))

            # Send to each subscriber
            for subscriber in subscribers:
                try:
                    result = await email_service.send_weekly_newsletter(
                        to_email=subscriber.email,
                        content=content,
                        unsubscribe_token=subscriber.unsubscribe_token,
                        marketing_consent=await _marketing_consent(session, subscriber),
                    )

                    if result["status"] == "sent":
                        stats["sent"] += 1

                        # Update subscriber stats
                        subscriber.emails_sent += 1
                        subscriber.last_sent_at = datetime.utcnow()

                        # Log the send
                        log = NewsletterLog(
                            subscriber_id=subscriber.id,
                            newsletter_type="weekly",
                            subject=content.get("subject", "Weekly Newsletter"),
                            status="sent"
                        )
                        session.add(log)

                    elif result["status"] == "failed":
                        stats["failed"] += 1
                        logger.error(f"Failed to send to {subscriber.email}: {result.get('error')}")

                    else:
                        stats["skipped"] += 1

                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"Error sending to {subscriber.email}: {str(e)}")

            await session.commit()
    finally:
        await engine.dispose()

    logger.info(f"Weekly newsletter job completed: {stats}")
    return stats


async def send_daily_newsletter():
    """
    Send daily newsletter to Premium subscribers.
    Runs Monday-Friday at 7:15 AM.
    """
    logger.info("Starting daily newsletter job...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    generator = NewsletterGenerator()
    email_service = EmailService()

    stats = {
        "total": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0
    }

    try:
        async with async_session() as session:
            # Get all active daily subscribers (Premium/Business only)
            result = await session.execute(
                select(NewsletterSubscriber, User)
                .join(User, NewsletterSubscriber.user_id == User.id, isouter=True)
                .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
                .where(NewsletterSubscriber.frequency == NewsletterFrequency.DAILY.value)
                .where(NewsletterSubscriber.confirmed_at.isnot(None))
            )
            rows = result.all()

            # Filter to only Premium/Business users
            premium_subscribers = []
            for subscriber, user in rows:
                if user and user.tier in [UserTier.PREMIUM.value, UserTier.BUSINESS.value]:
                    premium_subscribers.append((subscriber, user))
                elif not user:
                    # Anonymous subscriber with daily - downgrade to weekly
                    subscriber.frequency = NewsletterFrequency.WEEKLY.value
                    logger.info(f"Downgraded {subscriber.email} to weekly (no premium)")

            stats["total"] = len(premium_subscribers)
            logger.info(f"Found {len(premium_subscribers)} premium daily subscribers")

            if not premium_subscribers:
                await session.commit()
                logger.info("No premium subscribers for daily newsletter")
                return stats

            # Group by location for personalized content
            by_location = {}
            for subscriber, user in premium_subscribers:
                location = subscriber.location or user.location
                if location not in by_location:
                    by_location[location] = []
                by_location[location].append((subscriber, user))

            # On Monday: generate weekly stats card once (location-independent)
            weekly_card = None
            if datetime.utcnow().weekday() == 0:
                try:
                    weekly_card = await generator.get_weekly_stats(session)
                    logger.info("Weekly stats card generated for Monday newsletter")
                except Exception as e:
                    logger.error(f"Failed to generate weekly card: {str(e)}")

            # Briefing dzienny ma tylko odbiorców Premium/Business, a ci kupili m.in.
            # „Brak reklam" — blok „Polecane firmy" zostaje w newsletterze tygodniowym,
            # który i tak dociera do wszystkich. Ogłoszenia firm żyją poza tym w feedzie.
            promo = {}

            # Generate and send per location
            for location, subs in by_location.items():
                try:
                    content = await generator.generate_daily(session, location=location)
                    content.update(promo)
                    if weekly_card:
                        content["weekly_card"] = weekly_card
                except Exception as e:
                    logger.error(f"Failed to generate daily for {location}: {str(e)}")
                    continue

                for subscriber, user in subs:
                    try:
                        # Temperatura do nagłówka maila — ten sam fallback co w generatorze:
                        # pomiar istnieje tylko dla Rybna i Działdowa, a konto może wskazać
                        # dowolną z 24 miejscowości gminy (mieszkaniec Dębienia dostawał
                        # briefing bez pogody, bo zapytanie nie miało czego znaleźć).
                        weather = await generator._weather_for(session, location)
                        weather_temp = weather.temperature if weather else None

                        # Imię w mianowniku — tylko do powitania „Dzień dobry, X."
                        first_name = (user.full_name or "").strip().split(" ")[0] or None

                        result = await email_service.send_daily_newsletter(
                            to_email=subscriber.email,
                            content=content,
                            unsubscribe_token=subscriber.unsubscribe_token,
                            # Odbiorcą briefingu jest wyłącznie plan płatny — patrz filtr
                            # `premium_subscribers` wyżej. „Brak reklam" to część oferty.
                            marketing_consent=False,
                            weather_temp=weather_temp,
                            recipient_name=first_name
                        )

                        if result["status"] == "sent":
                            stats["sent"] += 1
                            subscriber.emails_sent += 1
                            subscriber.last_sent_at = datetime.utcnow()

                            log = NewsletterLog(
                                subscriber_id=subscriber.id,
                                newsletter_type="daily",
                                subject=content.get("subject", "Daily Briefing"),
                                status="sent"
                            )
                            session.add(log)

                        elif result["status"] == "failed":
                            stats["failed"] += 1

                        else:
                            stats["skipped"] += 1

                    except Exception as e:
                        stats["failed"] += 1
                        logger.error(f"Error sending daily to {subscriber.email}: {str(e)}")

            await session.commit()
    finally:
        await engine.dispose()

    logger.info(f"Daily newsletter job completed: {stats}")
    return stats


def run_weekly_newsletter():
    """Sync wrapper for APScheduler"""
    asyncio.run(send_weekly_newsletter())


def run_daily_newsletter():
    """Sync wrapper for APScheduler"""
    asyncio.run(send_daily_newsletter())
