from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, Source, Article, Weather, DailySummary, Event
from src.models import ArticleOutput
from src.integrations.weather import WeatherService
from src.scheduler.scheduler import start_scheduler
from src.config import settings
from datetime import datetime
from src.api.endpoints import cinema
from src.api.weather import router as weather_router


# Auth & Users (Sprint 1)
from src.auth.routes import router as auth_router
from src.users.routes import router as users_router

# Newsletter (Sprint 2)
from src.newsletter.routes import router as newsletter_router

# GUS Stats with tier-based access (Sprint 3)
from src.api.endpoints.gus import router as gus_router

# Polska w Liczbach — uzupełnienie danych gminnych (PwL)
from src.api.endpoints.pwl import router as pwl_router

# Business / CEIDG directory (Sprint 3+)
from src.api.endpoints.business import router as business_router

# Zgłoszenie24 – Citizen Reports (Sprint 4)
from src.api.endpoints.reports import router as reports_router

# Push Notifications (Sprint 5C)
from src.api.endpoints.push import router as push_router

# Waste Schedule (Sprint 7 - Organizator.ai)
from src.api.endpoints.waste import router as waste_router

# Health Module (Clinic Schedules + Pharmacy Duties)
from src.api.endpoints.health import router as health_router

# AI Chat + Multi-Agent System (Sprint 6)
from src.api.endpoints.chat import router as chat_router
from src.ai.agents import (
    orchestrator, RedaktorAgent, UrzednikAgent,
    GUSAnalitykAgent, PrzewodnikAgent, StraznikAgent, OrganizatorAgent
)

app = FastAPI(title="Centrum Operacyjne Mieszkańca API")

# CORS for frontend (use env var, fallback to localhost)
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else [
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://localhost:3004",
    "http://localhost:3005",
    "http://localhost:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for report uploads
from fastapi.staticfiles import StaticFiles
from pathlib import Path
uploads_dir = Path(__file__).parent.parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

app.include_router(cinema.router, prefix="/api/cinema", tags=["cinema"])
app.include_router(weather_router)  # /api/weather/*

# Auth & Users routes (Sprint 1)
app.include_router(auth_router)  # /api/auth/*
app.include_router(users_router)  # /api/users/*

# Newsletter routes (Sprint 2)
app.include_router(newsletter_router)  # /api/newsletter/*

# GUS Stats routes (Sprint 3 - Enhanced GUS Dashboard)
app.include_router(gus_router)  # /api/stats/*

# Polska w Liczbach routes — uzupełnienie gmina-poziom
app.include_router(pwl_router, prefix="/api/stats/pwl")  # /api/stats/pwl/*

# Business / CEIDG directory routes
app.include_router(business_router)  # /api/business/*

# Zgłoszenie24 – Reports routes (Sprint 4)
app.include_router(reports_router)  # /api/reports/*

# Push Notifications routes (Sprint 5C)
app.include_router(push_router)  # /api/push/*

# Waste Schedule routes (Sprint 7) - /api/waste/towns, /api/waste/schedule
app.include_router(waste_router)

# Bus Timetable routes - /api/bus/timetable, /api/bus/status
from src.api.endpoints.bus import router as bus_router
app.include_router(bus_router)

# Health routes - /api/health/today, /api/health/clinics
app.include_router(health_router)

# AI Chat routes (Sprint 6) - /api/chat/message, /api/chat/history, /api/chat/agents
app.include_router(chat_router)

# Payments - Przelewy24 + BLIK
from src.api.endpoints.payments import router as payments_router
app.include_router(payments_router)  # /api/payments/*

# SEO — sitemap.xml (no /api/ prefix, standard location for Google)
from src.api.endpoints.seo import router as seo_router
app.include_router(seo_router)

@app.on_event("startup")
async def startup_event():
    """Start scheduler and register AI agents on app startup"""
    start_scheduler()
    # Register all AI agents with the orchestrator
    for agent_cls in [RedaktorAgent, UrzednikAgent, GUSAnalitykAgent, PrzewodnikAgent, StraznikAgent, OrganizatorAgent]:
        orchestrator.register_agent(agent_cls())

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/sources")
async def get_sources(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Source))
    sources = result.scalars().all()
    return {"sources": sources}

@app.get("/api/articles", response_model=list[ArticleOutput])
async def get_articles(
    limit: int = 50,
    per_source: int = 5,
    days: int = 2,
    session: AsyncSession = Depends(get_session)
):
    """
    Get articles with filtering and grouping.
    
    Args:
        limit: Maximum total articles to return (default: 50)
        per_source: Maximum articles per source (default: 5)
        days: Only return articles from the last N days (default: 2)
    """
    from datetime import timedelta
    from sqlalchemy import func, or_, case
    
    # Calculate cutoff date (2 days ago)
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Use window function to rank articles per source
    # ROW_NUMBER() OVER (PARTITION BY source_id ORDER BY published_at DESC)
    row_number = func.row_number().over(
        partition_by=Article.source_id,
        order_by=[
            Article.published_at.desc().nulls_last(),
            Article.scraped_at.desc()
        ]
    ).label('row_num')
    
    # Subquery with row numbers
    subquery = (
        select(Article.id, row_number)
        .where(
            or_(
                Article.published_at >= cutoff_date,
                Article.scraped_at >= cutoff_date
            )
        )
        .subquery()
    )
    
    # Main query - join with subquery to filter by row_num <= per_source
    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .join(subquery, Article.id == subquery.c.id)
        .where(subquery.c.row_num <= per_source)
        .order_by(
            case((Article.category == 'Awaria', 0), else_=1),
            Article.published_at.desc().nulls_last(),
            Article.scraped_at.desc()
        )
        .limit(limit)
    )

    # Map results to ArticleOutput with source_name
    articles = []
    for article, source_name in result:
        article_dict = article.model_dump()
        article_dict['source_name'] = source_name
        articles.append(ArticleOutput(**article_dict))

    return articles



@app.get("/api/summary/daily")
async def get_latest_daily_summary(session: AsyncSession = Depends(get_session)):
    """Get the most recent daily summary"""
    result = await session.execute(
        select(DailySummary)
        .order_by(DailySummary.date.desc())
        .limit(1)
    )
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(
            status_code=404,
            detail="No daily summary found. Summaries are generated daily at 6:00 AM."
        )

    return {
        "id": summary.id,
        "date": summary.date.strftime("%Y-%m-%d"),
        "headline": summary.headline,
        "content": summary.content,
        "generated_at": summary.generated_at
    }

@app.get("/api/summary/daily/{date}")
async def get_daily_summary_by_date(
    date: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Get daily summary for a specific date

    Args:
        date: Date in format YYYY-MM-DD (e.g., "2026-01-10")
    """
    try:
        # Parse date string
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD (e.g., '2026-01-10')"
        )

    # Query for summary on that date
    result = await session.execute(
        select(DailySummary)
        .where(DailySummary.date == target_date)
    )
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No daily summary found for date: {date}"
        )

    return {
        "id": summary.id,
        "date": summary.date.strftime("%Y-%m-%d"),
        "headline": summary.headline,
        "content": summary.content,
        "generated_at": summary.generated_at
    }

@app.get("/api/events")
async def get_upcoming_events(
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    """Get upcoming events with source name (scraped from)"""
    from sqlalchemy import outerjoin
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(Event, Source.name.label("source_name"))
        .outerjoin(Article, Event.source_article_id == Article.id)
        .outerjoin(Source, Article.source_id == Source.id)
        .where(Event.event_date >= today_start)
        .order_by(Event.event_date.asc())
        .limit(limit)
    )
    rows = result.all()
    output = []
    for event, source_name in rows:
        d = event.dict()
        d["source_name"] = source_name
        output.append(d)
    return output


@app.get("/api/traffic")
async def get_traffic(session: AsyncSession = Depends(get_session)):
    """
    Get real-time traffic data from cache (refreshed every 4h by scheduler)

    Data is fetched from Gemini Grounding API and cached in database.
    Cache is refreshed every 4 hours (6:00, 10:00, 14:00, 18:00, 22:00, 2:00).
    """
    from src.database.schema import TrafficCache
    from src.integrations.traffic_service import TrafficService

    # Query latest cache entry
    result = await session.execute(
        select(TrafficCache)
        .where(TrafficCache.is_current == True)
        .order_by(TrafficCache.fetched_at.desc())
        .limit(1)
    )
    cache_entry = result.scalar_one_or_none()

    if cache_entry:
        return cache_entry.data

    # Fallback: no cache available - return static fallback data
    service = TrafficService()
    fallback_data = service._get_fallback_data()
    return fallback_data.dict()


# ======================
# Legacy GUS Statistics Endpoints - REMOVED (2026-02-17)
# ======================
# All GUS endpoints moved to src/api/endpoints/gus.py (database-first architecture)
# - OLD: /api/stats/demographics, /api/stats/employment, /api/stats/business
# - OLD: /api/stats/sync-gus, /api/stats/variables, /api/stats/update
# - NEW: /api/stats/overview, /api/stats/section/{section_key}, /api/stats/variable/{var_key}/detail
# - NEW: /api/stats/categories, /api/stats/variables/list, /api/stats/freshness
# See: backend/src/api/endpoints/gus.py (tier-based access, 88 variables, database-first)
