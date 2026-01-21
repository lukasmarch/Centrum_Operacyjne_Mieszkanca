from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, Source, Article, Weather, DailySummary, Event, GUSStatistic
from src.models import ArticleOutput
from src.integrations.weather import WeatherService
from src.scheduler.scheduler import start_scheduler
from datetime import datetime
from src.api.endpoints import cinema

# Auth & Users (Sprint 1)
from src.auth.routes import router as auth_router
from src.users.routes import router as users_router

# Newsletter (Sprint 2)
from src.newsletter.routes import router as newsletter_router

app = FastAPI(title="Centrum Operacyjne Mieszkańca API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3002", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cinema.router, prefix="/api/cinema", tags=["cinema"])

# Auth & Users routes (Sprint 1)
app.include_router(auth_router)  # /api/auth/*
app.include_router(users_router)  # /api/users/*

# Newsletter routes (Sprint 2)
app.include_router(newsletter_router)  # /api/newsletter/*

@app.on_event("startup")
async def startup_event():
    """Start scheduler on app startup"""
    start_scheduler()

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
    session: AsyncSession = Depends(get_session)
):
    # Join Article with Source to get source name
    # Sort by published_at (with NULL values last), then scraped_at as fallback
    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .order_by(
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

@app.get("/api/weather")
async def get_all_weather(session: AsyncSession = Depends(get_session)):
    """Get current weather for all locations"""
    result = await session.execute(
        select(Weather)
        .where(Weather.is_current == True)
        .order_by(Weather.fetched_at.desc())
    )
    weather_data = result.scalars().all()
    return {"weather": weather_data, "count": len(weather_data)}

@app.get("/api/weather/{location}")
async def get_weather_by_location(
    location: str,
    session: AsyncSession = Depends(get_session)
):
    """Get current weather for a specific location"""
    weather_service = WeatherService()
    weather = await weather_service.get_current_weather(session, location)

    if not weather:
        raise HTTPException(
            status_code=404,
            detail=f"Weather data not found for location: {location}"
        )

    return weather

@app.post("/api/weather/update")
async def update_weather(session: AsyncSession = Depends(get_session)):
    """Manually trigger weather update for all locations"""
    weather_service = WeatherService()
    results = await weather_service.update_all_locations(session)

    return {
        "message": "Weather updated successfully",
        "locations_updated": len(results),
        "data": results
    }

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
    """Get upcoming events"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await session.execute(
        select(Event)
        .where(Event.event_date >= today_start)
        .order_by(Event.event_date.asc())
        .limit(limit)
    )
    events = result.scalars().all()
    return events


@app.get("/api/traffic")
async def get_traffic():
    """Get real-time traffic data using Gemini Grounding"""
    from src.integrations.traffic_service import TrafficService
    service = TrafficService()
    return await service.get_traffic_data()


# ======================
# GUS Statistics Endpoints
# ======================

@app.get("/api/stats/demographics")
async def get_demographics_stats(
    year: int = None,
    session: AsyncSession = Depends(get_session)
):
    """
    Get demographic statistics for Powiat Działdowski

    Args:
        year: Specific year (optional, defaults to latest available)

    Returns:
        {
            "total": int,              # Ludność ogółem
            "working_age": int,        # W wieku produkcyjnym
            "density": float,          # Gęstość (os/km²)
            "growth": int,             # Przyrost naturalny
            "year": int,               # Rok danych
            "fetched_at": datetime,    # Kiedy pobrano z GUS
            "updated_at": datetime     # Ostatnia aktualizacja
        }
    """
    # Try to get from cache (database) first
    query = select(GUSStatistic).where(GUSStatistic.category == "demographics")

    if year:
        query = query.where(GUSStatistic.year == year)
    else:
        query = query.order_by(GUSStatistic.year.desc())

    result = await session.execute(query.limit(1))
    stat = result.scalar_one_or_none()

    if not stat:
        raise HTTPException(
            status_code=404,
            detail=f"No demographic statistics found{' for year ' + str(year) if year else ''}. Data is updated daily at 6:00 AM."
        )

    # Return data from JSONB + metadata
    response = stat.data.copy()
    response["fetched_at"] = stat.fetched_at
    response["updated_at"] = stat.updated_at

    return response


@app.get("/api/stats/employment")
async def get_employment_stats(
    year: int = None,
    session: AsyncSession = Depends(get_session)
):
    """
    Get employment/labor market statistics for Powiat Działdowski

    Args:
        year: Specific year (optional, defaults to latest available)

    Returns:
        {
            "unemployment_rate": float,    # Stopa bezrobocia (%)
            "unemployed_count": int,       # Liczba bezrobotnych
            "employed_count": int,         # Liczba pracujących
            "avg_salary": float,           # Średnie wynagrodzenie (PLN brutto)
            "year": int,                   # Rok danych
            "fetched_at": datetime,        # Kiedy pobrano z GUS
            "updated_at": datetime         # Ostatnia aktualizacja
        }
    """
    # Try to get from cache (database) first
    query = select(GUSStatistic).where(GUSStatistic.category == "employment")

    if year:
        query = query.where(GUSStatistic.year == year)
    else:
        query = query.order_by(GUSStatistic.year.desc())

    result = await session.execute(query.limit(1))
    stat = result.scalar_one_or_none()

    if not stat:
        raise HTTPException(
            status_code=404,
            detail=f"No employment statistics found{' for year ' + str(year) if year else ''}. Data is updated daily at 6:00 AM."
        )

    # Return data from JSONB + metadata
    response = stat.data.copy()
    response["fetched_at"] = stat.fetched_at
    response["updated_at"] = stat.updated_at

    return response


@app.post("/api/stats/update")
async def update_gus_statistics(session: AsyncSession = Depends(get_session)):
    """
    Manually trigger GUS statistics update

    Fetches latest data from GUS API and updates database cache.
    """
    from src.integrations.gus_api import GUSDataService

    service = GUSDataService()

    try:
        # Fetch latest data from GUS API
        demographics = await service.get_population_stats()
        employment = await service.get_employment_stats()

        current_year = datetime.now().year

        # Upsert demographics
        result = await session.execute(
            select(GUSStatistic)
            .where(
                GUSStatistic.category == "demographics",
                GUSStatistic.year == demographics.get("year", current_year)
            )
        )
        demo_stat = result.scalar_one_or_none()

        if demo_stat:
            demo_stat.data = demographics
            demo_stat.updated_at = datetime.utcnow()
            demo_stat.population_total = demographics.get("total")
        else:
            demo_stat = GUSStatistic(
                category="demographics",
                year=demographics.get("year", current_year),
                data=demographics,
                population_total=demographics.get("total")
            )
            session.add(demo_stat)

        # Upsert employment
        result = await session.execute(
            select(GUSStatistic)
            .where(
                GUSStatistic.category == "employment",
                GUSStatistic.year == employment.get("year", current_year)
            )
        )
        emp_stat = result.scalar_one_or_none()

        if emp_stat:
            emp_stat.data = employment
            emp_stat.updated_at = datetime.utcnow()
            emp_stat.unemployment_rate = employment.get("unemployment_rate")
        else:
            emp_stat = GUSStatistic(
                category="employment",
                year=employment.get("year", current_year),
                data=employment,
                unemployment_rate=employment.get("unemployment_rate")
            )
            session.add(emp_stat)

        await session.commit()
        await session.refresh(demo_stat)
        await session.refresh(emp_stat)

        return {
            "message": "GUS statistics updated successfully",
            "demographics": demographics,
            "employment": employment
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update GUS statistics: {str(e)}"
        )
