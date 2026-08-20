"""
Odpady: jedna polityka dla briefingu i dla wieczornego push (2026-08-21).

Do 20.08.2026 przypomnienie o wywozie było obiecane w mailu powitalnym
(„wieczorem dzień wcześniej"), a nie docierało do nikogo z Premium. Trzy
przyczyny, wszystkie tutaj rozwiązane:

- **Kanał**: jedyną drogą był push o 6:50 rano, wykluczający posiadaczy
  newslettera dziennego „bo dostaną w mailu" — czego briefing nigdy nie robił
  (`WasteSchedule` nie było nawet zaimportowane w generatorze).
- **Rejon**: dopasowanie szło warunkiem `town in location or location in town`.
  „Rybno" trafiało w `Rybno R1` **i** `Rybno R2`, czyli w połowie przypadków
  w cudzy termin. Rybno ma dwa rejony wywozu i to nie jest szczegół — różnią się
  o tydzień.
- **Zapis**: konta sprzed 20.08 mają w `users.location` wartości z krótszej listy
  („Rybno"), a harmonogram zna wyłącznie `Rybno R1` / `Rybno R2`.

Rejon jest **jawną niewiadomą**, a nie zgadywanką: przy „Rybno" zwracamy oba
i mówimy o tym wprost w treści, zamiast po cichu wybierać jeden.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database.schema import WasteSchedule

DAY_NAMES_PL = [
    "poniedziałek", "wtorek", "środa", "czwartek",
    "piątek", "sobota", "niedziela",
]


def _norm(value: str) -> str:
    """Porównanie odporne na wielkość liter i ogonki — 'Dębień' == 'debien'."""
    table = str.maketrans("ąćęłńóśźż", "acelnoszz")
    return (value or "").strip().lower().translate(table)


async def known_towns(session: AsyncSession) -> List[str]:
    """Nazwy rejonów wprost z harmonogramu — lista miejscowości w kodzie by się rozjechała."""
    result = await session.execute(select(WasteSchedule.town).distinct())
    return sorted({row for row in result.scalars().all() if row})


def match_towns(location: Optional[str], towns: Sequence[str]) -> List[str]:
    """Rejony wywozu dla lokalizacji konta.

    Kolejność prób jest istotna:
    1. trafienie dokładne (`Dębień` → `Dębień`),
    2. lokalizacja jako przedrostek rejonu (`Rybno` → `Rybno R1`, `Rybno R2`) —
       stąd bierze się niejednoznaczność, którą sygnalizuje `len(...) > 1`,
    3. rejon jako przedrostek lokalizacji (`Rybno R1` zapisane jako `Rybno R1 `).

    Świadomie NIE ma tu dopasowania „zawiera": `Wery` siedzi w `Kopaniarze-Wery`
    tylko w naszej wyobraźni, a `Nowa Wieś` trafiłaby w każdą inną „Wieś".
    """
    if not location:
        return []

    loc = _norm(location)
    if not loc:
        return []

    exact = [t for t in towns if _norm(t) == loc]
    if exact:
        return exact

    prefixed = [t for t in towns if _norm(t).startswith(loc + " ")]
    if prefixed:
        return sorted(prefixed)

    return [t for t in towns if loc.startswith(_norm(t) + " ")]


async def collections_on(
    session: AsyncSession,
    day: date,
    towns: Optional[Sequence[str]] = None,
) -> Dict[str, List[str]]:
    """Co jedzie danego dnia, pogrupowane po rejonie: {'Rybno R1': ['Zmieszane']}."""
    query = select(WasteSchedule).where(WasteSchedule.collection_date == day)
    if towns is not None:
        if not towns:
            return {}
        query = query.where(WasteSchedule.town.in_(list(towns)))

    result = await session.execute(query)

    by_town: Dict[str, List[str]] = {}
    for row in result.scalars().all():
        types = by_town.setdefault(row.town, [])
        if row.waste_type not in types:  # ten sam typ bywa w harmonogramie dwa razy
            types.append(row.waste_type)
    return {town: sorted(types) for town, types in by_town.items()}


def join_types(types: Sequence[str]) -> str:
    """'Bio i Zmieszane' — spójnik zamiast przecinka, bo to czyta człowiek w powiadomieniu."""
    items = list(types)
    if len(items) <= 1:
        return items[0] if items else ""
    return f"{', '.join(items[:-1])} i {items[-1]}"


def day_label(day: date, today: Optional[date] = None) -> str:
    """'dziś' / 'jutro' / 'w czwartek' — termin liczony względem dnia wysyłki."""
    today = today or date.today()
    delta = (day - today).days
    if delta == 0:
        return "dziś"
    if delta == 1:
        return "jutro"
    return f"w {DAY_NAMES_PL[day.weekday()]}"


async def next_collection_for_location(
    session: AsyncSession,
    location: Optional[str],
    within_days: int = 1,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """Najbliższy wywóz dla lokalizacji — dziś albo w ciągu `within_days` dni.

    Zwraca `None`, gdy nic nie jedzie albo gdy lokalizacji nie ma w harmonogramie
    (np. konto bez ustawionej miejscowości). Cisza jest tu poprawną odpowiedzią:
    przypomnienie o cudzym rejonie jest gorsze niż jego brak.
    """
    today = (now or datetime.now()).date()
    towns = match_towns(location, await known_towns(session))
    if not towns:
        return None

    for offset in range(0, within_days + 1):
        day = today + timedelta(days=offset)
        found = await collections_on(session, day, towns)
        if found:
            return {
                "date": day,
                "when": day_label(day, today),
                "zones": [
                    {"town": town, "types": types, "types_label": join_types(types)}
                    for town, types in sorted(found.items())
                ],
                # Przy „Rybno" bez rejonu mamy dwa wpisy i musimy to powiedzieć wprost
                "ambiguous": len(towns) > 1,
            }
    return None
