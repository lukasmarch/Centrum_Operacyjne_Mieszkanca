"""
Bus Timetable API – Linia RYBNO–DZIAŁDOWO przez Płośnicę (HAJKRU)

Endpointy:
  GET /api/bus/timetable  – pełny rozkład + przystanki (dla popup + widoku rozkładu)
  GET /api/bus/status     – aktualny status obu kierunków (pozycja autobusu / następny kurs)
"""
from datetime import datetime
from math import floor
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.database.connection import async_session

router = APIRouter(prefix="/api/bus", tags=["bus"])


async def _get_db():
    async with async_session() as session:
        yield session


def _parse_time(time_str: str, base: datetime) -> datetime:
    h, m = map(int, time_str.split(":"))
    return base.replace(hour=h, minute=m, second=0, microsecond=0)


@router.get("/timetable")
async def get_timetable(session: AsyncSession = Depends(_get_db)):
    """
    Zwraca pełny rozkład jazdy:
    - listę przystanków z GPS
    - kursy pogrupowane po kierunku, każdy z godzinami na wszystkich przystankach
    """
    # Przystanki
    result = await session.execute(
        text("SELECT stop_id, name, lat, lng, sequence FROM bus_stops ORDER BY sequence")
    )
    stops = [
        {"stop_id": r.stop_id, "name": r.name, "lat": r.lat, "lng": r.lng, "sequence": r.sequence}
        for r in result.fetchall()
    ]

    # Kursy z czasami
    result = await session.execute(text("""
        SELECT
            t.id        AS trip_id,
            t.direction,
            t.departure_time,
            t.service_type,
            st.stop_id,
            st.stop_sequence,
            st.arrival_time
        FROM bus_trips t
        JOIN bus_stop_times st ON st.trip_id = t.id
        ORDER BY t.direction, t.departure_time, st.stop_sequence
    """))
    rows = result.fetchall()

    trips: dict = {}
    for row in rows:
        direction = row.direction
        trip_id = row.trip_id
        key = f"{direction}_{trip_id}"
        if key not in trips:
            trips[key] = {
                "trip_id": trip_id,
                "direction": direction,
                "departure_time": row.departure_time,
                "service_type": row.service_type,
                "stop_times": {},
            }
        trips[key]["stop_times"][row.stop_id] = row.arrival_time

    grouped: dict = {"RYBNO_DZIALDOWO": [], "DZIALDOWO_RYBNO": []}
    for trip in trips.values():
        grouped[trip["direction"]].append(trip)

    return {"stops": stops, "trips": grouped}


@router.get("/status")
async def get_status(session: AsyncSession = Depends(_get_db)):
    """
    Oblicza aktualny status autobusów na podstawie rozkładu i bieżącej godziny.

    Dla każdego kierunku zwraca:
    - czy kurs jest aktywny
    - jeśli tak: który przystanek jest obecny/następny, postęp (0-1), minuty do następnego
    - jeśli nie: kiedy następny odjazd (godzina + za ile minut)
    """
    now = datetime.now()

    result = await session.execute(text("""
        SELECT
            t.id, t.direction, t.departure_time, t.service_type,
            st.stop_id, st.stop_sequence, st.arrival_time
        FROM bus_trips t
        JOIN bus_stop_times st ON st.trip_id = t.id
        ORDER BY t.direction, t.departure_time, st.stop_sequence
    """))
    rows = result.fetchall()

    # Zbuduj strukturę: direction → list of trips
    all_trips: dict = {}
    for row in rows:
        key = (row.direction, row.id)
        if key not in all_trips:
            all_trips[key] = {
                "trip_id": row.id,
                "direction": row.direction,
                "departure_time": row.departure_time,
                "service_type": row.service_type,
                "stops": [],  # (stop_id, arrival_time, seq)
            }
        all_trips[key]["stops"].append((row.stop_id, row.arrival_time, row.stop_sequence))

    directions_result = {}

    for direction in ("RYBNO_DZIALDOWO", "DZIALDOWO_RYBNO"):
        dir_trips = [t for (d, _), t in all_trips.items() if d == direction]
        dir_trips.sort(key=lambda t: t["departure_time"])

        active_bus = None
        next_departure = None
        min_diff = float("inf")

        for trip in dir_trips:
            stops = trip["stops"]  # list of (stop_id, arrival_time, seq)
            first_time = _parse_time(stops[0][1], now)
            last_time = _parse_time(stops[-1][1], now)

            if first_time <= now <= last_time:
                # Ten kurs jest aktualnie w drodze — znajdź segment
                for i in range(len(stops) - 1):
                    s1_id, s1_time_str, _ = stops[i]
                    s2_id, s2_time_str, _ = stops[i + 1]
                    t1 = _parse_time(s1_time_str, now)
                    t2 = _parse_time(s2_time_str, now)
                    if t1 <= now <= t2:
                        total = (t2 - t1).total_seconds()
                        elapsed = (now - t1).total_seconds()
                        progress = elapsed / total if total > 0 else 1.0
                        time_left = max(1, floor((t2 - now).total_seconds() / 60))
                        active_bus = {
                            "trip_id": trip["trip_id"],
                            "direction": direction,
                            "departure_time": trip["departure_time"],
                            "service_type": trip["service_type"],
                            "current_stop_id": s1_id,
                            "next_stop_id": s2_id,
                            "progress": round(progress, 4),
                            "time_left_minutes": time_left,
                            # pełna lista stop_times dla RouteTimeline
                            "all_stop_times": {s[0]: s[1] for s in stops},
                        }
                        break
                break  # tylko jeden aktywny kurs na raz w danym kierunku

            # Znajdź następny odjazd
            diff_sec = (first_time - now).total_seconds()
            if diff_sec > 0 and diff_sec < min_diff:
                min_diff = diff_sec
                next_departure = {
                    "trip_id": trip["trip_id"],
                    "time": trip["departure_time"],
                    "service_type": trip["service_type"],
                    "in_minutes": max(1, floor(diff_sec / 60)),
                }

        directions_result[direction] = {
            "is_active": active_bus is not None,
            "active_bus": active_bus,
            "next_departure": next_departure,
        }

    return {
        "now": now.strftime("%H:%M"),
        "day_of_week": now.weekday(),  # 0=Pon … 6=Nd
        "is_weekend": now.weekday() >= 5,
        "directions": directions_result,
    }
