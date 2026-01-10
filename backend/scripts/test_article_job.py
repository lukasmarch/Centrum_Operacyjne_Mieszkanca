#!/usr/bin/env python3
"""
Test article_job - scraping wszystkich aktywnych źródeł

Uruchomienie:
    cd backend
    python scripts/test_article_job.py
"""

import asyncio
import sys
from pathlib import Path

# Dodaj backend do path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.scheduler.article_job import update_articles_job

if __name__ == "__main__":
    print("=" * 60)
    print("TEST ARTICLE JOB - Scraping wszystkich źródeł")
    print("=" * 60)
    asyncio.run(update_articles_job())
