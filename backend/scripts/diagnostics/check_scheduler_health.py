#!/usr/bin/env python3
"""
Scheduler Health Check

Sprawdza status schedulera i zarejestrowanych jobów.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.scheduler.scheduler import scheduler, start_scheduler
from src.utils.logger import setup_logger

logger = setup_logger("SchedulerHealthCheck")


def check_scheduler_health():
    """Check if scheduler is running and list all jobs"""
    print("="*60)
    print("SCHEDULER HEALTH CHECK")
    print("="*60)
    print()

    # Check if scheduler is running
    if scheduler.running:
        print("✓ Scheduler is RUNNING")
    else:
        print("✗ Scheduler is NOT running")
        print("\nAttempting to start scheduler...")
        try:
            start_scheduler()
            print("✓ Scheduler started successfully")
        except Exception as e:
            print(f"✗ Failed to start scheduler: {e}")
            return

    print()
    print("="*60)
    print("REGISTERED JOBS")
    print("="*60)
    print()

    jobs = scheduler.get_jobs()
    if not jobs:
        print("⚠ No jobs registered")
        return

    for job in jobs:
        print(f"Job ID: {job.id}")
        print(f"  Name: {job.name}")
        print(f"  Trigger: {job.trigger}")
        print(f"  Next run: {job.next_run_time}")
        print()

    print("="*60)
    print(f"TOTAL JOBS: {len(jobs)}")
    print("="*60)


if __name__ == "__main__":
    check_scheduler_health()
