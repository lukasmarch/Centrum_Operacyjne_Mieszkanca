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
from src.api.weather import router as weather_router


# Auth & Users (Sprint 1)
from src.auth.routes import router as auth_router
from src.users.routes import router as users_router

# Newsletter (Sprint 2)
from src.newsletter.routes import router as newsletter_router

# GUS Stats with tier-based access (Sprint 3)
from src.api.endpoints.gus import router as gus_router

# Business / CEIDG directory (Sprint 3+)
from src.api.endpoints.business import router as business_router

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
app.include_router(weather_router)  # /api/weather/*

# Auth & Users routes (Sprint 1)
app.include_router(auth_router)  # /api/auth/*
app.include_router(users_router)  # /api/users/*

# Newsletter routes (Sprint 2)
app.include_router(newsletter_router)  # /api/newsletter/*

# GUS Stats routes (Sprint 3 - Enhanced GUS Dashboard)
app.include_router(gus_router)  # /api/stats/*

# Business / CEIDG directory routes
app.include_router(business_router)  # /api/business/*

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
    from sqlalchemy import func, or_
    
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


@app.get("/api/stats/business")
async def get_business_stats(
    year: int = None,
    session: AsyncSession = Depends(get_session)
):
    """
    Get entrepreneurship/business statistics for Powiat Działdowski

    Args:
        year: Specific year (optional, defaults to latest available)

    Returns:
        {
            "entities_regon_per_10k": float,     # Podmioty REGON na 10 tys. ludności
            "new_entities_per_10k": float,       # Nowo zarejestrowane na 10 tys. ludności
            "deregistered_per_10k": float,       # Wykreślone na 10 tys. ludności
            "micro_enterprises_share": float,    # Udział mikroprzedsiębiorstw (%)
            "deregistered_share": float,         # Udział wyrejestrowanych (%)
            "new_to_deregistered_ratio": float,  # Stosunek nowych do wyrejestrowanych (%)
            "entities_per_1k": float,            # Podmioty na 1000 ludności
            "sme_per_10k": float,                # MŚP na 10 tys. mieszkańców
            "large_entities_per_10k": float,     # Duże firmy (>49 osób) na 10 tys.
            "year": int,
            "fetched_at": datetime,
            "updated_at": datetime
        }
    """
    # Try to get from cache (database) first
    query = select(GUSStatistic).where(GUSStatistic.category == "business")

    if year:
        query = query.where(GUSStatistic.year == year)
    else:
        query = query.order_by(GUSStatistic.year.desc())

    result = await session.execute(query.limit(1))
    stat = result.scalar_one_or_none()

    if not stat:
        raise HTTPException(
            status_code=404,
            detail=f"No business statistics found{' for year ' + str(year) if year else ''}. Data is updated daily at 6:00 AM. Run POST /api/stats/update to fetch data."
        )

    # Return data from JSONB + metadata
    response = stat.data.copy()
    response["fetched_at"] = stat.fetched_at
    response["updated_at"] = stat.updated_at

    return response


# ==================== NOWE ENDPOINTY DLA GMINY RYBNO (Z CACHE W BAZIE) ====================

# Słownik zmiennych GUS
# Słownik zmiennych GUS
GUS_VARIABLES = {
    "60530": {"name": "Podmioty REGON na 10 tys. ludności", "key": "entities_regon_per_10k", "category": "business"},
    "60529": {"name": "Nowe firmy na 10 tys. ludności", "key": "new_entities_per_10k", "category": "business"},
    "60528": {"name": "Wykreślone firmy na 10 tys. ludności", "key": "deregistered_per_10k", "category": "business"},
    "72305": {"name": "Ludność ogółem", "key": "population_total", "category": "demographics"},
    "59":    {"name": "Urodzenia żywe", "key": "births_live", "category": "demographics"},
    "76450": {"name": "Wydatki inwestycyjne gmin (zł)", "key": "investment_expenditure", "category": "finance"}
}


@app.post("/api/stats/sync-gus")
async def sync_gus_data(session: AsyncSession = Depends(get_session)):
    """
    Synchronizuj dane GUS z API do bazy danych.
    Uruchom raz miesięcznie lub po pierwszym deploy.
    Pobiera dane dla wszystkich gmin i zmiennych.
    """
    from src.integrations.gus_api import GUSDataService
    from src.database.schema import GUSGminaStats
    from datetime import datetime

    service = GUSDataService()
    synced = {"gminy": 0, "records": 0, "errors": []}

    try:
        for gmina_name, unit_id in service.GMINY.items():
            for var_id, var_info in GUS_VARIABLES.items():
                try:
                    # Pobierz dane z GUS API (ostatnie 10 lat)
                    data = await service.get_gmina_stats(unit_id, var_id, years_back=10)
                    
                    for val in data.get("values", []):
                        if val["value"] is None:
                            continue
                            
                        # Upsert do bazy
                        result = await session.execute(
                            select(GUSGminaStats).where(
                                GUSGminaStats.unit_id == unit_id,
                                GUSGminaStats.var_id == var_id,
                                GUSGminaStats.year == val["year"]
                            )
                        )
                        existing = result.scalar_one_or_none()
                        
                        if existing:
                            existing.value = val["value"]
                            existing.fetched_at = datetime.utcnow()
                        else:
                            session.add(GUSGminaStats(
                                unit_id=unit_id,
                                unit_name=gmina_name,
                                var_id=var_id,
                                var_name=var_info["name"],
                                year=val["year"],
                                value=val["value"],
                                category=var_info["category"],
                                fetched_at=datetime.utcnow()
                            ))
                        synced["records"] += 1
                        
                except Exception as e:
                    synced["errors"].append(f"{gmina_name}/{var_id}: {str(e)}")
            
            synced["gminy"] += 1
        
        await session.commit()
        return {
            "message": f"Synced {synced['records']} records for {synced['gminy']} gminy",
            "details": synced
        }
        
    except Exception as e:
        await session.rollback()
        raise HTTPException(500, f"Sync failed: {str(e)}")


# NOTE: Endpointy /api/stats/trend i /api/stats/comparison przeniesione
# do router /api/stats w src/api/endpoints/gus.py
# Nowe endpointy pobierają dane bezpośrednio z API GUS (bez cache)

# @app.get("/api/stats/trend/{var_id}")
# async def get_historical_trend(...):
#     """ZAKOMENTOWANE - użyj endpointu z gus.py router"""

# @app.get("/api/stats/comparison/{var_id}")
# async def get_comparative_stats(...):
#     """ZAKOMENTOWANE - użyj endpointu z gus.py router"""


@app.get("/api/stats/variables")
async def get_available_variables():
    """
    Get list of available GUS variable IDs with descriptions
    """
    from src.integrations.gus_api import GUSDataService

    return {
        "variables": {info["key"]: {"id": var_id, "name": info["name"]} for var_id, info in GUS_VARIABLES.items()},
        "gminy": GUSDataService.GMINY
    }


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
        business = await service.get_business_stats()

        current_year = datetime.now().year

        # Upsert demographics
        demo_year = int(demographics.get("year") or current_year)
        result = await session.execute(
            select(GUSStatistic)
            .where(
                GUSStatistic.category == "demographics",
                GUSStatistic.year == demo_year
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
                year=demo_year,
                data=demographics,
                population_total=demographics.get("total")
            )
            session.add(demo_stat)

        # Upsert employment
        emp_year = int(employment.get("year") or current_year)
        result = await session.execute(
            select(GUSStatistic)
            .where(
                GUSStatistic.category == "employment",
                GUSStatistic.year == emp_year
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
                year=emp_year,
                data=employment,
                unemployment_rate=employment.get("unemployment_rate")
            )
            session.add(emp_stat)

        # Upsert business
        biz_year = int(business.get("year") or current_year)
        result = await session.execute(
            select(GUSStatistic)
            .where(
                GUSStatistic.category == "business",
                GUSStatistic.year == biz_year
            )
        )
        biz_stat = result.scalar_one_or_none()

        if biz_stat:
            biz_stat.data = business
            biz_stat.updated_at = datetime.utcnow()
        else:
            biz_stat = GUSStatistic(
                category="business",
                year=biz_year,
                data=business,
            )
            session.add(biz_stat)

        await session.commit()
        await session.refresh(demo_stat)
        await session.refresh(emp_stat)
        await session.refresh(biz_stat)

        return {
            "message": "GUS statistics updated successfully",
            "demographics": demographics,
            "employment": employment,
            "business": business
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update GUS statistics: {str(e)}"
        )

