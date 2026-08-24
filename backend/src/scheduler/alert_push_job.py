"""
Alerty push o awariach — job schedulera (co 15 minut)

Powstał 27.07.2026, po tym jak wyłączenie prądu w Rybnie stało cały dzień na
szczycie feedu i nie wywołało ani jednego powiadomienia. Przyczyna: jedyną
ścieżką, która pushowała awarie, był `proactive_alerts_job` z 6:50 — szukał
artykułów opublikowanych w ostatnich 2 godzinach i tylko dla Premium. Energa
datuje ogłoszenia kilka dni wstecz, a wpis trafił do bazy o 11:00, więc żaden
z dwóch warunków nie miał prawa się spełnić.

Trzy różnice wobec tamtej ścieżki:

- CO      — decyduje `services/alert_policy`, nie kategoria z AI. Kategoryzacja
            chodzi o 6:15 i 13:15; wyłączenie zescrapowane o 18:05 czekałoby na
            powiadomienie do rana, choć dotyczy dzisiejszego wieczoru.
- DLA KOGO— wszyscy subskrybenci (kategoria „alerty"), nie tylko Premium.
            „Alerty push o awariach i zagrożeniach" stoi w planie Dla Każdego.
- KIEDY   — co kwadrans przez całą dobę. Ten sam wpis bywa oceniany wiele razy:
            zapowiedź wyłączenia odpada, dopóki termin jest dalej niż 36 h,
            i przechodzi dopiero, gdy zdarzenie jest na wyciągnięcie ręki.

Przed powtórką chronią dwie rzeczy:

- `articles.alert_pushed_at` — Energa odświeża ten sam wpis co 3 h pod wspólnym
  `external_id`, więc bez znacznika jedno wyłączenie budziłoby telefon
  kilkanaście razy;
- sygnatura alertu (`alert_policy.signature`) — ten sam komunikat przedrukowany
  w drugim źródle to osobny wpis z własnym znacznikiem. 24.08.2026 o 6:08 poszły
  przez to dwa powiadomienia sekundę po sobie: post ZGK o wyłączeniu prądu
  (art. 5561) i jego przedruk na profilu Syli (art. 5564).
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.config import settings
from src.database.schema import Article
from src.services import alert_policy, feed_policy
from src.services.push_service import push_service
from src.utils.logger import setup_logger

logger = setup_logger("AlertPushJob")

LOCAL_TZ = ZoneInfo("Europe/Warsaw")

# Ile wpisów bierzemy pod uwagę w jednym przebiegu. Przy burzy Energa wypuszcza
# kilkanaście wyłączeń naraz — wtedy i tak zadziała MAX_ALERTS_PER_RUN.
SCAN_LIMIT = 120

# Twardy limit powiadomień na przebieg. Seria pushy pod rząd to najprostszy
# sposób, żeby mieszkaniec wyłączył powiadomienia na zawsze; reszta poczeka
# kwadrans, a wpisy i tak są w feedzie.
MAX_ALERTS_PER_RUN = 2

# Jak długo pamiętamy, o czym już powiadomiliśmy. `alert_pushed_at` chroni przed
# powtórką TEGO SAMEGO wpisu; to okno chroni przed powtórką tej samej TREŚCI
# z innego źródła — komunikat ZGK bywa przedrukowany na profilu Syli kilka
# godzin później i wtedy pierwszego wpisu nie ma już wśród kandydatów.
RECENT_PUSH_MEMORY_H = 24


def _format_when(event_at: Optional[datetime], event_until: Optional[datetime]) -> str:
    """Termin zdarzenia w czasie lokalnym — baza trzyma naiwny UTC."""
    if not event_at:
        return ""
    start = event_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ)
    today = datetime.now(LOCAL_TZ).date()

    if start.date() == today:
        day = "dziś"
    elif start.date() == today + timedelta(days=1):
        day = "jutro"
    else:
        day = start.strftime("%d.%m")

    window = f"{day} {start:%H:%M}"
    if event_until:
        end = event_until.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ)
        window += f"–{end:%H:%M}"
    return window


def _compose(article: Article, alert: alert_policy.Alert) -> Tuple[str, str]:
    """Nagłówek i treść powiadomienia."""
    places = list(alert.places)
    where = places[0] if len(places) == 1 else f"{places[0]} i {len(places) - 1} inne"
    title = f"{alert.label} — {where}"

    when = _format_when(article.event_at, article.event_until)
    headline = (article.display_title or article.title or "").strip()
    body = f"{when} · {headline}" if when else headline
    return title, body[:180]


async def _candidates(session: AsyncSession, now: datetime) -> List[Article]:
    """
    Wpisy, które w ogóle mogą dziś wywołać alert.

    Dwa okna, bo dwa rodzaje zdarzeń: świeżo zescrapowane (pożar, wypadek —
    liczy się moment publikacji) oraz zdarzenia z terminem w zasięgu ręki
    (wyłączenie prądu ogłoszone tydzień temu, ale zaczynające się jutro).
    """
    fresh_since = now - timedelta(hours=alert_policy.MAX_SCRAPE_LAG_H)
    event_from = now - timedelta(hours=alert_policy.MAX_AGE_H)
    event_to = now + timedelta(hours=alert_policy.PUSH_LOOKAHEAD_H)

    result = await session.execute(
        select(Article)
        .where(
            Article.alert_pushed_at == None,  # noqa: E711 — SQLAlchemy
            *feed_policy.publishable_conditions(Article),
            or_(
                Article.scraped_at >= fresh_since,
                Article.event_at.between(event_from, event_to),
            ),
        )
        .order_by(Article.scraped_at.desc())
        .limit(SCAN_LIMIT)
    )
    return list(result.scalars().all())


def _signature(article: Article) -> Optional[tuple]:
    """Klucz „ten sam alert" dla wpisu z bazy — patrz `alert_policy.signature`."""
    return alert_policy.signature(
        title=article.title,
        content=article.content or article.summary,
        published_at=article.published_at,
        event_at=article.event_at,
        event_until=article.event_until,
    )


async def _already_announced(session: AsyncSession, now: datetime) -> set:
    """
    O czym powiadomiliśmy w ostatniej dobie — kluczem alertu, nie identyfikatorem
    wpisu. `alert_pushed_at` chroni przed powtórką TEGO SAMEGO artykułu; to
    chroni przed powtórką tego samego ZDARZENIA opisanego gdzie indziej.
    """
    result = await session.execute(
        select(Article)
        .where(Article.alert_pushed_at >= now - timedelta(hours=RECENT_PUSH_MEMORY_H))
        .order_by(Article.alert_pushed_at.desc())
        .limit(SCAN_LIMIT)
    )
    return {sig for sig in (_signature(a) for a in result.scalars().all()) if sig}


async def run_alert_push_async():
    """Główna funkcja jobu."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.utcnow()
    sent_total = 0

    try:
        async with async_session() as session:
            candidates = await _candidates(session, now)
            announced = await _already_announced(session, now)

            for article in candidates:
                if sent_total >= MAX_ALERTS_PER_RUN:
                    break

                alert = alert_policy.evaluate(
                    title=article.title,
                    content=article.content or article.summary,
                    published_at=article.published_at,
                    scraped_at=article.scraped_at,
                    event_at=article.event_at,
                    event_until=article.event_until,
                    now=now,
                )
                if alert is None:
                    continue

                # Ten sam komunikat z dwóch źródeł = jedno powiadomienie.
                # Wpis i tak dostaje znacznik: inaczej wracałby do oceny co
                # kwadrans, dopóki termin zdarzenia nie minie.
                sig = _signature(article)
                if sig and sig in announced:
                    article.alert_pushed_at = datetime.utcnow()
                    session.add(article)
                    await session.commit()
                    logger.info(
                        f"Pominięto powtórkę art={article.id} "
                        f"[{alert.kind}] — to samo zdarzenie już wysłane"
                    )
                    continue

                title, body = _compose(article, alert)

                # Znacznik PRZED wysyłką: przy błędzie sieci w połowie pętli
                # wolimy stracić jedno powiadomienie niż wysłać je dwa razy.
                article.alert_pushed_at = datetime.utcnow()
                session.add(article)
                await session.commit()

                recipients = await push_service.send_to_category(
                    session=session,
                    category="alerty",
                    title=title,
                    body=body,
                    url="/",
                    icon="/icon-192.png",
                    places=alert.places,
                )
                if sig:
                    announced.add(sig)
                sent_total += 1
                logger.info(
                    f"Alert [{alert.kind}] art={article.id} → {recipients} urządzeń | "
                    f"{title} | {body}"
                )

            if not sent_total:
                logger.info(f"Brak alertów do wysłania (przejrzano {len(candidates)} wpisów)")
    finally:
        await engine.dispose()


def run_alert_push():
    """Wrapper synchroniczny dla APScheduler."""
    asyncio.run(run_alert_push_async())
