"""
Main scheduler using APScheduler
Manages all periodic tasks
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
import atexit

from src.scheduler.weather_job import run_weather_job
from src.scheduler.article_job import run_article_job
from src.scheduler.ai_jobs import run_ai_job
from src.scheduler.summary_job import run_summary_job
from src.scheduler.gus_job import run_gus_job
from src.scheduler.cinema_job import run_cinema_job
from src.scheduler.newsletter_job import run_weekly_newsletter, run_daily_newsletter
from src.scheduler.air_quality_job import update_air_quality
from src.scheduler.ceidg_job import run_ceidg_job
from src.utils.logger import setup_logger

logger = setup_logger("Scheduler")

# Initialize scheduler
scheduler = BackgroundScheduler()


def _job_executed_listener(event):
    """Log successful job executions"""
    logger.info(f"✓ Job '{event.job_id}' executed successfully")


def _job_error_listener(event):
    """Log job errors with traceback"""
    logger.error(f"✗ Job '{event.job_id}' raised exception: {event.exception}", exc_info=True)


def _job_missed_listener(event):
    """Log missed job executions"""
    logger.warning(f"⚠ Job '{event.job_id}' missed its scheduled run time")


def start_scheduler():
    """
    Start all scheduled jobs

    DAILY PIPELINE (1x per day at 6:00 AM):
    1. Article Scraping (6:00) - fetch new articles from sources
    2. AI Processing (6:15) - categorize articles (processed=True)
    3. Daily Summary (6:45) - generate summary for yesterday (requires processed articles)

    This sequence ensures articles are scraped AND processed before summary generation.
    """

    # Weather update every hour
    scheduler.add_job(
        func=run_weather_job,
        trigger=IntervalTrigger(hours=1),
        id='weather_update',
        name='Update weather data',
        replace_existing=True
    )

    # Air Quality update every 4 hours (Airly API limits)
    scheduler.add_job(
        func=update_air_quality,
        trigger=IntervalTrigger(hours=4),
        id='air_quality_update',
        name='Update Air Quality (Airly)',
        replace_existing=True
    )

    # Article scraping once daily at 6:00 AM (STEP 1 of daily pipeline)
    scheduler.add_job(
        func=run_article_job,
        trigger=CronTrigger(hour=6, minute=0),
        id='article_update',
        name='Update articles',
        replace_existing=True
    )

    # AI processing once daily at 6:15 AM, right after scraping (STEP 2 of daily pipeline)
    # Previously ran every hour (IntervalTrigger) which caused timing issues
    scheduler.add_job(
        func=run_ai_job,
        trigger=CronTrigger(hour=6, minute=15),
        id='ai_processing',
        name='AI article processing',
        replace_existing=True
    )

    # Daily summary generation once at 6:45 AM (STEP 3 of daily pipeline)
    # Runs 30 minutes after AI processing to ensure articles are categorized
    # Generates summary for YESTERDAY (full day of data)
    scheduler.add_job(
        func=run_summary_job,
        trigger=CronTrigger(hour=6, minute=45),
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

    # CEIDG Business sync - weekly on Sunday at 3:00 AM
    # Data doesn't change often, weekly sync is sufficient
    scheduler.add_job(
        func=run_ceidg_job,
        trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
        id='ceidg_sync',
        name='Sync CEIDG businesses',
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

    # Add event listeners for job monitoring
    scheduler.add_listener(_job_executed_listener, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_job_error_listener, EVENT_JOB_ERROR)
    scheduler.add_listener(_job_missed_listener, EVENT_JOB_MISSED)

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
