"""
Migration: Add bus timetable tables + populate with official schedule data
Source: PDF "Rozkład Jazdy Linia RYBNO–DZIAŁDOWO przez Płośnicę" (HAJKRU)

Tworzy tabele: bus_stops, bus_trips, bus_stop_times
i wypełnia je danymi z oficjalnego rozkładu jazdy.

Typy kursów:
  GS – kursuje zawsze (dni nauki szkolnej + dni robocze wolne od zajęć)
  S  – kursuje w dni nauki szkolnej
  G  – kursuje w dni robocze wolne od zajęć szkolnych

Użycie:
    cd backend && python -m scripts.migrations.add_bus_timetable
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings

# ─────────────────────────────────────────────
# PRZYSTANKI  (sequence = kolejność RYB→DZA)
# ─────────────────────────────────────────────
STOPS = [
    ("rybno",                 "Rybno (Centrum)",          53.3942, 19.9392, 1),
    ("tuczki_1",              "Tuczki I",                 53.3636, 19.9767, 2),
    ("tuczki_2",              "Tuczki II",                53.3550, 19.9850, 3),
    ("zabiny",                "Żabiny",                   53.3456, 19.9989, 4),
    ("koszelewy",             "Koszelewy",                53.3283, 20.0319, 5),
    ("plosnica",              "Płośnica",                 53.2797, 20.1044, 6),
    ("rutkowice",             "Rutkowice",                53.2678, 20.1339, 7),
    ("skurpie_1",             "Skurpie I",                53.2564, 20.1581, 8),
    ("skurpie_2",             "Skurpie II",               53.2500, 20.1650, 9),
    ("burkat_1",              "Burkat I",                 53.2417, 20.1786, 10),
    ("burkat_2",              "Burkat II",                53.2390, 20.1790, 11),
    ("dzialdowogrunwaldzka",  "Działdowo ul. Grunwaldzka",53.2361, 20.1803, 12),
    ("dzialdowopkp",          "Działdowo dworzec PKP/PKS",53.2350, 20.1830, 13),
]

# ─────────────────────────────────────────────
# ROZKŁAD JAZDY (z oficjalnego PDF)
# Format: (departure_time, service_type, {stop_id: "HH:MM", ...})
# ─────────────────────────────────────────────

RYB_DZA_TRIPS = [
    ("06:40", "GS", {
        "rybno": "06:40", "tuczki_1": "06:45", "tuczki_2": "06:47",
        "zabiny": "06:49", "koszelewy": "06:53", "plosnica": "07:02",
        "rutkowice": "07:07", "skurpie_1": "07:11", "skurpie_2": "07:13",
        "burkat_1": "07:15", "burkat_2": "07:18",
        "dzialdowogrunwaldzka": "07:21", "dzialdowopkp": "07:24",
    }),
    ("08:35", "S", {
        "rybno": "08:35", "tuczki_1": "08:40", "tuczki_2": "08:42",
        "zabiny": "08:44", "koszelewy": "08:48", "plosnica": "08:57",
        "rutkowice": "09:02", "skurpie_1": "09:06", "skurpie_2": "09:08",
        "burkat_1": "09:10", "burkat_2": "09:13",
        "dzialdowogrunwaldzka": "09:16", "dzialdowopkp": "09:19",
    }),
    ("10:45", "S", {
        "rybno": "10:45", "tuczki_1": "10:50", "tuczki_2": "10:52",
        "zabiny": "10:54", "koszelewy": "10:58", "plosnica": "11:07",
        "rutkowice": "11:12", "skurpie_1": "11:16", "skurpie_2": "11:18",
        "burkat_1": "11:20", "burkat_2": "11:23",
        "dzialdowogrunwaldzka": "11:26", "dzialdowopkp": "11:29",
    }),
    ("11:20", "G", {
        "rybno": "11:20", "tuczki_1": "11:25", "tuczki_2": "11:27",
        "zabiny": "11:29", "koszelewy": "11:33", "plosnica": "11:42",
        "rutkowice": "11:47", "skurpie_1": "11:51", "skurpie_2": "11:53",
        "burkat_1": "11:55", "burkat_2": "11:58",
        "dzialdowogrunwaldzka": "12:01", "dzialdowopkp": "12:04",
    }),
    ("13:00", "S", {
        "rybno": "13:00", "tuczki_1": "13:05", "tuczki_2": "13:07",
        "zabiny": "13:09", "koszelewy": "13:13", "plosnica": "13:22",
        "rutkowice": "13:27", "skurpie_1": "13:31", "skurpie_2": "13:33",
        "burkat_1": "13:35", "burkat_2": "13:38",
        "dzialdowogrunwaldzka": "13:41", "dzialdowopkp": "13:44",
    }),
    ("14:45", "S", {
        "rybno": "14:45", "tuczki_1": "14:50", "tuczki_2": "14:52",
        "zabiny": "14:54", "koszelewy": "14:58", "plosnica": "15:07",
        "rutkowice": "15:12", "skurpie_1": "15:16", "skurpie_2": "15:18",
        "burkat_1": "15:20", "burkat_2": "15:23",
        "dzialdowogrunwaldzka": "15:26", "dzialdowopkp": "15:29",
    }),
    ("15:15", "G", {
        "rybno": "15:15", "tuczki_1": "15:20", "tuczki_2": "15:22",
        "zabiny": "15:24", "koszelewy": "15:28", "plosnica": "15:37",
        "rutkowice": "15:42", "skurpie_1": "15:46", "skurpie_2": "15:48",
        "burkat_1": "15:50", "burkat_2": "15:53",
        "dzialdowogrunwaldzka": "15:56", "dzialdowopkp": "15:59",
    }),
]

DZA_RYB_TRIPS = [
    ("07:25", "GS", {
        "dzialdowopkp": "07:25", "dzialdowogrunwaldzka": "07:28",
        "burkat_2": "07:31", "burkat_1": "07:34",
        "skurpie_2": "07:36", "skurpie_1": "07:38",
        "rutkowice": "07:42", "plosnica": "07:47",
        "koszelewy": "07:56", "zabiny": "08:00",
        "tuczki_2": "08:02", "tuczki_1": "08:04", "rybno": "08:09",
    }),
    ("09:30", "S", {
        "dzialdowopkp": "09:30", "dzialdowogrunwaldzka": "09:33",
        "burkat_2": "09:36", "burkat_1": "09:39",
        "skurpie_2": "09:41", "skurpie_1": "09:43",
        "rutkowice": "09:47", "plosnica": "09:52",
        "koszelewy": "10:01", "zabiny": "10:05",
        "tuczki_2": "10:07", "tuczki_1": "10:09", "rybno": "10:14",
    }),
    ("11:40", "S", {
        "dzialdowopkp": "11:40", "dzialdowogrunwaldzka": "11:43",
        "burkat_2": "11:46", "burkat_1": "11:49",
        "skurpie_2": "11:51", "skurpie_1": "11:53",
        "rutkowice": "11:57", "plosnica": "12:02",
        "koszelewy": "12:11", "zabiny": "12:15",
        "tuczki_2": "12:17", "tuczki_1": "12:19", "rybno": "12:24",
    }),
    ("12:20", "G", {
        "dzialdowopkp": "12:20", "dzialdowogrunwaldzka": "12:23",
        "burkat_2": "12:26", "burkat_1": "12:29",
        "skurpie_2": "12:31", "skurpie_1": "12:33",
        "rutkowice": "12:37", "plosnica": "12:42",
        "koszelewy": "12:51", "zabiny": "12:55",
        "tuczki_2": "12:57", "tuczki_1": "12:59", "rybno": "13:04",
    }),
    ("13:50", "S", {
        "dzialdowopkp": "13:50", "dzialdowogrunwaldzka": "13:53",
        "burkat_2": "13:56", "burkat_1": "13:59",
        "skurpie_2": "14:01", "skurpie_1": "14:03",
        "rutkowice": "14:07", "plosnica": "14:12",
        "koszelewy": "14:21", "zabiny": "14:25",
        "tuczki_2": "14:27", "tuczki_1": "14:29", "rybno": "14:34",
    }),
    ("15:40", "S", {
        "dzialdowopkp": "15:40", "dzialdowogrunwaldzka": "15:43",
        "burkat_2": "15:46", "burkat_1": "15:49",
        "skurpie_2": "15:51", "skurpie_1": "15:53",
        "rutkowice": "15:57", "plosnica": "16:02",
        "koszelewy": "16:11", "zabiny": "16:15",
        "tuczki_2": "16:17", "tuczki_1": "16:19", "rybno": "16:24",
    }),
    ("16:20", "G", {
        "dzialdowopkp": "16:20", "dzialdowogrunwaldzka": "16:23",
        "burkat_2": "16:26", "burkat_1": "16:29",
        "skurpie_2": "16:31", "skurpie_1": "16:33",
        "rutkowice": "16:37", "plosnica": "16:42",
        "koszelewy": "16:51", "zabiny": "16:55",
        "tuczki_2": "16:57", "tuczki_1": "16:59", "rybno": "17:04",
    }),
]


async def run_migration():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:

        # 1. Tworzenie tabel (idempotentne)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bus_stops (
                id SERIAL PRIMARY KEY,
                stop_id VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                lng DOUBLE PRECISION NOT NULL,
                sequence INTEGER NOT NULL
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bus_trips (
                id SERIAL PRIMARY KEY,
                direction VARCHAR(30) NOT NULL,
                departure_time VARCHAR(5) NOT NULL,
                service_type VARCHAR(2) NOT NULL
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bus_stop_times (
                id SERIAL PRIMARY KEY,
                trip_id INTEGER NOT NULL REFERENCES bus_trips(id),
                stop_id VARCHAR(50) NOT NULL,
                stop_sequence INTEGER NOT NULL,
                arrival_time VARCHAR(5) NOT NULL
            )
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_bus_stop_times_trip_seq
            ON bus_stop_times(trip_id, stop_sequence)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_bus_trips_direction
            ON bus_trips(direction)
        """))

        # 2. Wyczyść istniejące dane (idempotentne)
        await conn.execute(text("DELETE FROM bus_stop_times"))
        await conn.execute(text("DELETE FROM bus_trips"))
        await conn.execute(text("DELETE FROM bus_stops"))

        # 3. Wstaw przystanki
        for stop_id, name, lat, lng, seq in STOPS:
            await conn.execute(text("""
                INSERT INTO bus_stops (stop_id, name, lat, lng, sequence)
                VALUES (:stop_id, :name, :lat, :lng, :seq)
            """), {"stop_id": stop_id, "name": name, "lat": lat, "lng": lng, "seq": seq})

        print(f"  ✓ Wstawiono {len(STOPS)} przystanków")

        # 4. Wstaw kursy i godziny
        trip_count = 0
        stop_time_count = 0
        for direction, trip_list in [("RYBNO_DZIALDOWO", RYB_DZA_TRIPS),
                                      ("DZIALDOWO_RYBNO", DZA_RYB_TRIPS)]:
            for dep_time, svc_type, stop_times in trip_list:
                result = await conn.execute(text("""
                    INSERT INTO bus_trips (direction, departure_time, service_type)
                    VALUES (:dir, :dep, :svc)
                    RETURNING id
                """), {"dir": direction, "dep": dep_time, "svc": svc_type})
                trip_id = result.scalar_one()
                trip_count += 1

                for seq, (stop_id, arrival) in enumerate(stop_times.items(), start=1):
                    await conn.execute(text("""
                        INSERT INTO bus_stop_times (trip_id, stop_id, stop_sequence, arrival_time)
                        VALUES (:trip_id, :stop_id, :seq, :arrival)
                    """), {"trip_id": trip_id, "stop_id": stop_id,
                           "seq": seq, "arrival": arrival})
                    stop_time_count += 1

        print(f"  ✓ Wstawiono {trip_count} kursów ({stop_time_count} rekordów stop_times)")
        print("  ✓ Migracja zakończona pomyślnie")

    await engine.dispose()


if __name__ == "__main__":
    print("Migracja: add_bus_timetable")
    asyncio.run(run_migration())
