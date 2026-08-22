"""
Narzędzia pogodowe — prognoza, stan bieżący, jakość powietrza (2026-08-22)

**Dane były od dawna, brakowało drogi do nich.** `weather_job` co godzinę zapisuje
komplet: pomiar bieżący, 40 slotów prognozy 5-dniowej (`forecast->'hourly'`)
i indeks UV. Z tego kompletu Przewodnik czytał wyłącznie pomiar bieżący
i średnią z siedmiu dni WSTECZ — więc na „jaka będzie pogoda jutro" (21.08,
19:07) odpowiadał z wiedzy ogólnej o sierpniu. Endpoint `/api/weather/forecast`
serwuje te same sloty do widgetu na stronie od miesięcy.

**Doba liczona lokalnie, nie w UTC.** OpenWeather podaje `dt` w UTC, baza trzyma
naiwny UTC, a mieszkaniec pyta o „jutro" w czasie polskim. Slot z 22:00 UTC to
już następny dzień w Rybnie — grupowanie po dacie UTC przesuwałoby wieczory
na zły dzień i „jutro" zaczynałoby się o 2:00 w nocy.

**Fallback na Rybno.** Pomiar istnieje tylko dla `Rybno` i `Działdowo`, a konto
wybiera jedną z 24 miejscowości — mieszkaniec Dębienia bez fallbacku dostawał
pustkę (ten sam błąd naprawiał `NewsletterGenerator._weather_for`).

Test: `cd backend && python -m scripts.test_agent_tools`
"""
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from src.ai.tools import Tool, ToolContext, ToolResult, register

LOCAL_TZ = ZoneInfo("Europe/Warsaw")

# Stacje, dla których mamy pomiar. Reszta miejscowości gminy → Rybno.
KNOWN_LOCATIONS = ("Rybno", "Działdowo")

# Ile dni prognozy oddajemy domyślnie. Pięć to pełny zakres OWM; trzy pokrywają
# pytanie „co na weekend" i nie rozdymają wiadomości `tool` do modelu.
DEFAULT_FORECAST_DAYS = 3
MAX_FORECAST_DAYS = 5

# Slot 3-godzinny liczy się jeszcze przez chwilę po swoim początku — inaczej
# o 11:59 znikałaby prognoza na godziny 9-12, czyli na TERAZ.
SLOT_GRACE_H = 3

# Po ilu godzinach od pobrania pomiar przestaje być „aktualny". `weather_job`
# chodzi co godzinę, więc sześć godzin oznacza, że coś nie działa — i model ma
# o tym powiedzieć, zamiast podawać stare dane z pewną miną.
STALE_AFTER_H = 6

_POLISH_DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]


def _resolve_location(name: Optional[str]) -> str:
    """Nazwa miejscowości → najbliższa stacja pomiarowa."""
    if not name:
        return "Rybno"
    cleaned = name.strip().lower()
    for known in KNOWN_LOCATIONS:
        if known.lower() == cleaned:
            return known
    if "działdow" in cleaned or "dzialdow" in cleaned:
        return "Działdowo"
    return "Rybno"


def _day_label(day: datetime, today: datetime) -> str:
    """„dziś" / „jutro" / „w czwartek" — model dostaje etykietę gotową, bo
    licząc ją sam, myli się przy przełomie tygodnia."""
    delta = (day.date() - today.date()).days
    if delta == 0:
        return "dziś"
    if delta == 1:
        return "jutro"
    if delta == 2:
        return "pojutrze"
    return _POLISH_DAYS[day.weekday()]


def _staleness_note(row: dict, ctx: ToolContext) -> Optional[str]:
    """Ostrzeżenie o nieświeżym pomiarze — dla modelu, nie do logu.

    Model bez tej informacji nie ma jak odróżnić danych sprzed kwadransa od
    danych sprzed trzech dni: jedne i drugie przychodzą z bazy jako liczby.
    """
    fetched = row.get("fetched_at")
    if not fetched:
        return None
    age_h = (ctx.now - fetched).total_seconds() / 3600
    if age_h < STALE_AFTER_H:
        return None
    return (
        f"UWAGA: pomiar pochodzi sprzed {int(age_h)} h "
        f"({fetched:%d.%m.%Y %H:%M} UTC) — dane mogą być nieaktualne. "
        "Powiedz o tym wprost."
    )


def build_days(slots: list, now_utc: datetime, days: int) -> tuple:
    """Sloty 3-godzinne → doby. Funkcja czysta, żeby dała się sprawdzić bez bazy.

    Dwie decyzje mają tu ciężar:

    * **doba liczona lokalnie** — slot z 22:00 UTC to już następny dzień
      w Rybnie; grupowanie po dacie UTC przesuwałoby wieczory na zły dzień;
    * **sloty z przeszłości odpadają** — gdy `weather_job` przestanie chodzić,
      wpis zostaje w bazie z `is_current = TRUE`, a bez tego filtra agent
      podałby prognozę sprzed trzech dni jako jutrzejszą, cicho i z pełnym
      przekonaniem. Ta sama pułapka, co utrudnienie drogowe sprzed dwóch dni
      wiszące w widgecie ruchu.
    """
    today_local = now_utc.astimezone(LOCAL_TZ)

    by_day: "OrderedDict[str, list]" = OrderedDict()
    for slot in slots:
        stamp = slot.get("dt")
        if not stamp:
            continue
        slot_utc = datetime.fromtimestamp(stamp, tz=timezone.utc)
        if slot_utc < now_utc - timedelta(hours=SLOT_GRACE_H):
            continue
        local_dt = slot_utc.astimezone(LOCAL_TZ)
        by_day.setdefault(local_dt.strftime("%Y-%m-%d"), []).append((local_dt, slot))

    dni, charts_days = [], []
    for _, entries in list(by_day.items())[:days]:
        temps = [s.get("temp") for _, s in entries if s.get("temp") is not None]
        if not temps:
            continue
        pops = [s.get("pop") or 0 for _, s in entries]
        rains = [s.get("rain_3h") or 0 for _, s in entries]
        winds = [s.get("wind_speed") or 0 for _, s in entries]

        # Opis dnia bierzemy ze slotu najbliższego południu — nocne „bezchmurnie"
        # opisuje dzień gorzej niż cokolwiek o 12:00.
        midday = min(entries, key=lambda e: abs(e[0].hour - 12))
        day_dt = entries[0][0]

        dzien = {
            "dzien": _day_label(day_dt, today_local),
            "data": day_dt.strftime("%d.%m.%Y"),
            "temp_min_c": round(min(temps), 1),
            "temp_max_c": round(max(temps), 1),
            "opis": midday[1].get("description", ""),
            "szansa_opadow_proc": int(round(max(pops) * 100)),
            "opad_mm": round(sum(rains), 1),
            "wiatr_max_m_s": round(max(winds), 1) if winds else None,
        }
        dni.append(dzien)
        charts_days.append({**dzien, "icon": midday[1].get("icon", "")})

    return dni, charts_days


async def _fetch_weather_row(ctx: ToolContext, location: str) -> Optional[dict]:
    result = await ctx.session.execute(
        text("""
            SELECT temperature, feels_like, description, humidity, wind_speed,
                   pressure, clouds, rain_1h, sunrise, sunset, forecast, fetched_at
            FROM weather
            WHERE location = :loc AND is_current = TRUE
            ORDER BY fetched_at DESC
            LIMIT 1
        """),
        {"loc": location},
    )
    row = result.first()
    return dict(row._mapping) if row else None


async def current_weather(ctx: ToolContext, location: Optional[str] = None) -> ToolResult:
    """Pomiar bieżący dla najbliższej stacji."""
    resolved = _resolve_location(location)
    row = await _fetch_weather_row(ctx, resolved)
    if not row:
        return ToolResult(
            content={"info": f"Brak pomiaru dla lokalizacji {resolved}."},
            empty=True,
        )

    fetched = row.get("fetched_at")
    payload = {
        "lokalizacja": resolved,
        "temperatura_c": row["temperature"],
        "odczuwalna_c": row["feels_like"],
        "opis": row["description"],
        "wilgotnosc_proc": row["humidity"],
        "wiatr_m_s": row["wind_speed"],
        "cisnienie_hpa": row["pressure"],
        "zachmurzenie_proc": row["clouds"],
        "opad_mm_h": row.get("rain_1h"),
        "pomiar_z": fetched.strftime("%d.%m.%Y %H:%M UTC") if fetched else None,
    }
    if row.get("sunrise") and row.get("sunset"):
        payload["wschod_slonca"] = row["sunrise"].strftime("%H:%M")
        payload["zachod_slonca"] = row["sunset"].strftime("%H:%M")
    if location and resolved != location.strip():
        payload["uwaga"] = (
            f"Pomiar pochodzi ze stacji {resolved} — najbliższej dla: {location.strip()}."
        )
    stale = _staleness_note(row, ctx)
    if stale:
        payload["uwaga_swiezosc"] = stale
    return ToolResult(content=payload)


async def weather_forecast(
    ctx: ToolContext,
    location: Optional[str] = None,
    days: int = DEFAULT_FORECAST_DAYS,
) -> ToolResult:
    """Prognoza dobowa złożona z 3-godzinnych slotów OpenWeather."""
    resolved = _resolve_location(location)
    row = await _fetch_weather_row(ctx, resolved)
    if not row or not row.get("forecast"):
        return ToolResult(
            content={"info": f"Brak prognozy dla lokalizacji {resolved}."},
            empty=True,
        )

    try:
        days = max(1, min(int(days), MAX_FORECAST_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_FORECAST_DAYS

    forecast = row["forecast"] or {}
    now_utc = ctx.now.replace(tzinfo=timezone.utc)
    dni, charts_days = build_days(forecast.get("hourly") or [], now_utc, days)

    if not dni:
        # Wszystkie sloty w przeszłości = prognoza się przeterminowała, a job
        # jej nie odświeżył. Uczciwa pustka zamiast wczorajszej pogody na jutro.
        fetched = row.get("fetched_at")
        return ToolResult(
            content={
                "info": (
                    f"Prognoza dla {resolved} jest nieaktualna "
                    f"(ostatnie pobranie: {fetched:%d.%m.%Y %H:%M} UTC)."
                    if fetched else f"Brak aktualnej prognozy dla {resolved}."
                ),
                "co_powiedziec": (
                    "Powiedz, że nie masz aktualnej prognozy, i odeślij do "
                    "zakładki Pogoda w serwisie. NIE podawaj prognozy z pamięci."
                ),
            },
            empty=True,
        )

    payload = {
        "lokalizacja": resolved,
        "dni": dni,
        "indeks_uv": forecast.get("uv_index"),
        "zrodlo": "OpenWeatherMap",
    }
    if location and resolved != location.strip():
        payload["uwaga"] = (
            f"Prognoza dla stacji {resolved} — najbliższej dla: {location.strip()}."
        )
    stale = _staleness_note(row, ctx)
    if stale:
        payload["uwaga_swiezosc"] = stale

    charts = [{
        "chart_type": "forecast",
        "title": f"Prognoza — {resolved}",
        "days": charts_days,
        "uv_index": forecast.get("uv_index"),
    }]
    return ToolResult(content=payload, charts=charts)


async def air_quality(ctx: ToolContext, location: Optional[str] = None) -> ToolResult:
    """Jakość powietrza z czujnika Airly."""
    resolved = _resolve_location(location)
    result = await ctx.session.execute(
        text("""
            SELECT pm25, pm10, caqi, caqi_level, fetched_at
            FROM air_quality
            WHERE location = :loc AND is_current = TRUE
            ORDER BY fetched_at DESC
            LIMIT 1
        """),
        {"loc": resolved},
    )
    row = result.first()
    if not row:
        return ToolResult(
            content={"info": f"Brak pomiaru jakości powietrza dla {resolved}."},
            empty=True,
        )
    data = dict(row._mapping)
    return ToolResult(content={
        "lokalizacja": resolved,
        "pm25_ug_m3": data["pm25"],
        "pm10_ug_m3": data["pm10"],
        "caqi": data["caqi"],
        "poziom": data["caqi_level"],
        "pomiar_z": data["fetched_at"].strftime("%d.%m.%Y %H:%M UTC") if data.get("fetched_at") else None,
    })


_LOCATION_PARAM = {
    "type": "string",
    "description": (
        "Miejscowość w gminie Rybno lub okolicy. Pomiar istnieje dla Rybna "
        "i Działdowa — inne nazwy zostaną przypisane do najbliższej stacji."
    ),
}

register(Tool(
    name="current_weather",
    description=(
        "Aktualny pomiar pogody: temperatura, odczuwalna, opis, wiatr, wilgotność, "
        "ciśnienie, wschód i zachód słońca. Użyj przy pytaniu o pogodę TERAZ, dziś, "
        "o warunki na zewnątrz w tej chwili."
    ),
    short="pogoda teraz (temperatura, wiatr, zachmurzenie, wschód/zachód słońca)",
    parameters={
        "type": "object",
        "properties": {"location": _LOCATION_PARAM},
        "required": [],
    },
    fn=current_weather,
    status_message="Sprawdzam aktualny pomiar pogody…",
))

register(Tool(
    name="weather_forecast",
    description=(
        "Prognoza pogody na najbliższe dni (do 5): temperatura min/max, opis, "
        "szansa opadów, suma opadu, wiatr, indeks UV. Użyj ZAWSZE, gdy pytanie "
        "dotyczy przyszłości: jutro, weekend, najbliższe dni, czy będzie padać, "
        "czy warto planować coś na zewnątrz."
    ),
    short="prognoza na najbliższe dni (do 5), z szansą opadów i indeksem UV",
    parameters={
        "type": "object",
        "properties": {
            "location": _LOCATION_PARAM,
            "days": {
                "type": "integer",
                "description": "Liczba dni prognozy, 1-5. Domyślnie 3.",
                "minimum": 1,
                "maximum": MAX_FORECAST_DAYS,
            },
        },
        "required": [],
    },
    fn=weather_forecast,
    status_message="Pobieram prognozę pogody…",
))

register(Tool(
    name="air_quality",
    description=(
        "Jakość powietrza z czujnika Airly: PM2.5, PM10, indeks CAQI i jego poziom. "
        "Użyj przy pytaniu o smog, czystość powietrza, warunki dla alergika lub "
        "bezpieczeństwo aktywności na zewnątrz."
    ),
    short="jakość powietrza (PM2.5, PM10, indeks CAQI)",
    parameters={
        "type": "object",
        "properties": {"location": _LOCATION_PARAM},
        "required": [],
    },
    fn=air_quality,
    status_message="Sprawdzam jakość powietrza…",
))
