"""
Main scheduler using APScheduler
Manages all periodic tasks
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import atexit

from src.scheduler.weather_job import run_weather_job
from src.scheduler.article_job import run_article_job
from src.scheduler.ai_jobs import run_ai_job
from src.scheduler.summary_job import run_summary_job
from src.scheduler.gus_job import run_gus_job
from src.scheduler.cinema_job import run_cinema_job
from src.scheduler.newsletter_job import run_weekly_newsletter, run_daily_newsletter
from src.utils.logger import setup_logger

logger = setup_logger("Scheduler")

# Initialize scheduler
scheduler = BackgroundScheduler()


def start_scheduler():
    """Start all scheduled jobs"""

    # Weather update every 15 minutes
    scheduler.add_job(
        func=run_weather_job,
        trigger=IntervalTrigger(hours=1),
        id='weather_update',
        name='Update weather data',
        replace_existing=True
    )

    # Article scraping twice daily: 6:00 AM and 12:00 PM
    scheduler.add_job(
        func=run_article_job,
        trigger=CronTrigger(hour='6,12', minute=0),
        id='article_update',
        name='Update articles',
        replace_existing=True
    )

    # AI processing every 1 hour
    scheduler.add_job(
        func=run_ai_job,
        trigger=IntervalTrigger(hours=1),
        id='ai_processing',
        name='AI article processing',
        replace_existing=True
    )

    # Daily summary generation twice: 6:30 AM and 12:30 PM (after scraping)
    scheduler.add_job(
        func=run_summary_job,
        trigger=CronTrigger(hour='6,12', minute=30),
        id='daily_summary',
        name='Generate daily summary',
        replace_existing=True
    )

    # GUS statistics update daily at 6:00 AM
    scheduler.add_job(
        func=run_gus_job,
        trigger=CronTrigger(hour=6, minute=0),
        id='gus_update',
        name='Update GUS statistics',
        replace_existing=True
    )
    
    # Cinema Repertoire update daily at 8:00 AM
    scheduler.add_job(
        func=run_cinema_job,
        trigger=CronTrigger(hour=8, minute=0),
        id='cinema_update',
        name='Update Cinema Repertoire',
        replace_existing=True
    )

    # Weekly Newsletter - Saturday at 10:00 AM (Sprint 2)
    scheduler.add_job(
        func=run_weekly_newsletter,
        trigger=CronTrigger(day_of_week='sat', hour=10, minute=0),
        id='newsletter_weekly',
        name='Send weekly newsletter',
        replace_existing=True
    )

    # Daily Newsletter (Premium) - Mon-Fri at 6:30 AM (Sprint 2)
    scheduler.add_job(
        func=run_daily_newsletter,
        trigger=CronTrigger(day_of_week='mon-fri', hour=6, minute=30),
        id='newsletter_daily',
        name='Send daily newsletter (Premium)',
        replace_existing=True
    )

    logger.info("Scheduler started with jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} ({job.id}): {job.trigger}")

    scheduler.start()

    # Ensure scheduler shuts down on exit
    atexit.register(lambda: scheduler.shutdown())


def stop_scheduler():
    """Stop scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    # Test scheduler
    import time

    print("Starting scheduler (test mode - will run for 2 minutes)...")
    start_scheduler()

    try:
        time.sleep(120)  # Run for 2 minutes
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
    finally:
        stop_scheduler()
