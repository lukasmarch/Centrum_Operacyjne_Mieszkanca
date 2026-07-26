"""
Health API — clinic schedules + pharmacy duties for Gmina Rybno

GET /api/health/today    → who's on duty today (main widget endpoint)
GET /api/health/clinics  → full weekly schedule (future use)
"""
import re
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session

router = APIRouter(prefix="/api/health", tags=["health"])

DAY_NAMES_PL = [
    "poniedziałek", "wtorek", "środa", "czwartek",
    "piątek", "sobota", "niedziela"
]

def _easter_date(year: int) -> date:
    """Easter Sunday (Gauss algorithm) — needed for movable Polish holidays."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _is_polish_holiday(d: date) -> bool:
    """Dni ustawowo wolne od pracy w Polsce (stałe + ruchome)."""
    fixed = {
        (1, 1), (1, 6), (5, 1), (5, 3), (8, 15),
        (11, 1), (11, 11), (12, 24), (12, 25), (12, 26),
    }
    if (d.month, d.day) in fixed:
        return True
    easter = _easter_date(d.year)
    movable = {
        easter,
        easter + timedelta(days=1),   # Poniedziałek Wielkanocny
        easter + timedelta(days=49),  # Zielone Świątki
        easter + timedelta(days=60),  # Boże Ciało
    }
    return d in movable


# Matches day ranges like "02-03.03" or "2-3.03"
_RANGE_RE = re.compile(r'(\d{1,2})-(\d{1,2})\.(\d{2})')
# Matches single dates like "16.03" or "2.03"
_DATE_RE = re.compile(r'(\d{1,2})\.(\d{2})')


def _dates_in_segment(segment: str, year: int) -> list[date]:
    """Extract all dates from a note segment (handles ranges and single dates)."""
    found: list[date] = []

    # Ranges first: "02-03.03" → March 2 and 3
    for m in _RANGE_RE.finditer(segment):
        d_start, d_end, month = int(m.group(1)), int(m.group(2)), int(m.group(3))
        for day in range(d_start, d_end + 1):
            try:
                found.append(date(year, month, day))
            except ValueError:
                pass

    # Single dates from remainder (remove ranges to avoid double-match)
    clean = _RANGE_RE.sub("", segment)
    for m in _DATE_RE.finditer(clean):
        day, month = int(m.group(1)), int(m.group(2))
        try:
            found.append(date(year, month, day))
        except ValueError:
            pass

    return found


def _today_change_note(notes: Optional[str], today: date) -> Optional[str]:
    """
    Parse pipe-separated note segments and return the first segment
    that mentions today's date.  Returns None when today is not affected.

    Example notes value:
      "W dniach 2.03, 16.03 lekarz przyjmuje w godz. 8:00-18:00. |
       W dniu 19.03, 31.03 lekarz nie przyjmuje."
    """
    if not notes:
        return None
    for segment in notes.split(" | "):
        segment = segment.strip()
        if not segment:
            continue
        if today in _dates_in_segment(segment, today.year):
            return segment
    return None


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
        # Only include notes when today's date is explicitly mentioned
        change_note = _today_change_note(notes, today)
        if change_note:
            doctor_entry["notes"] = change_note
        clinics_map[clinic_name].append(doctor_entry)

    clinics = [
        {"clinic_name": name, "doctors": doctors}
        for name, doctors in clinics_map.items()
    ]

    # 2. Pharmacies active today — exactly ONE duty type applies per day:
    #    holiday (dni świąteczne) > weekend (niedziela) > weekday (pn–sob)
    result = await session.execute(
        text("""
            SELECT pharmacy_name, address, phone, hours_from, hours_to, duty_type, notes, day_of_week
            FROM pharmacy_duties
            WHERE valid_year = :year
            ORDER BY pharmacy_name
        """),
        {"year": today.year},
    )
    pharmacy_rows = result.fetchall()

    if _is_polish_holiday(today):
        wanted_duty = "holiday"
    elif day_of_week == 6:
        wanted_duty = "weekend"
    else:
        wanted_duty = "weekday"

    def _row_matches(row) -> bool:
        duty_type, row_dow = row[5], row[7]
        if duty_type == wanted_duty:
            return True
        # Explicit day-of-week assignment wins regardless of duty_type label
        return row_dow is not None and row_dow == day_of_week

    matched = [row for row in pharmacy_rows if _row_matches(row)]
    # Fallback: holiday without dedicated duty entry → treat like Sunday
    if not matched and wanted_duty == "holiday":
        matched = [row for row in pharmacy_rows if row[5] == "weekend"]

    pharmacies = []
    seen_pharmacies = set()
    for row in matched:
        name, address, phone, hours_from, hours_to, duty_type, notes, _ = row
        if name in seen_pharmacies:
            continue
        seen_pharmacies.add(name)
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
