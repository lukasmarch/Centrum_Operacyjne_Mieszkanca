"""
Narzędzia codzienne — odpady, kino, przychodnia, apteki, urząd (2026-08-22)

**Co znika.** Organizator wybierał sekcje kontekstu słownikiem `INTENT_KEYWORDS`
(cztery kubełki, ~30 rdzeni). Pytanie „Godziny pracy" (18.08, 19:13) nie trafiło
w żaden wzorzec, więc dostał komplet czterech sekcji naraz — i odpowiedział
pytaniem („o jakie godziny chodzi: lekarzy, aptek czy kina?"), bo w tym komplecie
nie było godzin, o które mieszkańcowi chodziło.

**Czego brakowało w ogóle.** Tego samego dnia padły „Jak pracuje gops" i „Gops".
Godziny urzędu i jednostek gminy nie istniały NIGDZIE: ani w karcie gminy, ani
w `bip_documents`, ani w harmonogramach. Powstało wtedy `office_hours` — dane
dwóch instytucji wpisane wprost w stałą.

⚠️ **`office_hours` już tu nie ma (24.08.2026).** Ręcznie wpisana stała nie ma
jak zdezaktualizować się głośno i obie jej pozycje okazały się błędne: urząd
czynny 8:00–16:00 (w stałej 7:15–15:15), a GOPS miał wpisany adres i telefon
Urzędu Gminy zamiast własnych. Zastąpiło ją `institution_info`
(`ai/tools/institutions.py`) czytające tabelę `gmina_institutions`, którą
napełnia scraper BIP — dwanaście jednostek zamiast dwóch.

**Miejscowość rozpoznaje model, nie regex.** `TOWN_ALIASES` (24 nazwy × odmiany
przypadków) zostaje w kodzie narzędzia jako DOPASOWANIE nazwy do harmonogramu,
ale wyłuskaniem „w Hartowcu" → „Hartowiec" zajmuje się model — on to robi
z definicji, a lista odmian przestaje rosnąć przy każdej nowej formie fleksyjnej.

⚠️ Rybno ma DWA rejony wywozu (`Rybno R1`/`Rybno R2`) różniące się o tydzień —
patrz `services/waste_policy.match_towns`. Samo „Rybno" → R1 z adnotacją.

Test: `cd backend && python -m scripts.test_agent_tools`
"""
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text

from src.ai.tools import Tool, ToolContext, ToolResult, register
from src.utils.logger import setup_logger

logger = setup_logger("DailyTools")

# Miejscowości w harmonogramie wywozu — kanoniczne nazwy z `waste_schedule`.
KNOWN_TOWNS = (
    "Rybno R1", "Rybno R2", "Jeglia", "Gralewo Stacja", "Gronowo", "Grądy",
    "Wery", "Kopaniarze", "Grabacz", "Koszelewki", "Koszelewy", "Żabiny",
    "Rapaty", "Prusy", "Szczupliny", "Nowa Wieś", "Groszki", "Naguszewo",
    "Rumian", "Truszczyny", "Dębień", "Hartowiec", "Tuczki", "Domki letniskowe",
)

_PL_TRANSLATE = str.maketrans("ąćęłńóśźż", "acelnoszz")

DAY_NAMES_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]

# Godziny pracy urzędu i jednostek — stan na 22.08.2026 (BIP /19/, spgzozrybno.pl).
# Wpisane wprost, bo to wiedza stała: zmienia się raz na kilka lat, a jej brak
# kosztował trzy nieudane odpowiedzi jednego wieczoru.
def _normalize(value: str) -> str:
    return (value or "").lower().translate(_PL_TRANSLATE)


def _match_town(name: Optional[str]) -> tuple:
    """Nazwa od modelu → nazwa z harmonogramu. Zwraca (miejscowość, adnotacja)."""
    if not name:
        return "Rybno R1", "Domyślnie rejon Rybno R1."
    cleaned = _normalize(name).strip()

    for town in KNOWN_TOWNS:
        if _normalize(town) == cleaned:
            return town, None

    # Samo „Rybno" bez rejonu — dwa rejony różnią się o tydzień, więc milczące
    # wybranie jednego z nich byłoby podaniem złej daty co drugiemu pytającemu.
    if cleaned.startswith("rybno"):
        if "r2" in cleaned or "rejon 2" in cleaned:
            return "Rybno R2", None
        return "Rybno R1", (
            "Rybno ma dwa rejony wywozu (R1 i R2) różniące się o tydzień — "
            "to terminy dla R1. Zapytaj mieszkańca, czy to jego rejon."
        )

    for town in KNOWN_TOWNS:
        norm = _normalize(town)
        # Odmiana przypadka: „hartowcu" / „hartowca" wobec „hartowiec".
        if cleaned.startswith(norm[:5]) or norm.startswith(cleaned[:5]):
            return town, None

    return "Rybno R1", (
        f"Nie znam miejscowości '{name}' w harmonogramie — to terminy dla Rybna R1. "
        f"Dostępne: {', '.join(KNOWN_TOWNS)}."
    )


async def waste_schedule(
    ctx: ToolContext, town: Optional[str] = None, days: int = 30
) -> ToolResult:
    """Terminy wywozu odpadów dla miejscowości."""
    try:
        days = max(1, min(int(days), 90))
    except (TypeError, ValueError):
        days = 30

    resolved, note = _match_town(town or getattr(ctx.user, "location", None))
    result = await ctx.session.execute(
        text("""
            SELECT waste_type, collection_date
            FROM waste_schedule
            WHERE town = :town
              AND collection_date >= CURRENT_DATE
              AND collection_date <= CURRENT_DATE + :days * INTERVAL '1 day'
            ORDER BY collection_date, waste_type
        """),
        {"town": resolved, "days": days},
    )
    rows = [{"typ": r[0], "data": r[1]} for r in result]

    if not rows:
        return ToolResult(
            content={
                "info": f"Brak terminów wywozu dla {resolved} w oknie {days} dni.",
                "dostepne_miejscowosci": list(KNOWN_TOWNS),
                "co_powiedziec": (
                    "Podaj listę miejscowości z harmonogramu i zapytaj, o którą chodzi."
                ),
            },
            empty=True,
            summary=f"brak terminów dla: {resolved}",
        )

    today = date.today()
    by_date: dict = {}
    for row in rows:
        left = (row["data"] - today).days
        label = f"{row['data']:%d.%m.%Y}" + (" (DZIŚ)" if left == 0 else f" (za {left} dni)")
        by_date.setdefault(label, []).append(row["typ"])

    payload = {
        "miejscowosc": resolved,
        "terminy": [{"kiedy": k, "rodzaje": v} for k, v in by_date.items()],
    }
    if note:
        payload["uwaga"] = note

    first = next(iter(by_date))
    return ToolResult(
        content=payload,
        summary=f"{resolved}: najbliższy wywóz {first.split(' ')[0]}",
    )


async def cinema_repertoire(ctx: ToolContext) -> ToolResult:
    """Repertuar kin w Działdowie i Lubawie na dziś i jutro."""
    result = await ctx.session.execute(text("""
        SELECT cinema_name, date, title, genre, showtimes, link
        FROM cinema_showtimes
        WHERE date IN (
            TO_CHAR(CURRENT_DATE, 'DD.MM.YYYY'),
            TO_CHAR(CURRENT_DATE + INTERVAL '1 day', 'DD.MM.YYYY')
        )
        ORDER BY cinema_name, date, title
    """))
    rows = [dict(r._mapping) for r in result]

    if not rows:
        return ToolResult(
            content={
                "info": "Brak repertuaru na dziś i jutro.",
                "co_powiedziec": (
                    "Powiedz, że repertuaru na te dni nie ma w bazie (jest "
                    "odświeżany codziennie rano), i wskaż stronę kina."
                ),
            },
            empty=True,
            summary="brak repertuaru na dziś i jutro",
        )

    seanse = [{
        "kino": r["cinema_name"],
        "data": r["date"],
        "tytul": r["title"],
        "gatunek": r["genre"],
        "godziny": r["showtimes"] or [],
        "link": r["link"] or "",
    } for r in rows]
    return ToolResult(content={"seanse": seanse}, summary=f"{len(seanse)} seansów")


async def clinic_schedule(ctx: ToolContext, day_offset: int = 0) -> ToolResult:
    """Harmonogram przyjęć lekarzy SPGZOZ Rybno."""
    try:
        day_offset = max(0, min(int(day_offset), 7))
    except (TypeError, ValueError):
        day_offset = 0
    target = date.today() + timedelta(days=day_offset)

    result = await ctx.session.execute(
        text("""
            SELECT clinic_name, doctor_name, doctor_role, hours_from, hours_to,
                   notes, source_url
            FROM clinic_schedules
            WHERE day_of_week = :dow OR specific_date = :target
            ORDER BY clinic_name, hours_from
        """),
        {"dow": target.weekday(), "target": target},
    )
    rows = [dict(r._mapping) for r in result]
    day_label = DAY_NAMES_PL[target.weekday()]

    if not rows:
        return ToolResult(
            content={
                "info": f"Brak zaplanowanych przyjęć na {day_label} {target:%d.%m.%Y}.",
                "co_powiedziec": "Wskaż spgzozrybno.pl albo kontakt z przychodnią.",
            },
            empty=True,
            summary=f"brak przyjęć w {day_label}",
        )

    return ToolResult(
        content={
            "dzien": f"{day_label} {target:%d.%m.%Y}",
            "przyjecia": [{
                "poradnia": r["clinic_name"],
                "lekarz": r["doctor_name"] or "—",
                "rola": r.get("doctor_role") or "",
                "godziny": f"{r['hours_from']}-{r['hours_to']}",
                "uwagi": r.get("notes") or "",
            } for r in rows],
            "zrodlo": "https://www.spgzozrybno.pl",
        },
        summary=f"{len(rows)} przyjęć w {day_label}",
    )


async def pharmacy_duty(ctx: ToolContext) -> ToolResult:
    """Apteki dyżurujące dziś w powiecie działdowskim."""
    today = date.today()
    result = await ctx.session.execute(
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
        {"year": today.year, "dow": today.weekday()},
    )
    rows = [dict(r._mapping) for r in result]

    if not rows:
        return ToolResult(
            content={"info": f"Brak danych o dyżurach aptek na {today:%d.%m.%Y}."},
            empty=True,
            summary="brak danych o dyżurach",
        )

    seen, apteki = set(), []
    for r in rows:
        key = f"{r['pharmacy_name']}_{r['hours_from']}"
        if key in seen:
            continue
        seen.add(key)
        apteki.append({
            "nazwa": r["pharmacy_name"],
            "adres": r.get("address") or "",
            "telefon": r.get("phone") or "",
            "godziny": f"{r['hours_from']}-{r['hours_to']}",
        })
    return ToolResult(
        content={"data": today.strftime("%d.%m.%Y"), "apteki": apteki},
        summary=f"{len(apteki)} aptek na dyżurze",
    )


register(Tool(
    name="waste_schedule",
    description=(
        "Terminy wywozu odpadów dla konkretnej miejscowości w gminie Rybno: "
        "zmieszane, segregacja, bio, gabaryty, popiół. Użyj przy każdym pytaniu "
        "o śmieci, odpady, wywóz, pojemniki, harmonogram odbioru."
    ),
    short="harmonogram wywozu odpadów dla miejscowości",
    parameters={
        "type": "object",
        "properties": {
            "town": {
                "type": "string",
                "description": (
                    "Miejscowość w mianowniku, np. „Hartowiec”, „Koszelewy”, „Rybno”. "
                    "Odmień nazwę z pytania („w Hartowcu” → „Hartowiec”). Pomiń, "
                    "żeby użyć miejscowości z profilu zalogowanego mieszkańca."
                ),
            },
            "days": {
                "type": "integer",
                "description": "Okno w dniach, 1-90. Domyślnie 30.",
                "minimum": 1, "maximum": 90,
            },
        },
        "required": [],
    },
    fn=waste_schedule,
    status_message="Sprawdzam harmonogram wywozu…",
))

register(Tool(
    name="cinema_repertoire",
    description=(
        "Repertuar kin w Działdowie i Lubawie na dziś i jutro: tytuły, gatunki, "
        "godziny seansów. Użyj przy pytaniu o kino, film, seans, repertuar."
    ),
    short="repertuar kin (Działdowo, Lubawa) na dziś i jutro",
    parameters={"type": "object", "properties": {}, "required": []},
    fn=cinema_repertoire,
    status_message="Sprawdzam repertuar kin…",
))

register(Tool(
    name="clinic_schedule",
    description=(
        "Harmonogram przyjęć lekarzy w SPGZOZ Rybno: POZ, stomatologia, "
        "ginekologia, logopedia, gabinet zabiegowy, USG. Zwraca nazwiska "
        "i godziny. Użyj przy pytaniu o lekarza, przychodnię, poradnię, wizytę."
    ),
    short="przyjęcia lekarzy w przychodni SPGZOZ Rybno",
    parameters={
        "type": "object",
        "properties": {
            "day_offset": {
                "type": "integer",
                "description": "0 = dziś, 1 = jutro, do 7. Domyślnie 0.",
                "minimum": 0, "maximum": 7,
            },
        },
        "required": [],
    },
    fn=clinic_schedule,
    status_message="Sprawdzam harmonogram przychodni…",
))

register(Tool(
    name="pharmacy_duty",
    description=(
        "Apteki dyżurujące dziś w powiecie działdowskim, z adresem i telefonem. "
        "Użyj przy pytaniu o aptekę, dyżur apteki, gdzie kupić leki wieczorem."
    ),
    short="apteki na dyżurze dziś (powiat działdowski)",
    parameters={"type": "object", "properties": {}, "required": []},
    fn=pharmacy_duty,
    status_message="Sprawdzam dyżury aptek…",
))

