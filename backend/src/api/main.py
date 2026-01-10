from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, Source, Article, Weather
from src.models import ArticleOutput
from src.integrations.weather import WeatherService
from src.scheduler.scheduler import start_scheduler

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
