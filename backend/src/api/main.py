from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, Source, Article, Weather, DailySummary, Event
from src.models import ArticleOutput
from src.integrations.weather import WeatherService
from src.scheduler.scheduler import start_scheduler
from datetime import datetime

app = FastAPI(title="Centrum Operacyjne Mieszkańca API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3002", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .order_by(Article.scraped_at.desc())
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
