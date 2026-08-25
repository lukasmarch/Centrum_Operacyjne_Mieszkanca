from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, Source, Article, Weather, DailySummary, Event
from src.models import ArticleOutput
from src.integrations.weather import WeatherService
from src.scheduler.scheduler import start_scheduler
from src.config import settings
from src.utils.logger import setup_logger
from datetime import datetime, timedelta
from src.api.endpoints import cinema
from src.api.weather import router as weather_router


# Auth & Users (Sprint 1)
from src.auth.routes import router as auth_router
from src.auth.dependencies import get_admin_user
from src.users.routes import router as users_router

# Newsletter (Sprint 2)
from src.newsletter.routes import router as newsletter_router

# GUS Stats with tier-based access (Sprint 3)
from src.api.endpoints.gus import router as gus_router

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

# Social media — propozycje postów dla n8n (backend buduje treść, n8n publikuje)
from src.api.endpoints.social import router as social_router

# AI Chat + Multi-Agent System (Sprint 6)
from src.api.endpoints.chat import router as chat_router
from src.ai.agents import (
    orchestrator, RedaktorAgent, UrzednikAgent,
    GUSAnalitykAgent, PrzewodnikAgent, StraznikAgent, OrganizatorAgent,
    KoordynatorAgent,
)

logger = setup_logger("API")

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

from src.api.endpoints.voice import router as voice_router
app.include_router(voice_router)  # /api/voice/transcribe

app.include_router(social_router)  # /api/social/* — propozycje postów dla n8n

# Sesje Rady Gminy — skróty obrad. Publiczne widzą wyłącznie skróty zatwierdzone
# przez człowieka; `/review/{token}` to strona akceptacji otwierana z maila.
from src.api.endpoints.council import router as council_router
app.include_router(council_router)  # /api/council/*

@app.on_event("startup")
async def startup_event():
    """Start scheduler and register AI agents on app startup"""
    if settings.SCHEDULER_ENABLED:
        start_scheduler()
    else:
        # Środowisko lokalne: API działa, zadania nie ruszają. Patrz komentarz
        # przy SCHEDULER_ENABLED w config.py — chodzi o Apify, OpenAI i push
        logger.warning(
            "SCHEDULER_ENABLED=false — harmonogram zadań NIE wystartował "
            "(scraping, AI, alerty push i newslettery są wyłączone)"
        )
    # Register all AI agents with the orchestrator
    for agent_cls in [RedaktorAgent, UrzednikAgent, GUSAnalitykAgent, PrzewodnikAgent,
                      StraznikAgent, OrganizatorAgent, KoordynatorAgent]:
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

    Kolejność feedu nie jest czysto chronologiczna — liczy się świeżość
    przemnożona przez wagę źródła, a wpisy z tego samego źródła są przeplatane
    (src/services/feed_policy.py). Bez tego pierwsza piątka zawsze pochodziła
    z jednego profilu FB publikującego kilkanaście razy dziennie.

    Args:
        limit: Maximum total articles to return (default: 50)
        per_source: Maximum articles per source (default: 5)
        days: Only return articles from the last N days (default: 2)
    """
    from datetime import timedelta
    from sqlalchemy import func, or_

    from src.services.feed_policy import (
        MAX_PINNED,
        article_score,
        collapse_duplicates,
        dedup_text,
        diversify,
        is_pinned_alert,
        publishable_conditions,
        source_label,
        still_relevant_event,
    )

    # Calculate cutoff date (2 days ago)
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    now = datetime.utcnow()

    # Use window function to rank articles per source
    # Limit per źródło liczony od momentu, który się liczy: dla zapowiedzi zdarzeń
    # (wyłączenia prądu) jest nim termin, nie data ogłoszenia.
    #
    # ODLEGŁOŚĆ od teraz, nie „najdalej w przyszłość" — ta sama reguła, którą
    # ranking stosuje w `feed_policy._reference_time`. Sortowanie malejące po
    # `coalesce(event_at, published_at)` stawiało na czele okna zapowiedzi
    # z najodleglejszym terminem: po dopuszczeniu do feedu zdarzeń bez godziny
    # końca (`still_relevant_event`) zebranie wiejskie z 16 września zajęłoby
    # miejsce w piątce Syli, czyli największego źródła lokalnych wpisów.
    reference_distance = func.least(
        func.abs(func.extract(
            "epoch",
            func.coalesce(Article.event_at, Article.published_at, Article.scraped_at) - now,
        )),
        func.abs(func.extract(
            "epoch", func.coalesce(Article.published_at, Article.scraped_at) - now
        )),
    )
    row_number = func.row_number().over(
        partition_by=Article.source_id,
        order_by=[reference_distance.asc(), Article.scraped_at.desc()],
    ).label('row_num')

    # Subquery with row numbers

    subquery = (
        select(Article.id, row_number)
        .where(
            or_(
                Article.published_at >= cutoff_date,
                Article.scraped_at >= cutoff_date,
                # zapowiedziane zdarzenie zostaje w feedzie do swojego terminu,
                # choćby ogłoszenie miało trzy tygodnie. `still_relevant_event`,
                # nie samo `event_until >= now`: godzinę końca zna Energa i alert
                # meteo, nie zna jej zapowiedź czytana przez model, a wpis
                # z terminem i bez końca wypadał z feedu w dniu, którego dotyczył
                # (25.08.2026: konsultacje ws. kanalizacji tego dnia o 19:00).
                still_relevant_event(Article, now),
            )
        )
        .where(*publishable_conditions(Article))  # filler i cudze reklamy poza feedem
        .subquery()
    )

    # Main query - join with subquery to filter by row_num <= per_source
    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .join(subquery, Article.id == subquery.c.id)
        .where(subquery.c.row_num <= per_source)
    )

    rows = list(result)

    # Ten sam materiał z dwóch źródeł (oba kanały Energi, przedruki) — raz.
    # Kolejność wejściowa musi już być rankingiem, więc najpierw sortujemy.
    rows.sort(
        key=lambda row: article_score(
            row[0].published_at, row[0].scraped_at, row[1], now,
            row[0].event_at, row[0].event_until, row[0].content_score,
            row[0].locality, row[0].title, row[0].content,
        ),
        reverse=True,
    )
    rows = collapse_duplicates(
        rows,
        text_of=lambda row: dedup_text(row[0]),
    )

    # Awarie dotyczące najbliższych godzin zostają na górze — reszta wg rankingu
    pinned, regular = [], []
    for article, source_name in rows:
        bucket = pinned if is_pinned_alert(
            article.category, article.published_at, article.scraped_at, now,
            article.event_at, article.event_until,
            article.title, article.content, article.locality,
        ) else regular
        bucket.append((article, source_name))

    # Blok przypięty ma twardy limit: przy wichurze Energa wypuszcza kilkanaście
    # wyłączeń naraz i feed zamieniał się w listę awarii. Nadmiar nie znika —
    # wraca do zwykłego rankingu, gdzie i tak stoi wysoko.
    overflow = pinned[MAX_PINNED:]
    pinned = pinned[:MAX_PINNED]
    regular = sorted(
        regular + overflow,
        key=lambda row: article_score(
            row[0].published_at, row[0].scraped_at, row[1], now,
            row[0].event_at, row[0].event_until, row[0].content_score,
            row[0].locality, row[0].title, row[0].content,
        ),
        reverse=True,
    )

    # Przeplot także wewnątrz bloku awarii — trzy wyłączenia prądu z jednego
    # kanału nie mogą zepchnąć wypadku drogowego pod linię zgięcia
    pinned = diversify(pinned, key=lambda row: row[0].source_id)
    ordered = pinned + diversify(
        regular, key=lambda row: row[0].source_id, preceding=pinned
    )

    # Map results to ArticleOutput with source_name
    pinned_ids = {article.id for article, _ in pinned}
    articles = []
    for article, source_name in ordered[:limit]:
        article_dict = article.model_dump()
        article_dict['source_name'] = source_name
        article_dict['source_label'] = source_label(source_name)
        article_dict['is_pinned'] = article.id in pinned_ids
        articles.append(ArticleOutput(**article_dict))

    return articles


@app.delete("/api/articles/{article_id}")
async def takedown_article(
    article_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_admin_user),
):
    """
    Notice-and-takedown: trwale usuwa artykuł wraz z jego embeddingami RAG
    (żądania usunięcia treści — prawo autorskie / wizerunek / art. 17 RODO).
    Wymaga roli administratora.
    """
    from sqlalchemy import text as sql_text

    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Artykuł nie został znaleziony")

    title = article.title
    await session.execute(sql_text(
        "DELETE FROM document_embeddings WHERE source_type = 'article' AND source_id = :aid"
    ), {"aid": article_id})
    await session.delete(article)
    await session.commit()

    return {"status": "deleted", "article_id": article_id, "title": title}


@app.post("/api/admin/storm-run")
async def force_storm_run(
    background: BackgroundTasks,
    force: bool = False,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_admin_user),
):
    """
    Ręczne wymuszenie przebiegu sztormowego — „ściągnij Facebooka TERAZ".

    Wartownik (`storm_watch`, co 30 min) sam decyduje na podstawie feedu Energi
    i ostrzeżeń IMGW. Ale 22.08.2026 pokazało, że człowiek wie o awarii wcześniej
    niż jakikolwiek automat: mieszkańcy pisali o braku wody, a żadne źródło
    maszynowe o wodzie nie mówi — Energa zna wyłącznie prąd. Ten endpoint jest
    dla takiej chwili.

    Hamulec odstępu (`storm_policy.MIN_GAP_H`) obowiązuje domyślnie i tutaj:
    plan Apify to 5 US$/mies., a cykl 22.06–21.07 zamknął się PONAD limitem.
    `force=true` go pomija — świadomie, bo czasem trzeba.

    Scrapowanie idzie w tle: aktor Apify chodzi minutami, a żądanie nie ma na
    co czekać. Efekt zobaczysz w feedzie, a push (jeśli to awaria) w ciągu
    kwadransa — `alert_push_job` czyta tekst, nie kategorię.
    """
    from src.scheduler.article_job import STORM_SOCIAL_SOURCES, update_articles_job
    from src.services import storm_policy

    now = datetime.utcnow()
    last_scraped = (await session.execute(
        select(Source.last_scraped).where(Source.name.in_(STORM_SOCIAL_SOURCES))
        .order_by(Source.last_scraped.desc()).limit(1)
    )).scalar_one_or_none()

    if not force and not storm_policy.enough_gap(last_scraped, now):
        minut = int((timedelta(hours=storm_policy.MIN_GAP_H) - (now - last_scraped)).total_seconds() // 60)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Profile pobrano {last_scraped:%H:%M} UTC — odstęp "
                f"{storm_policy.MIN_GAP_H} h minie za {minut} min. "
                f"Użyj ?force=true, jeśli to nie może czekać."
            ),
        )

    # Korutynę podajemy wprost — Starlette sam ją doczeka w pętli. Owijanie
    # w `asyncio.run` byłoby proszeniem się o „loop already running".
    background.add_task(
        update_articles_job,
        exclude_types=["social_media"],
        include_names=STORM_SOCIAL_SOURCES,
    )
    return {
        "status": "started",
        "sources": STORM_SOCIAL_SOURCES,
        "forced": force,
        "last_scraped": last_scraped.isoformat() if last_scraped else None,
        "note": "Przebieg chodzi w tle. Push o awarii pójdzie w ciągu 15 min.",
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
    """Get upcoming events with source name (scraped from)"""
    from src.services.feed_policy import visible_event_conditions
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(Event, Source.name.label("source_name"))
        .outerjoin(Article, Event.source_article_id == Article.id)
        .outerjoin(Source, Article.source_id == Source.id)
        .where(Event.event_date >= today_start)
        # powtórki scalone i wydarzenia spoza powiatu zostają w bazie, ale nie
        # w kalendarzu — `feed_policy.visible_event_conditions`
        .where(*visible_event_conditions(Event))
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

    from datetime import datetime, timedelta

    # Query latest cache entry (current or most recent when TTL expired)
    result = await session.execute(
        select(TrafficCache)
        .order_by(TrafficCache.fetched_at.desc())
        .limit(1)
    )
    cache_entry = result.scalar_one_or_none()

    if cache_entry:
        expires_at = cache_entry.fetched_at + timedelta(seconds=cache_entry.ttl_seconds)
        data = dict(cache_entry.data)
        data["fetched_at"] = cache_entry.fetched_at.isoformat()
        data["is_expired"] = datetime.utcnow() > expires_at
        return data

    # Fallback: no cache at all - return static fallback data
    service = TrafficService()
    fallback_data = service._get_fallback_data()
    result = fallback_data.dict()
    result["is_expired"] = True
    return result


# ======================
# Legacy GUS Statistics Endpoints - REMOVED (2026-02-17)
# ======================
# All GUS endpoints moved to src/api/endpoints/gus.py (database-first architecture)
# - OLD: /api/stats/demographics, /api/stats/employment, /api/stats/business
# - OLD: /api/stats/sync-gus, /api/stats/variables, /api/stats/update
# - NEW: /api/stats/overview, /api/stats/section/{section_key}, /api/stats/variable/{var_key}/detail
# - NEW: /api/stats/categories, /api/stats/variables/list, /api/stats/freshness
# See: backend/src/api/endpoints/gus.py (tier-based access, 88 variables, database-first)
