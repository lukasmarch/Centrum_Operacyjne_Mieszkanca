"""
Materiał, który briefing podaje modelowi — bez wywoływania AI (2026-08-02)

Sprawdza trzy rzeczy, które 2.08.2026 poszły źle na produkcji:
1. do modelu idzie `display_title`, nie surowy tytuł z Facebooka,
2. cudze apele („kontakt z redakcją") nie wchodzą do materiału,
3. ostrzeżenie meteo po terminie ważności wypada, a pogodę opisuje sekcja
   z tego samego rekordu, który zasila widget.

Uruchomienie:
    cd backend && python -m scripts.test_summary_context          # na atrapach
    cd backend && python -m scripts.test_summary_context --db     # na bazie
"""
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from src.ai.summary_generator import SummaryGenerator
from src.services import weather_alert
from src.services.feed_policy import strip_cta_tail, strip_foreign_cta

OK = "✓"
FAIL = "✗"


@dataclass
class FakeArticle:
    id: int
    title: str
    display_title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    category: str = "Inne"
    published_at: Optional[datetime] = None
    event_at: Optional[datetime] = None
    event_until: Optional[datetime] = None
    location_mentioned: list = field(default_factory=list)
    source_id: int = 5


@dataclass
class FakeWeather:
    location: str = "Rybno"
    temperature: float = 18.39
    feels_like: float = 18.0
    description: str = "zachmurzenie umiarkowane"
    wind_speed: float = 3.4
    fetched_at: Optional[datetime] = None
    forecast: Optional[dict] = None


def _fixtures(now: datetime):
    """Realne wpisy z produkcji z 1–2.08.2026."""
    tablica = FakeArticle(
        id=5151,
        title="🔎 Znaleziono tablicę rejestracyjną podczas Dni Rybna!\n\nPodczas trwających…",
        display_title="Znaleziono tablicę rejestracyjną w Rybnie, pilny kontakt z redakcją",
        summary=(
            "Podczas Dni Rybna znaleziona została tablica rejestracyjna. Osoby, które "
            "poznają tablicę, proszone są o kontakt z redakcją w celu jej odzyskania."
        ),
        category="Urząd",
        published_at=now - timedelta(hours=18),
    )
    burza = FakeArticle(
        id=5154,
        title="⛈️ Uwaga! IMGW wydał ostrzeżenie II stopnia przed burzami dla naszego regionu! ⚠️",
        display_title="Ostrzeżenie przed burzami II stopnia w regionie, IMGW zaleca ostrożność",
        summary="IMGW ogłosił ostrzeżenie II stopnia przed burzami w godzinach 15:00–01:00.",
        content="Dziś, w godzinach 15:00–01:00, prognozowane są niebezpieczne zjawiska atmosferyczne.",
        category="Awaria",
        published_at=now - timedelta(hours=25),
    )
    return tablica, burza


def _weather(now: datetime) -> FakeWeather:
    slots = []
    for i in range(1, 6):
        stamp = now + timedelta(hours=3 * i)
        slots.append({
            "dt": int(stamp.replace(tzinfo=None).timestamp()),
            "temp": 18.0 + i,
            "pop": 0,
            "rain_3h": None,
            "description": "bezchmurnie",
        })
    return FakeWeather(fetched_at=now - timedelta(hours=1), forecast={"hourly": slots})


def run_offline() -> int:
    now = datetime(2026, 8, 2, 11, 30)
    tablica, burza = _fixtures(now)
    generator = SummaryGenerator.__new__(SummaryGenerator)  # bez klienta OpenAI
    generator._local_article_ids = {tablica.id, burza.id}
    generator._source_names = {5: "Facebook - Syla"}

    failures = 0

    # 1. Ostrzeżenie meteo z wczoraj wygasło
    expired = weather_alert.expired(
        burza.title, burza.content, burza.published_at, None, now
    )
    print(f"{OK if expired else FAIL} wczorajszy alert burzowy uznany za wygasły")
    failures += not expired

    ongoing = weather_alert.expired(
        burza.title, burza.content, burza.published_at, None,
        burza.published_at + timedelta(hours=6),
    )
    print(f"{OK if not ongoing else FAIL} ten sam alert w trakcie ważności zostaje")
    failures += ongoing

    # 2. Tytuł i treść bez cudzych apeli
    title = strip_cta_tail(tablica.display_title)
    body = strip_foreign_cta(tablica.summary)
    title_ok = "redakcj" not in title.lower() and "tablic" in title.lower()
    body_ok = "redakcj" not in body.lower() and "tablica" in body.lower()
    print(f"{OK if title_ok else FAIL} tytuł bez apelu: {title!r}")
    print(f"{OK if body_ok else FAIL} treść bez apelu: {body!r}")
    failures += (not title_ok) + (not body_ok)

    # 3. Materiał dla modelu
    text = generator._prepare_input_for_ai(
        datetime(2026, 8, 2),
        {"Urząd": [tablica]},
        events=[],
        air_quality=None,
        top_article=tablica,
        now=now,
        weather=_weather(now),
    )
    checks = [
        ("brak surowego tytułu z FB (emoji 🔎)", "🔎" not in text),
        ("brak cudzego apelu w materiale", "redakcj" not in text.lower()),
        ("jest sekcja pogodowa", "POGODA W RYBNIE" in text),
        ("jest prognoza z szansą opadów", "opady 0%" in text),
        ("jest reguła rozstrzygania", "ROZSTRZYGA O POGODZIE" in text),
    ]
    for label, passed in checks:
        print(f"{OK if passed else FAIL} {label}")
        failures += not passed

    print("\n--- materiał dla modelu (fragment) ---")
    print("\n".join(text.splitlines()[:8]))
    print("…")
    print("\n".join(text.splitlines()[-14:]))
    return failures


async def run_db() -> int:
    """Ten sam materiał, ale na realnych artykułach z bazy."""
    from src.database.connection import async_session
    from sqlmodel import select
    from src.database.schema import Article, Source, Weather

    async with async_session() as session:
        now = datetime.utcnow()
        generator = SummaryGenerator.__new__(SummaryGenerator)
        source_rows = (await session.execute(select(Source.id, Source.name))).all()
        generator._source_names = {row.id: row.name for row in source_rows}

        result = await session.execute(
            select(Article)
            .where(Article.processed == True)  # noqa: E712
            .where(Article.published_at >= now - timedelta(days=2))
            .order_by(Article.published_at.desc())
            .limit(30)
        )
        articles = list(result.scalars().all())
        generator._local_article_ids = {a.id for a in articles}

        alerts = [a for a in articles if weather_alert.is_weather_alert(a.title, a.content)]
        print(f"Ostrzeżeń meteo w materiale: {len(alerts)}")
        for a in alerts:
            _, end = weather_alert.validity_or_default(a.title, a.content, a.published_at)
            gone = weather_alert.expired(a.title, a.content, a.published_at, a.event_until, now)
            print(f"  [{a.id}] ważne do {end} (UTC) → {'WYGASŁE' if gone else 'aktualne'}")
            print(f"        {(a.display_title or a.title)[:80]}")

        weather = (await session.execute(
            select(Weather)
            .where(Weather.location == "Rybno")
            .where(Weather.is_current == True)  # noqa: E712
            .order_by(Weather.fetched_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if weather is None:
            print(f"{FAIL} brak bieżącego rekordu pogody dla Rybna")
            return 1

        print(f"\n{OK} pogoda: {weather.temperature}°C, {weather.description}, "
              f"pomiar {weather.fetched_at}")
        print("\n".join(SummaryGenerator._weather_lines(weather, now)))
        return 0


if __name__ == "__main__":
    if "--db" in sys.argv:
        raise SystemExit(asyncio.run(run_db()))
    failed = run_offline()
    print(f"\n{'BŁĘDY: ' + str(failed) if failed else 'Wszystko przechodzi'}")
    raise SystemExit(1 if failed else 0)
