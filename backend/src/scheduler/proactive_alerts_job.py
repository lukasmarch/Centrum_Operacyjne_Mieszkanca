"""
Wieczorne powiadomienia proaktywne — job schedulera (codziennie o 18:00)

ZASADA KANAŁÓW (brak duplikatów, ale i brak dziur):
- Poranny briefing 7:15 (mail, Premium) = pełny obraz dnia, w tym wywóz odpadów
- **Wieczór 18:00 (push)** = to, co trzeba zrobić PRZED jutrem: wystawić pojemnik,
  przygotować się na mróz. Wiadomość o 6:50 rano przychodziła po tym, jak śmieciarka
  już jechała przez wieś.
- Awarie NIE są tu obsługiwane — od 27.07.2026 robi to `alert_push_job` (co 15 min,
  dla wszystkich subskrybentów). Awaria nie czeka na okno pipeline'u.

Dwie zmiany z 21.08.2026, obie wynikają z obietnicy w mailu powitalnym
(„Przypomnienie o wywozie odpadów — wieczorem dzień wcześniej"):

1. **Godzina**: 6:50 → 18:00. Rano dzień wcześniej to nie jest „wieczorem",
   a rano tego samego dnia jest już za późno.
2. **Odbiorcy**: koniec wykluczania osób z newsletterem dziennym. Wykluczenie
   stało tu z adnotacją „dostaną to w emailu", a briefing o odpadach nie mówił
   ani słowa — `WasteSchedule` nie było nawet zaimportowane w generatorze.
   Newsletter dzienny jest dla Premium DOMYŚLNY, więc wykluczenie obejmowało
   dokładnie tych, którym obiecaliśmy przypomnienie. Teraz briefing pisze
   o wywozie rano, a push przypomina wieczorem — inny moment, inne zadanie.

Odbiorca: Premium/Business z aktywną subskrypcją push.
"""
import asyncio
from datetime import datetime, date, timedelta
from typing import List

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.config import settings
from src.database.schema import User, UserTier
from src.services import waste_policy
from src.services.push_service import push_service
from src.utils.logger import setup_logger

logger = setup_logger("ProactiveAlertsJob")


async def _get_premium_users(session) -> List[User]:
    """Premium/Business z aktywnym kontem — z lokalizacją, bo od niej zależy rejon wywozu."""
    result = await session.execute(
        select(User).where(
            User.tier.in_([UserTier.PREMIUM.value, UserTier.BUSINESS.value]),
            User.is_active == True,  # noqa: E712 — SQLAlchemy wymaga porównania
        )
    )
    return list(result.scalars().all())


async def _send_frost_alert(session, user_ids: List[int]) -> int:
    """
    Alert mrozowy gdy prognoza < -5°C.

    O 18:00 ma sens, jakiego nie miał o 6:50: „tej nocy" to jeszcze przyszłość,
    więc da się przełożyć wyjazd albo okryć instalację.
    """
    from src.database.schema import Weather

    result = await session.execute(
        select(Weather).order_by(Weather.fetched_at.desc()).limit(1)
    )
    weather = result.scalar_one_or_none()
    if not weather:
        return 0

    temp = getattr(weather, 'temp_min', None) or getattr(weather, 'temperature', None)
    if temp is None or temp >= -5:
        return 0

    logger.info(f"Frost alert: temp={temp}°C → sending to {len(user_ids)} Premium users")
    return await push_service.send_proactive_reminder(
        session=session,
        user_ids=user_ids,
        title=f"Uwaga: mróz {temp:.0f}°C tej nocy",
        body="Możliwe silne oblodzenie dróg i chodników. Jedź ostrożnie.",
        url="/pogoda",
        icon="/icon-192.png",
    )


async def _send_waste_reminder(session, users: List[User], now: datetime) -> int:
    """Przypomnienie o jutrzejszym wywozie — jeden push na użytkownika.

    Rejon liczy `waste_policy`, nie zapytanie „nazwa zawiera nazwę": Rybno ma dwa
    rejony różniące się o tydzień, a warunek `town in location` wysyłał mieszkańcowi
    Rybna oba terminy naraz. Konto bez rozpoznanej miejscowości nie dostaje nic —
    cudzy termin jest gorszy niż cisza.
    """
    tomorrow = (now + timedelta(days=1)).date()
    day_name = waste_policy.DAY_NAMES_PL[tomorrow.weekday()]

    towns_all = await waste_policy.known_towns(session)
    tomorrow_collections = await waste_policy.collections_on(session, tomorrow)
    if not tomorrow_collections:
        return 0

    total = 0
    for user in users:
        zones = waste_policy.match_towns(user.location, towns_all)
        mine = {t: types for t, types in tomorrow_collections.items() if t in zones}
        if not mine:
            continue

        types_label = waste_policy.join_types(
            sorted({t for types in mine.values() for t in types})
        )
        where = " i ".join(sorted(mine))
        sent = await push_service.send_proactive_reminder(
            session=session,
            user_ids=[user.id],
            title=f"Jutro ({day_name}) wywóz — wystaw pojemnik",
            body=f"{types_label} — {where}",
            url="/",
            icon="/icon-192.png",
        )
        total += sent

    return total


async def run_proactive_alerts_async():
    """Główna funkcja jobu."""
    logger.info("=== Proactive Alerts Job START ===")
    start = datetime.utcnow()
    now = datetime.now()  # czas lokalny — „jutro" liczymy po polskiej dacie
    total_sent = 0

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        users = await _get_premium_users(session)
        if not users:
            logger.info("Proactive: brak Premium userów")
            await engine.dispose()
            return

        logger.info(f"Proactive: {len(users)} kont Premium/Business")

        # 1. Wywóz jutro — wieczorem dzień wcześniej, dokładnie jak obiecuje mail powitalny
        total_sent += await _send_waste_reminder(session, users, now)

        # 2. Mróz tej nocy
        total_sent += await _send_frost_alert(session, [u.id for u in users])

    await engine.dispose()
    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"=== Proactive Alerts Job DONE: {total_sent} total, {elapsed:.1f}s ===")


def run_proactive_alerts():
    """Wrapper synchroniczny dla APScheduler."""
    asyncio.run(run_proactive_alerts_async())
