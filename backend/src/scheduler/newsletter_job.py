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
            # Get all active weekly subscribers (confirmed only)
            result = await session.execute(
                select(NewsletterSubscriber)
                .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
                .where(NewsletterSubscriber.frequency == NewsletterFrequency.WEEKLY.value)
                .where(NewsletterSubscriber.confirmed_at.isnot(None))
            )
            subscribers = result.scalars().all()

            stats["total"] = len(subscribers)
            logger.info(f"Found {len(subscribers)} weekly subscribers")

            if not subscribers:
                logger.info("No weekly subscribers to send to")
                return stats

            # Generate newsletter content once (same for all)
            try:
                content = await generator.generate_weekly(session)
            except Exception as e:
                logger.error(f"Failed to generate weekly newsletter: {str(e)}")
                return stats

            # Send to each subscriber
            for subscriber in subscribers:
                try:
                    result = await email_service.send_weekly_newsletter(
                        to_email=subscriber.email,
                        content=content,
                        unsubscribe_token=subscriber.unsubscribe_token
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

            # Generate and send per location
            for location, subs in by_location.items():
                try:
                    content = await generator.generate_daily(session, location=location)
                    if weekly_card:
                        content["weekly_card"] = weekly_card
                except Exception as e:
                    logger.error(f"Failed to generate daily for {location}: {str(e)}")
                    continue

                for subscriber, user in subs:
                    try:
                        # Get weather temp for this location
                        from src.database import Weather
                        weather_result = await session.execute(
                            select(Weather)
                            .where(Weather.location == location)
                            .where(Weather.is_current == True)
                            .limit(1)
                        )
                        weather = weather_result.scalar_one_or_none()
                        weather_temp = weather.temperature if weather else None

                        result = await email_service.send_daily_newsletter(
                            to_email=subscriber.email,
                            content=content,
                            unsubscribe_token=subscriber.unsubscribe_token,
                            weather_temp=weather_temp
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
