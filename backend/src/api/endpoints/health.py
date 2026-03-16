"""
Health API — clinic schedules + pharmacy duties for Gmina Rybno

GET /api/health/today    → who's on duty today (main widget endpoint)
GET /api/health/clinics  → full weekly schedule (future use)
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session

router = APIRouter(prefix="/api/health", tags=["health"])

DAY_NAMES_PL = [
    "poniedziałek", "wtorek", "środa", "czwartek",
    "piątek", "sobota", "niedziela"
]


@router.get("/today")
async def get_health_today(session: AsyncSession = Depends(get_session)):
    """
    Returns clinics and pharmacies active today.
    Main endpoint for the dashboard widget.
    """
    today = date.today()
    day_of_week = today.weekday()  # 0=Mon, 6=Sun
    day_name = DAY_NAMES_PL[day_of_week]

    # 1. Clinics with matching day_of_week OR specific_date = today
    result = await session.execute(
        text("""
            SELECT clinic_name, doctor_name, doctor_role, hours_from, hours_to, notes
            FROM clinic_schedules
            WHERE day_of_week = :dow OR specific_date = :today
            ORDER BY clinic_name, hours_from
        """),
        {"dow": day_of_week, "today": today},
    )
    clinic_rows = result.fetchall()

    # Group by clinic_name
    clinics_map: dict[str, list] = {}
    for row in clinic_rows:
        clinic_name, doctor_name, doctor_role, hours_from, hours_to, notes = row
        if clinic_name not in clinics_map:
            clinics_map[clinic_name] = []
        doctor_entry = {
            "name": doctor_name,
            "role": doctor_role,
            "hours": f"{hours_from}-{hours_to}",
        }
        if notes:
            doctor_entry["notes"] = notes
        clinics_map[clinic_name].append(doctor_entry)

    clinics = [
        {"clinic_name": name, "doctors": doctors}
        for name, doctors in clinics_map.items()
    ]

    # 2. Pharmacies active today
    is_weekend = day_of_week >= 5
    result = await session.execute(
        text("""
            SELECT pharmacy_name, address, phone, hours_from, hours_to, duty_type, notes
            FROM pharmacy_duties
            WHERE valid_year = :year
              AND (
                  duty_type = 'weekday'
                  OR (duty_type = 'weekend' AND (:dow = 5 OR :dow = 6))
                  OR (duty_type = 'holiday' AND :dow = 6)
                  OR day_of_week = :dow
              )
            ORDER BY pharmacy_name
        """),
        {"year": today.year, "dow": day_of_week},
    )
    pharmacy_rows = result.fetchall()

    pharmacies = []
    seen_pharmacies = set()
    for row in pharmacy_rows:
        name, address, phone, hours_from, hours_to, duty_type, notes = row
        key = f"{name}_{hours_from}"
        if key in seen_pharmacies:
            continue
        seen_pharmacies.add(key)
        entry = {
            "name": name,
            "address": address,
            "hours": f"{hours_from}-{hours_to}",
            "duty_type": duty_type,
        }
        if phone:
            entry["phone"] = phone
        pharmacies.append(entry)

    return {
        "date": today.isoformat(),
        "day_name": day_name,
        "clinics": clinics,
        "pharmacies": pharmacies,
    }


@router.get("/clinics")
async def get_all_clinics(session: AsyncSession = Depends(get_session)):
    """Full weekly clinic schedule (for future detailed page)."""
    result = await session.execute(
        text("""
            SELECT clinic_name, doctor_name, doctor_role, day_of_week,
                   specific_date, hours_from, hours_to, notes
            FROM clinic_schedules
            ORDER BY clinic_name, day_of_week, hours_from
        """)
    )
    rows = result.fetchall()

    schedules = []
    for row in rows:
        clinic_name, doctor_name, doctor_role, dow, specific_date, h_from, h_to, notes = row
        entry = {
            "clinic_name": clinic_name,
            "doctor_name": doctor_name,
            "doctor_role": doctor_role,
            "day_of_week": dow,
            "day_name": DAY_NAMES_PL[dow] if dow is not None else None,
            "specific_date": specific_date.isoformat() if specific_date else None,
            "hours": f"{h_from}-{h_to}",
            "notes": notes,
        }
        schedules.append(entry)

    return {"schedules": schedules, "count": len(schedules)}
