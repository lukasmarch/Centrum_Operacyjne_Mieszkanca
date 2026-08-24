"""
Narzędzia agentów — rejestr i kontrakt (2026-08-22)

**Po co to powstało.** 21.08 o 19:07 mieszkaniec pyta „jak pogoda będzie jutro",
Przewodnik odpowiada „nie mam tego w aktualnej bazie". Prognoza była: 40 slotów
w `weather.forecast`, odświeżanych co godzinę. Agent jej nie przeczytał, bo
`_build_context` jej nie składał — a model nie miał jak o nią poprosić.

To nie był wyjątek, tylko reguła. Dane pobierało się PRZED zrozumieniem pytania,
na podstawie słów kluczowych:

    wanted = {k for k, kws in INTENT_KEYWORDS.items() if any(kw in msg for kw in kws)}

Pytanie „Godziny pracy" (18.08) nie trafiło w żaden wzorzec, więc Organizator
dostał komplet czterech sekcji i dopytał zamiast odpowiedzieć. Sześć takich
heurystyk żyło w pięciu plikach: `INTENT_KEYWORDS`, `PLACE_KEYWORDS`,
`_GENERIC_QUESTION`, `_is_place_query`, `_detect_place_category`,
`_classify_gus_query`.

**Co się zmienia.** Funkcja `_fetch_waste` była narzędziem od zawsze — miała
sygnaturę i zwracała strukturę. Brakowało jej dwóch rzeczy: opisu dla modelu
i tego, żeby to MODEL decydował o wywołaniu. Rejestr dokłada jedno i drugie.

**Dlaczego to nie jest tylko wygodniejszy `if`.** Pętla w `base_agent` biegnie
kilka razy, więc model widzi WYNIK narzędzia i może dobrać następne. Pytanie
„czy uchwała o sieci szkół ma sens przy naszej demografii" wymaga uchwały
(`legal_acts`), szeregu GUS (`gus_gmina_stats`) i zrozumienia, po co się sieć
szkół zmienia. Żadna heurystyka słów kluczowych tego nie połączy, bo musiałaby
z góry wiedzieć, że pytanie o uchwałę potrzebuje demografii.

**Granice, świadomie wąskie:**

* narzędzia są WYŁĄCZNIE do odczytu. Zapis (zgłoszenie, subskrypcja) to inna
  klasa ryzyka — model, który się pomyli przy odczycie, kłamie; przy zapisie
  zostawia ślad w bazie;
* `ToolContext.now` wstrzykiwane, nie `datetime.utcnow()` w środku funkcji.
  Regresji z 7.08 (Strażnik gubiący wyłączenie prądu) nie dałoby się powtórzyć
  po fakcie, gdyby czas brał się z zegara — patrz `straznik._fetch_alert_articles`;
* każde narzędzie ma `status_message` — użytkownik widzi „Sprawdzam prognozę…",
  a nie zastanawia się, czemu odpowiedź idzie dwie sekundy dłużej;
* schemat parametrów pisany wprost jako JSON Schema, nie generowany z sygnatury.
  Opis pola trafia do modelu i decyduje o trafności wywołania — to treść
  promptu, a nie metadana, którą można wyprowadzić z typu.

Test: `cd backend && python -m scripts.test_agent_tools`
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.logger import setup_logger

logger = setup_logger("AgentTools")


@dataclass
class ToolContext:
    """Wszystko, czego narzędzie potrzebuje poza własnymi argumentami.

    `user` bywa `None` (rozmowa anonimowa) — narzędzie nie może na nim polegać
    bez sprawdzenia. `now` jest naiwnym UTC, jak cała baza.
    """
    session: AsyncSession
    user: Optional[Any] = None
    now: datetime = field(default_factory=datetime.utcnow)
    # Bufor telemetrii (`services/tool_telemetry.ToolTelemetry`). Wypełnia go
    # PĘTLA w `base_agent`, nie narzędzie — narzędzie ma nie wiedzieć, że jest
    # mierzone, bo inaczej każde nowe musiałoby o tym pamiętać. `None` przy
    # wywołaniach z testów i skryptów: pomiar jest opcjonalny z założenia.
    telemetry: Optional[Any] = None


@dataclass
class ToolResult:
    """Wynik narzędzia w trzech rozłącznych warstwach.

    `content` idzie do modelu jako wiadomość `tool` (JSON). `sources` i `charts`
    NIE idą — wędrują obok, prosto do interfejsu. Model nie musi przepisywać
    adresu URL ani serii danych, żeby użytkownik je zobaczył; przepisywanie
    było jedynym powodem, dla którego mógłby je przekręcić.

    `empty=True` mówi „szukałem i nie ma", co jest inną informacją niż błąd
    narzędzia. Prompt agenta traktuje te dwa przypadki inaczej: pustka to
    odpowiedź („nie ma awarii"), błąd to powód, żeby się do niego przyznać.
    """
    content: Any
    sources: list = field(default_factory=list)
    charts: list = field(default_factory=list)
    empty: bool = False
    error: Optional[str] = None
    # Jedno zdanie dla CZŁOWIEKA o tym, co narzędzie znalazło („6 terminów
    # wywozu", „kalendarz pusty"). Idzie do interfejsu, nie do modelu — użytkownik
    # ma widzieć, na czym stoi odpowiedź, zanim ta odpowiedź powstanie.
    summary: Optional[str] = None
    # Żądanie przekazania pytania innemu agentowi (`tools/handoff.py`).
    # Wypełnia je WYŁĄCZNIE `przekaz_dalej`; dla każdego innego narzędzia
    # zostaje `None`. Pętla agenta traktuje je jak stop: przerywa rundy
    # i oddaje decyzję orkiestratorowi, bo agent bez zasięgu nie ma z czego
    # napisać odpowiedzi — a to, co napisze mimo wszystko, będzie odmową.
    handoff: Optional[dict] = None


ToolFn = Callable[..., Awaitable[ToolResult]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON Schema obiektu argumentów
    fn: ToolFn
    status_message: str       # widoczny krok pracy w UI
    # Jednozdaniowy opis do bloku „TWOJE NARZĘDZIA". Krótszy niż `description`,
    # bo tamten czyta model przy KAŻDYM wywołaniu, a ten trafia do promptu raz.
    short: str = ""
    # Własny limit czasu; `None` = wspólny `TOOL_TIMEOUT_S` z `base_agent`.
    # Ustawiają go WYŁĄCZNIE narzędzia, które nie są zapytaniem do bazy:
    # delegacja (`tools/delegation.py`) uruchamia całą pętlę innego agenta wraz
    # z jego wywołaniami modelu, więc mierzy się w dziesiątkach sekund, nie
    # w milisekundach. Wspólne 15 s ucinało Urzędnika w połowie pracy —
    # koordynator dostawał pustkę i pisał odpowiedź bez części o finansach.
    timeout_s: Optional[float] = None

    def schema(self) -> dict:
        """Definicja w formacie OpenAI `tools`."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


TOOL_REGISTRY: dict[str, Tool] = {}


def args_label(args: dict) -> str:
    """Argumenty wywołania w postaci czytelnej dla człowieka.

    „Rybno · 3 dni" zamiast `{"location": "Rybno", "days": 3}`. Interfejs
    pokazuje NIE TYLKO to, że agent coś sprawdza, ale CZEGO dokładnie szuka —
    bo to jest moment, w którym użytkownik widzi, że został źle zrozumiany
    („szukam w: Działdowo", gdy pytał o Rybno) i może poprawić pytanie, zamiast
    czekać na odpowiedź nie na temat.
    """
    if not args:
        return ""
    parts = []
    for key, value in args.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            parts.append(key if value else f"bez {key}")
        elif key in ("days", "hours"):
            parts.append(f"{value} {'dni' if key == 'days' else 'h'}")
        else:
            parts.append(str(value))
    return " · ".join(parts)[:80]


def register(tool: Tool) -> Tool:
    """Dopisuje narzędzie do rejestru. Nazwa musi być unikalna w całym projekcie
    — agent wskazuje narzędzia po nazwie, więc cicha podmianka byłaby cichą
    zmianą zachowania kilku agentów naraz."""
    if tool.name in TOOL_REGISTRY:
        raise ValueError(f"Narzędzie '{tool.name}' jest już zarejestrowane")
    TOOL_REGISTRY[tool.name] = tool
    return tool


def get(name: str) -> Optional[Tool]:
    return TOOL_REGISTRY.get(name)


def schemas_for(names: list[str]) -> list[dict]:
    """Definicje narzędzi dla `chat.completions(tools=...)`.

    Nieznana nazwa to błąd konfiguracji agenta, nie sytuacja do obsłużenia
    w locie — ale wywalenie się na starcie rozmowy byłoby gorsze od odpowiedzi
    bez jednego narzędzia, więc log i pomijamy.
    """
    schemas = []
    for name in names:
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            logger.error(f"Agent żąda nieznanego narzędzia '{name}' — pomijam")
            continue
        schemas.append(tool.schema())
    return schemas


def describe_for(names: list[str]) -> str:
    """Blok `system` „TWOJE NARZĘDZIA" — świadomość własnego zasięgu.

    Bez niego agent nie wie, czego NIE MA, i na pytanie spoza zakresu
    („uchwała z 2019") zgaduje albo milczy. Z nim potrafi powiedzieć, gdzie
    kończy się jego wiedza — a to jedyna odpowiedź, która nie wprowadza
    mieszkańca w błąd.

    Lista jest krótka celowo: rozdęty blok konkuruje o uwagę modelu
    z materiałem źródłowym — ten sam argument, przez który karta gminy
    ma limit 2 kB.
    """
    lines = []
    for name in names:
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            continue
        lines.append(f"- {tool.name} — {tool.short or tool.description}")
    if not lines:
        return ""

    # Zakończenie zależy od tego, czy agent ma dokąd oddać pytanie. Do etapu 7
    # brzmiało bezwarunkowo „powiedz WPROST, czego nie masz" — i działało aż
    # za dobrze: Redaktor odmówił analizy kondycji gminy, choć dane leżały
    # u GUS-Analityka i Urzędnika. Instrukcja była słuszna, dopóki odmowa była
    # jedynym uczciwym wyjściem. Gdy agent ma `przekaz_dalej`, uczciwym
    # wyjściem jest przekazanie pytania, a odmowa staje się szkodą.
    if "przekaz_dalej" in names:
        ending = (
            "Gdy pytanie wykracza poza to, co potrafisz sprawdzić, NIE ODMAWIAJ "
            "i nie pisz, czego nie potrafisz — zawołaj `przekaz_dalej`. Inny "
            "agent ma te dane i to on odpowie mieszkańcowi. Odmowa jest "
            "właściwa TYLKO wtedy, gdy nikt w systemie tego nie ma; wtedy "
            "powiedz wprost, czego brakuje, i wskaż, gdzie to znaleźć. "
            "Nie udawaj, że sprawdziłeś."
        )
    else:
        ending = (
            "Jeśli pytanie wykracza poza to, co potrafisz sprawdzić — powiedz "
            "WPROST, czego nie masz, i wskaż, gdzie mieszkaniec to znajdzie. "
            "Nie udawaj, że sprawdziłeś."
        )

    return (
        "TWOJE NARZĘDZIA (wołaj je zamiast zgadywać; wynik narzędzia ma "
        "pierwszeństwo przed twoją wiedzą ogólną):\n"
        + "\n".join(lines)
        + "\n\n" + ending
    )


# Import modułów narzędziowych rejestruje je w `TOOL_REGISTRY`. Trzyma się tu,
# na dole, bo moduły importują `register`/`Tool` z tego pliku.
from src.ai.tools import (  # noqa: E402,F401
    alerts, council, daily, delegation, handoff, knowledge, places, weather,
)
