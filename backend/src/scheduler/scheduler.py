"""
Main scheduler using APScheduler
Manages all periodic tasks
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
import atexit
import traceback
import threading
from datetime import datetime, timedelta

from src.scheduler.weather_job import run_weather_job
from src.scheduler.article_job import run_article_job
from src.scheduler.ai_jobs import run_ai_job
from src.scheduler.summary_job import run_summary_job
from src.scheduler.gus_job import run_gus_job
from src.scheduler.cinema_job import run_cinema_job
from src.scheduler.traffic_job import run_traffic_job
from src.scheduler.newsletter_job import run_weekly_newsletter, run_daily_newsletter
from src.scheduler.air_quality_job import run_air_quality_job
from src.scheduler.ceidg_job import run_ceidg_job
from src.scheduler.embedding_job import run_embedding_job
from src.scheduler.places_job import run_places_job
from src.scheduler.health_job import run_health_job
from src.scheduler.proactive_alerts_job import run_proactive_alerts
from src.scheduler.trial_expiry_job import run_trial_expiry
from src.utils.logger import setup_logger

logger = setup_logger("Scheduler")

# Initialize scheduler with Polish timezone
scheduler = BackgroundScheduler(timezone='Europe/Warsaw')

# Rate limit state: {job_id: datetime_last_sent}
# Moduł-poziomowy singleton — przeżywa wszystkie wywołania listenerów w procesie
_alert_last_sent: dict = {}
_alert_lock = threading.Lock()


def _send_admin_alert(job_id: str, exception: Exception, traceback_str: str) -> None:
    """
    Wyślij email do admina gdy job schedulera crasha.

    SYNC — wywoływana z wątku APScheduler (nie może używać async/await).
    Rate limit: max 1 email/job/ADMIN_ALERT_RATE_LIMIT_HOURS godzin.
    Połyka wszystkie wyjątki — awaria alertu nie może wpłynąć na scheduler.
    """
    try:
        from src.config import settings

        if not settings.ADMIN_ALERT_EMAIL:
            return
        if not settings.RESEND_API_KEY:
            logger.warning("ADMIN_ALERT_EMAIL ustawiony ale brak RESEND_API_KEY — alert pominięty")
            return

        now = datetime.now()
        rate_limit = timedelta(hours=settings.ADMIN_ALERT_RATE_LIMIT_HOURS)

        with _alert_lock:
            last_sent = _alert_last_sent.get(job_id)
            if last_sent and (now - last_sent) < rate_limit:
                logger.debug(
                    f"Alert rate-limited dla '{job_id}' "
                    f"(następny po {(last_sent + rate_limit).strftime('%H:%M:%S')})"
                )
                return
            # Zapisz PRZED wysyłką — ochrona przy Resend timeout (nie zalewa API przy awarii Resend)
            _alert_last_sent[job_id] = now

        exc_type = type(exception).__name__
        exc_message = str(exception)
        tb_snippet = traceback_str[-2000:] if len(traceback_str) > 2000 else traceback_str
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        subject = f"[ALERT] Scheduler job '{job_id}' crashed — {exc_type}"
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: monospace; background: #f5f5f5; padding: 20px; color: #222; }}
    .card {{ background: #fff; border-left: 4px solid #d32f2f; padding: 20px;
             border-radius: 4px; max-width: 700px; }}
    h2 {{ color: #d32f2f; margin-top: 0; font-size: 18px; }}
    .label {{ color: #666; font-size: 12px; text-transform: uppercase; margin: 12px 0 4px; }}
    .value {{ background: #f0f0f0; padding: 8px 12px; border-radius: 3px; word-break: break-all; }}
    pre {{ background: #1e1e1e; color: #f8f8f2; padding: 16px; border-radius: 4px;
           font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
    .footer {{ margin-top: 20px; font-size: 11px; color: #999; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Scheduler Job Failed</h2>
    <div class="label">Job ID</div>
    <div class="value">{job_id}</div>
    <div class="label">Exception Type</div>
    <div class="value">{exc_type}</div>
    <div class="label">Message</div>
    <div class="value">{exc_message}</div>
    <div class="label">Timestamp</div>
    <div class="value">{timestamp}</div>
    <div class="label">Traceback (ostatnie 2000 znaków)</div>
    <pre>{tb_snippet}</pre>
    <div class="footer">
      Centrum Operacyjne Mieszkańca — Automated Alert<br>
      Rate limit: 1 alert / {settings.ADMIN_ALERT_RATE_LIMIT_HOURS}h per job
    </div>
  </div>
</body>
</html>"""

        import resend as resend_lib
        resend_lib.api_key = settings.RESEND_API_KEY
        resend_lib.Emails.send({
            "from": f"{settings.NEWSLETTER_FROM_NAME} <{settings.NEWSLETTER_FROM_EMAIL}>",
            "to": [settings.ADMIN_ALERT_EMAIL],
            "subject": subject,
            "html": html_body,
        })
        logger.info(
            f"Admin alert wysłany dla '{job_id}' ({exc_type}) → {settings.ADMIN_ALERT_EMAIL}"
        )

    except Exception as alert_exc:
        # CRITICAL: nigdy nie propaguj błędu alertu — log i połknij
        logger.error(f"Błąd wysyłki alertu admina dla '{job_id}': {alert_exc}")


def _job_executed_listener(event):
    """Log successful job executions"""
    logger.info(f"✓ Job '{event.job_id}' executed successfully")


def _job_error_listener(event):
    """Log job errors with traceback and send admin alert"""
    tb_str = (
        "".join(traceback.format_tb(event.traceback))
        if event.traceback else "(brak traceback)"
    )
    logger.error(
        f"✗ Job '{event.job_id}' raised {type(event.exception).__name__}: {event.exception}\n{tb_str}"
    )
    _send_admin_alert(
        job_id=event.job_id,
        exception=event.exception,
        traceback_str=tb_str,
    )


def _job_missed_listener(event):
    """Log missed job executions"""
    logger.warning(f"⚠ Job '{event.job_id}' missed its scheduled run time")


def start_scheduler():
    """
    Start all scheduled jobs

    DAILY PIPELINE (1x per day at 6:00 AM):
    1. Article Scraping (6:00) - fetch new articles from sources
    2. AI Processing (6:15) - categorize up to 100 articles (processed=True, ~32 min)
    3. Daily Summary (7:00) - generate summary for yesterday (requires processed articles)

    This sequence ensures articles are scraped AND fully processed before summary generation.
    Summary runs at 7:00 to allow AI processing to complete (batch=100 takes ~32 minutes).
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
        func=run_air_quality_job,
        trigger=IntervalTrigger(hours=4),
        id='air_quality_update',
        name='Update Air Quality (Airly)',
        replace_existing=True
    )

    # Traffic cache update every 4 hours (Gemini API - kosztowne)
    # Runs at: 2:00, 6:00, 10:00, 14:00, 18:00, 22:00 (6 calls/day)
    scheduler.add_job(
        func=run_traffic_job,
        trigger=CronTrigger(hour='2,6,10,14,18,22', minute=0),
        id='traffic_update',
        name='Update Traffic Cache (Gemini)',
        replace_existing=True
    )

    # Article scraping once daily at 6:00 AM PL time (STEP 1 of daily pipeline)
    scheduler.add_job(
        func=run_article_job,
        trigger=CronTrigger(hour=6, minute=0),
        id='article_update',
        name='Update articles',
        replace_existing=True
    )

    # AI processing once daily at 6:15 AM PL time (STEP 2 of daily pipeline)
    # Processes up to 100 articles (batch_size=100), takes ~32 minutes
    scheduler.add_job(
        func=run_ai_job,
        trigger=CronTrigger(hour=6, minute=15),
        id='ai_processing',
        name='AI article processing (batch=100)',
        replace_existing=True
    )

    # Embedding job at 6:50 AM PL time (STEP 2.5 - po AI processing)
    scheduler.add_job(
        func=run_embedding_job,
        trigger=CronTrigger(hour=6, minute=50),
        id='embedding_update',
        name='Embed new articles for RAG (text-embedding-3-small)',
        replace_existing=True
    )

    # Daily summary generation at 7:00 AM PL time (STEP 3 of daily pipeline)
    # Runs 45 minutes after AI processing to ensure all articles are categorized
    scheduler.add_job(
        func=run_summary_job,
        trigger=CronTrigger(hour=7, minute=0),
        id='daily_summary',
        name='Generate daily summary',
        replace_existing=True
    )

    # GUS statistics update quarterly (Jan, Apr, Jul, Oct) at 4:00 AM
    # Data publikowane raz na rok, quarterly refresh wystarczy
    scheduler.add_job(
        func=run_gus_job,
        trigger=CronTrigger(month='1,4,7,10', day=1, hour=4, minute=0),
        id='gus_update',
        name='Update GUS statistics (quarterly)',
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

    # Local Places update — weekly on Monday at 5:00 AM (Gemini Maps grounding)
    scheduler.add_job(
        func=run_places_job,
        trigger=CronTrigger(day_of_week='mon', hour=5, minute=0),
        id='places_update',
        name='Update local places (Gemini Maps)',
        replace_existing=True
    )

    # Health schedules update — weekly on Monday at 6:30 AM
    scheduler.add_job(
        func=run_health_job,
        trigger=CronTrigger(day_of_week='mon', hour=6, minute=30),
        id='health_update',
        name='Update health schedules (clinics + pharmacies)',
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

    # Daily Newsletter (Premium) - Mon-Fri at 7:15 AM (Sprint 2)
    # Runs AFTER daily summary (7:00) to ensure AI processing is complete
    # Timeline: scraping (6:00) → AI (6:15, ~32min) → summary (7:00) → newsletter (7:15)
    scheduler.add_job(
        func=run_daily_newsletter,
        trigger=CronTrigger(day_of_week='mon-fri', hour=7, minute=15),
        id='newsletter_daily',
        name='Send daily newsletter (Premium)',
        replace_existing=True
    )

    # Proactive AI Asystent — codziennie o 6:50 (po summary 6:45, przed newsletterem 7:15)
    # Wysyła spersonalizowane push dla Premium: wywóz śmieci, mróz, awarie, BIP
    scheduler.add_job(
        func=run_proactive_alerts,
        trigger=CronTrigger(hour=6, minute=50),
        id='proactive_alerts',
        name='Proactive AI Asystent (Premium push)',
        replace_existing=True
    )

    # Trial Expiry — codziennie o 5:00, downgrade wygasłych triali do Free
    scheduler.add_job(
        func=run_trial_expiry,
        trigger=CronTrigger(hour=5, minute=0),
        id='trial_expiry',
        name='Trial Expiry (downgrade to Free)',
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
