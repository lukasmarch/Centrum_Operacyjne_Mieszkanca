"""
`institution_info` — dane teleadresowe jednostek gminy (etap 7 pkt 5)

**Zastępuje `office_hours`**, które umiało dokładnie dwie instytucje wpisane
w stałą `OFFICE_HOURS` — i obie miało błędnie (urząd 7:15–15:15 zamiast
8:00–16:00, GOPS z adresem i telefonem Urzędu Gminy). Dziś dwanaście jednostek
z BIP: urząd, GOPS, ZOZ, biblioteka, OSiR, pięć szkół, przedszkole, żłobek.

**Dlaczego z bazy, a nie z karty gminy** (`services/gmina_facts.py`). Karta ma
limit 2 kB pilnowany testem, bo wchodzi do promptu KAŻDEGO agenta przy KAŻDYM
pytaniu — dwanaście adresów i telefonów zjadłoby ją w całości, a płaciłby za
to również ktoś pytający o wywóz śmieci. Do tego kryterium karty („zmienia się
rzadziej niż raz na rok, mieści się w linijce") godziny pracy nie spełniają.

Trzeci powód jest praktyczny: wiedza w prompcie **nie zostawia śladu**. Odczyt
przez narzędzie zapisuje wiersz w `agent_tool_calls`, więc po tygodniu widać,
o które jednostki ludzie pytają i czego w bazie brakuje. To jedyny sposób,
żeby dowiedzieć się tego z ruchu, a nie ze zgadywania.

⚠️ **Puste `hours` to prawidłowy wynik, nie awaria.** BIP publikuje godziny
tylko dla urzędu. Narzędzie mówi wtedy wprost, że ich nie mamy, i podaje
telefon — zmyślona godzina otwarcia szkoły jest gorsza niż jej brak.
Uzupełnia się je ręcznie w bazie i przebieg scrapera ich nie kasuje.
"""
import re
from typing import Optional

from sqlalchemy import text

from src.ai.tools import Tool, ToolContext, ToolResult, register

# Mowa potoczna → `kind` z bazy. Krótka lista, nie słownik synonimów: model
# dostaje pełne nazwy w opisie narzędzia i zwykle trafia sam. To jest siatka
# na „ośrodek pomocy", „opieka społeczna", „urząd".
_KIND_HINTS: tuple[tuple[str, str], ...] = (
    ("gops", "gops"), ("pomocy społecznej", "gops"), ("opieki społecznej", "gops"),
    ("opieka społeczna", "gops"), ("pomoc społeczna", "gops"),
    ("urząd", "urzad"), ("urzad", "urzad"), ("gmina", "urzad"),
    ("szkoł", "szkola"), ("szkol", "szkola"), ("podstawow", "szkola"),
    ("przedszkol", "przedszkole"), ("żłob", "zlobek"), ("zlob", "zlobek"),
    ("bibliotek", "biblioteka"),
    ("sport", "osir"), ("osir", "osir"), ("rekreac", "osir"),
    ("zdrow", "zoz"), ("przychodn", "zoz"), ("ośrodek zdrowia", "zoz"), ("zoz", "zoz"),
)


def _match_kind(query: str) -> Optional[str]:
    lowered = (query or "").lower()
    for needle, kind in _KIND_HINTS:
        if needle in lowered:
            return kind
    return None


async def institution_info(ctx: ToolContext, instytucja: Optional[str] = None) -> ToolResult:
    """Kontakt, adres, kierownik i (jeśli znamy) godziny pracy jednostek gminy."""
    query = (instytucja or "").strip()

    sql = ("SELECT slug, name, kind, address, phone, email, website, manager, "
           "hours, scope, bip_url FROM gmina_institutions WHERE active = TRUE")
    params: dict = {}

    if query:
        kind = _match_kind(query)
        if kind:
            sql += " AND kind = :kind"
            params["kind"] = kind
        else:
            # Nazwa własna albo miejscowość („szkoła w Rumianie", „Żabiny”).
            sql += " AND (name ILIKE :q OR address ILIKE :q OR slug ILIKE :q)"
            params["q"] = f"%{query}%"

    sql += " ORDER BY CASE kind WHEN 'urzad' THEN 0 WHEN 'gops' THEN 1 ELSE 2 END, name"

    rows = [dict(r._mapping) for r in (await ctx.session.execute(text(sql), params))]

    # Rodzaj trafiony, ale pytanie mówiło o KONKRETNEJ jednostce: „szkoła
    # w Rumianie" wracała jako komplet pięciu szkół, bo słowo „szkoł"
    # przesłaniało miejscowość. Zawężamy po rdzeniu pozostałych słów — nazwy
    # w bazie są w miejscowniku („w Rumianie"), tak samo jak w pytaniu,
    # a adresy w mianowniku („Rumian 12"), stąd porównanie po rdzeniu.
    if len(rows) > 1 and query:
        stems = [w[:5].lower() for w in re.findall(r"[\wóąęćśżźłń]{5,}", query)
                 if not _match_kind(w)]
        if stems:
            narrowed = [
                r for r in rows
                if any(s in f"{r['name']} {r['address'] or ''}".lower() for s in stems)
            ]
            if narrowed:
                rows = narrowed

    if not rows and query:
        # Zapytanie nie trafiło — oddajemy KOMPLET nazw zamiast pustki. Model
        # ma wtedy z czego wybrać przy następnej rundzie, a mieszkaniec dostaje
        # listę tego, co w ogóle znamy, zamiast „nie znalazłem".
        wszystkie = [dict(r._mapping) for r in (await ctx.session.execute(
            text("SELECT name FROM gmina_institutions WHERE active = TRUE ORDER BY name")
        ))]
        return ToolResult(
            content={
                "info": f"Nie mam jednostki pasującej do „{query}”.",
                "znane_jednostki": [w["name"] for w in wszystkie],
            },
            empty=True,
            summary=f"brak dopasowania: {query[:40]}",
        )

    if not rows:
        return ToolResult(
            content={"info": "Brak danych o jednostkach gminy w bazie."},
            empty=True,
            summary="baza jednostek pusta",
        )

    jednostki = []
    bez_godzin = 0
    for row in rows:
        if not row["hours"]:
            bez_godzin += 1
        jednostki.append({
            "nazwa": row["name"],
            "adres": row["address"] or None,
            "telefon": row["phone"] or None,
            "email": row["email"] or None,
            "www": row["website"] or None,
            "kieruje": row["manager"] or None,
            # Wprost dla modelu, żeby nie musiał wnioskować z `null`. Prompt
            # agenta ma to powtórzyć mieszkańcowi, a nie zamilczeć.
            "godziny_pracy": row["hours"] or "NIE MAMY tej informacji — podaj telefon",
            "zakres_spraw": row["scope"] or None,
        })

    sources = [
        {"type": "bip_static", "id": 0, "title": r["name"],
         "url": r["bip_url"], "similarity": 1.0}
        for r in rows if r["bip_url"]
    ]

    return ToolResult(
        content={"jednostki": jednostki},
        sources=sources,
        summary=(f"{len(jednostki)} jednostek"
                 + (f", {bez_godzin} bez godzin" if bez_godzin else "")),
    )


register(Tool(
    name="institution_info",
    description=(
        "Adres, telefon, kierownik i godziny pracy jednostek gminy Rybno: "
        "Urząd Gminy, GOPS (pomoc społeczna), ośrodek zdrowia, biblioteka, "
        "Ośrodek Sportu i Rekreacji, szkoły podstawowe (Rybno, Hartowiec, "
        "Koszelewy, Rumian, Żabiny), przedszkole, żłobek. Użyj przy pytaniu: "
        "kiedy czynny urząd, do której pracuje GOPS, jaki telefon do szkoły "
        "w Rumianie, kto kieruje biblioteką, gdzie jest żłobek. Pomiń argument, "
        "żeby dostać wszystkie jednostki."
    ),
    short="dane jednostek gminy: urząd, GOPS, szkoły, biblioteka, OSiR, żłobek",
    parameters={
        "type": "object",
        "properties": {
            "instytucja": {
                "type": "string",
                "description": (
                    "Nazwa albo rodzaj jednostki: „GOPS”, „urząd gminy”, "
                    "„szkoła w Rumianie”, „biblioteka”, „żłobek”. Pomiń, "
                    "żeby dostać listę wszystkich."
                ),
            },
        },
        "required": [],
    },
    fn=institution_info,
    status_message="Sprawdzam dane jednostki…",
))
