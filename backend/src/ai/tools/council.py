"""
Narzędzie sesji Rady Gminy (etap 5, 2026-08-24)

**Bramka akceptacji obowiązuje także agenta — i to jest tu najważniejsze.**
Narzędzie czyta WYŁĄCZNIE sesje w stanie `published`. Skrót w stanie `pending`
nie istnieje dla agenta tak samo, jak nie istnieje dla strony: cytat da się
sprawdzić twardo, ale `description` punktu już nie, a na sesji pilotażowej model
dopisał tam cel zagospodarowania działki, którego nikt nie wypowiedział.
Wpuszczenie `pending` do czatu obeszłoby jedyne zabezpieczenie, jakie ta funkcja
ma — i zrobiłoby to po cichu, bo w rozmowie nikt nie sprawdza, skąd wzięło się
zdanie.

**Numery uchwał doklejamy z rejestru, bo z nagrania ich nie ma.** Model
streszczający obrady zapisuje `resolutions[].number = null` — na sesji XXIII
wszystkie siedem. Nic dziwnego: przewodniczący czyta tytuł uchwały, a nie jej
numer, bo numer nadaje się po głosowaniu. Rejestr `legal_acts` (etap 4) ma te
numery i zna DATĘ PODJĘCIA, a ta jest równa dacie sesji. Jedno zapytanie SQL
zamienia „przyjęto uchwałę o kredycie dla OSP" w „UCHWAŁA NR XXIII/176/2026".

To jest dokładnie ta klasa odpowiedzi, dla której powstały narzędzia: żadna
heurystyka słów kluczowych nie połączyłaby nagrania z rejestrem aktów, bo
musiałaby z góry wiedzieć, że pytanie o obrady potrzebuje numerów uchwał.
"""
import json
from typing import Optional

from sqlalchemy import func, select

from src.services import provenance as prov
from src.ai.tools import Tool, ToolContext, ToolResult, register
from src.database.schema import CouncilSession, CouncilSessionStatus, LegalAct
from src.utils.logger import setup_logger

logger = setup_logger("CouncilTools")

PUBLISHED = CouncilSessionStatus.PUBLISHED.value

# Ile sesji naraz. Dwie, bo skrót jednej to siedem punktów z opisami — trzy
# sesje w kontekście wypchnęłyby wszystko inne, a mieszkaniec pyta o ostatnią.
DEFAULT_LIMIT = 2
MAX_LIMIT = 5

# Ile znaków opisu punktu wchodzi do kontekstu. Pełny opis bywa akapitem,
# a punktów jest kilkanaście na sesję.
POINT_CHARS = 400


def _summary(row: CouncilSession) -> dict:
    try:
        return json.loads(row.summary_json or "{}")
    except Exception:
        logger.warning(f"Skrót sesji {row.id} nie jest poprawnym JSON-em")
        return {}


async def _acts_for(ctx: ToolContext, row: CouncilSession) -> list[dict]:
    """Uchwały podjęte w dniu sesji — z rejestru, po dacie podjęcia."""
    if not row.session_date:
        return []
    stmt = (
        select(LegalAct)
        .where(func.date(LegalAct.adopted_at) == row.session_date.date())
        .where(LegalAct.act_group.ilike("%Uchwały%"))
        .order_by(LegalAct.act_number)
    )
    acts = (await ctx.session.execute(stmt)).scalars().all()
    return [
        {"numer": a.act_number, "tytul": a.title, "status": a.status, "url": a.url}
        for a in acts
    ]


async def council_sessions(ctx: ToolContext, limit: int = DEFAULT_LIMIT) -> ToolResult:
    """Skróty obrad Rady Gminy — tylko zatwierdzone przez człowieka."""
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))

    rows = (await ctx.session.execute(
        select(CouncilSession)
        .where(CouncilSession.status == PUBLISHED)
        .order_by(CouncilSession.session_date.desc().nullslast(),
                  CouncilSession.id.desc())
        .limit(limit)
    )).scalars().all()

    if not rows:
        # Rozróżnienie, które musi dotrzeć do mieszkańca: to nie jest „nie ma
        # obrad", tylko „nie ma jeszcze SPRAWDZONEGO skrótu". Nagrania są
        # publiczne i można ich posłuchać.
        #
        # ⚠️ Pustka NIE JEST końcem pracy — 25.08.2026 była. Mieszkaniec zapytał
        # „kiedy w gminie Rybno posiedzenie rady i komisji", Urzędnik zawołał to
        # narzędzie, dostał pustkę i cztery razy z rzędu odpowiedział „skrótów
        # jeszcze nie opublikowano", mimo dwóch próśb o szukanie dalej. Termin
        # XXIV sesji leżał w tym czasie i w kalendarzu (`upcoming_events`),
        # i w ogłoszeniu BIP w RAG (`search_documents` zwracał salę, godzinę
        # i porządek obrad). Zawinił TEN tekst: wynik narzędzia jest ostatnią
        # rzeczą, jaką model czyta przed pisaniem, więc „odeślij do BIP" bije
        # każdą instrukcję z promptu. Zakaz zostaje, ale zawężony do tego, co
        # chronił: nie wolno STRESZCZAĆ PRZEBIEGU niezatwierdzonej sesji.
        # Podanie terminu z ogłoszenia nigdy nie było tym samym.
        return ToolResult(
            content={
                "info": "Żaden skrót obrad nie został jeszcze zatwierdzony do publikacji.",
                "co_powiedziec": (
                    "To narzędzie zna tylko PRZEBIEG obrad, które już się odbyły, "
                    "i nic takiego nie jest jeszcze zatwierdzone do publikacji.\n"
                    "Jeśli pytanie dotyczy TERMINU posiedzenia — kiedy się zbiera "
                    "Rada albo komisja, o której godzinie, co będzie w porządku "
                    "obrad — to NIE JEST pytanie o skrót i masz szukać dalej: "
                    "zawołaj upcoming_events (kalendarz zna datę i godzinę), "
                    "a potem search_documents (ogłoszenia BIP o sesjach i "
                    "posiedzeniach komisji). Dopiero gdy oba wrócą puste, "
                    "powiedz, że terminu nie znasz.\n"
                    "Jeśli pytanie dotyczy PRZEBIEGU obrad: powiedz, że skrótów "
                    "jeszcze nie publikujemy — każdy przechodzi sprawdzenie przez "
                    "człowieka, zanim trafi na stronę — i odeślij po nagrania "
                    "i protokoły do BIP Gminy Rybno (bip.gminarybno.pl, "
                    "„Protokoły z sesji”). Przebiegu NIE streszczaj z pamięci "
                    "ani z innych źródeł."
                ),
            },
            empty=True,
            summary="brak zatwierdzonych skrótów obrad",
        )

    sesje, sources = [], []
    for row in rows:
        data = _summary(row)
        punkty = [
            {
                "temat": p.get("title"),
                "co_ustalono": (p.get("description") or "")[:POINT_CHARS] or None,
                "kto": p.get("speaker") or None,
                "cytat": p.get("quote") or None,
            }
            for p in (data.get("points") or [])
        ]

        # Uchwały: to, co powiedziano na sali (bez numerów) + numery z rejestru.
        uchwaly = [
            {"temat": r.get("subject"), "wynik": r.get("outcome")}
            for r in (data.get("resolutions") or [])
        ]

        sesje.append({
            "sesja": row.session_number,
            "data": row.session_date.date().isoformat() if row.session_date else None,
            "naglowek": data.get("headline"),
            "wprowadzenie": data.get("lead"),
            "punkty": punkty,
            "glosowania": uchwaly,
            "uchwaly_z_rejestru": await _acts_for(ctx, row),
        })
        sources.append({
            "type": "council_session",
            "id": row.id,
            "title": f"Sesja {row.session_number or ''} Rady Gminy Rybno".strip(),
            "url": row.page_url,
            "similarity": 1.0,
        })

    return ToolResult(
        content={"sesje": sesje},
        sources=sources,
        summary=f"{len(sesje)} skrót(y) obrad",
    )


register(Tool(
    name="council_sessions",
    provenance=prov.URZEDOWE,
    description=(
        "PRZEBIEG obrad Rady Gminy Rybno, które JUŻ SIĘ ODBYŁY: co Rada "
        "omawiała, co ustaliła, jak głosowała, kto zabierał głos, wraz "
        "z numerami podjętych uchwał. Używaj przy pytaniach o to, CO BYŁO "
        "(„co było na ostatniej sesji”, „co Rada uchwaliła w czerwcu”, „czy "
        "radni rozmawiali o drodze”). "
        "NIE UŻYWAJ do pytań o TERMIN — „kiedy jest sesja”, „kiedy zbiera się "
        "komisja”, „co będzie w porządku obrad” dotyczą posiedzenia, które "
        "dopiero nastąpi: to upcoming_events (data i godzina z kalendarza) "
        "oraz search_documents (ogłoszenie BIP z salą i porządkiem obrad). "
        "Zwraca WYŁĄCZNIE skróty zatwierdzone przez człowieka — gdy nic nie "
        "wraca, znaczy to, że skrót jeszcze nie został sprawdzony, a NIE że "
        "sesji nie było. Pytania o sam akt prawny (numer, status, data wejścia "
        "w życie) załatwia search_legal_acts."
    ),
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Ile ostatnich sesji, domyślnie 2, maksymalnie 5.",
            },
        },
        "required": [],
    },
    fn=council_sessions,
    status_message="Czytam skróty obrad Rady…",
    short=(
        "przebieg obrad Rady, które już się odbyły (tylko skróty zatwierdzone "
        "przez człowieka) — nie terminy przyszłych posiedzeń"
    ),
))
