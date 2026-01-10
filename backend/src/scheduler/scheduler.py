"""
Main scheduler using APScheduler
Manages all periodic tasks
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

from src.scheduler.weather_job import run_weather_job
from src.scheduler.article_job import run_article_job
from src.scheduler.ai_jobs import run_ai_job
from src.utils.logger import setup_logger

logger = setup_logger("Scheduler")

# Initialize scheduler
scheduler = BackgroundScheduler()


def start_scheduler():
    """Start all scheduled jobs"""

    # Weather update every 15 minutes
    scheduler.add_job(
        func=run_weather_job,
        trigger=IntervalTrigger(minutes=15),
        id='weather_update',
        name='Update weather data',
        replace_existing=True
    )

    # Article update every 6 hours
    scheduler.add_job(
        func=run_article_job,
        trigger=IntervalTrigger(hours=6),
        id='article_update',
        name='Update articles',
        replace_existing=True
    )

    # AI processing every 30 minutes
    scheduler.add_job(
        func=run_ai_job,
        trigger=IntervalTrigger(minutes=30),
        id='ai_processing',
        name='AI article processing',
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
