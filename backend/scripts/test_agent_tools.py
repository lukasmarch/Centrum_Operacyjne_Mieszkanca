"""
Sprawdza warstwę narzędzi agentów — `python -m scripts.test_agent_tools [--db]`.

Trzy rzeczy, każda z innego powodu:

1. **Rejestr** — schematy muszą być poprawnym JSON Schema, bo idą wprost do
   OpenAI, a błąd w nich wychodzi dopiero w rozmowie z mieszkańcem.
2. **Pętla** — na atrapie klienta, bez kosztów modelu. Pętla narzędziowa ma
   jedną właściwość, której nie wolno stracić: MUSI się kończyć. Ostatnia runda
   leci bez `tools`, więc model nie ma jak prosić w nieskończoność — i dokładnie
   to tu sprawdzamy, razem z wykonaniem równoległym i z tym, że błąd narzędzia
   wraca do modelu, zamiast wywracać rozmowę.
3. **Pogoda** (`--db`) — czy prognoza faktycznie wychodzi z bazy. To ten sam
   przypadek, od którego cała praca się zaczęła: 21.08 agent odpowiedział
   „nie mam tego w bazie", mając w niej 40 slotów prognozy.
"""
import asyncio
import json
import sys

from src.ai.agents.base_agent import BaseAgent
from src.ai.tools import TOOL_REGISTRY, Tool, ToolContext, ToolResult, describe_for, schemas_for

failures: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}{f' — {detail}' if detail else ''}")
        failures.append(label)


# ---------------------------------------------------------------- rejestr
print("\n== Rejestr narzędzi ==")
check(len(TOOL_REGISTRY) > 0, f"rejestr niepusty ({len(TOOL_REGISTRY)} narzędzi)")

for name, tool in TOOL_REGISTRY.items():
    schema = tool.schema()
    fn = schema["function"]
    check(fn["name"] == name, f"{name}: nazwa zgodna ze schematem")
    check(
        len(fn["description"]) >= 40,
        f"{name}: opis mówi modelowi, KIEDY użyć",
        "krótki opis = narzędzie wołane nie wtedy, kiedy trzeba",
    )
    check(
        fn["parameters"].get("type") == "object" and "properties" in fn["parameters"],
        f"{name}: parametry to obiekt JSON Schema",
    )
    check(bool(tool.status_message), f"{name}: ma widoczny krok pracy dla UI")
    # Schemat musi się serializować — OpenAI dostaje go jako JSON.
    try:
        json.dumps(schema)
        check(True, f"{name}: schemat serializuje się do JSON")
    except Exception as e:
        check(False, f"{name}: schemat serializuje się do JSON", str(e))

print("\n== Blok świadomości ==")
block = describe_for(list(TOOL_REGISTRY))
check("TWOJE NARZĘDZIA" in block, "blok ma nagłówek")
check(
    "WPROST" in block,
    "blok każe przyznać się do granic wiedzy",
    "bez tego agent zgaduje zamiast powiedzieć, czego nie ma",
)
check(
    len(block.encode("utf-8")) < 2048,
    f"blok nie rozdyma promptu ({len(block.encode('utf-8'))} B)",
    "rozdęty blok konkuruje o uwagę modelu z materiałem źródłowym",
)
check(schemas_for(["nie_ma_takiego"]) == [], "nieznane narzędzie jest pomijane, nie wywala agenta")


# ------------------------------------------------------------------ atrapy
class _Fn:
    def __init__(self, name, arguments):
        self.name, self.arguments = name, arguments


class _Call:
    def __init__(self, idx, name, arguments):
        self.id, self.index = f"call_{idx}", idx
        self.type = "function"
        self.function = _Fn(name, arguments)


class _Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content, self.tool_calls = content, tool_calls


class _Choice:
    def __init__(self, message):
        self.message = message


class _Usage:
    total_tokens = 100


class _Response:
    def __init__(self, message):
        self.choices, self.usage = [_Choice(message)], _Usage()


class FakeCompletions:
    """Odtwarza zachowanie OpenAI: kolejne rundy z zaplanowanego scenariusza."""

    def __init__(self, script):
        self.script, self.calls_seen = list(script), []

    async def create(self, **kwargs):
        self.calls_seen.append(kwargs)
        step = self.script.pop(0) if self.script else ("text", "koniec")
        kind, payload = step
        if kind == "tools":
            # Model nie może zażądać narzędzi, których mu nie podano — tak samo
            # zachowuje się prawdziwe API. To jedyny hamulec pętli, więc atrapa
            # musi go odtwarzać wiernie, a nie omijać.
            if "tools" not in kwargs:
                return _Response(_Msg(content="musiałem odpowiedzieć"))
            return _Response(_Msg(tool_calls=[
                _Call(i, name, args) for i, (name, args) in enumerate(payload)
            ]))
        return _Response(_Msg(content=payload))


class FakeClient:
    def __init__(self, script):
        self.chat = type("chat", (), {"completions": FakeCompletions(script)})()


async def _echo(ctx: ToolContext, value: str = "") -> ToolResult:
    return ToolResult(content={"echo": value}, sources=[{"title": f"src:{value}"}])


async def _boom(ctx: ToolContext) -> ToolResult:
    raise RuntimeError("narzędzie padło")


async def _slow(ctx: ToolContext) -> ToolResult:
    await asyncio.sleep(30)
    return ToolResult(content={})


for name, fn in (("_t_echo", _echo), ("_t_boom", _boom), ("_t_slow", _slow)):
    if name not in TOOL_REGISTRY:
        TOOL_REGISTRY[name] = Tool(
            name=name, description="atrapa testowa " + name,
            parameters={"type": "object", "properties": {
                "value": {"type": "string", "description": "cokolwiek"}}, "required": []},
            fn=fn, status_message=f"Testuję {name}…",
        )


class _StubAgent(BaseAgent):
    name = "stub"
    tools = ["_t_echo", "_t_boom"]
    system_prompt = "test"

    def __init__(self, script):
        self.client = FakeClient(script)


async def run_loop_tests():
    print("\n== Pętla narzędziowa ==")

    # 1. Bez narzędzi — zero dodatkowych rund, tekst leci od razu.
    agent = _StubAgent([("text", "zwykła odpowiedź")])
    out = await agent._agentic_complete([{"role": "user", "content": "?"}],
                                        ToolContext(session=None))
    check(out["answer"] == "zwykła odpowiedź", "odpowiedź bez narzędzi wraca w jednej rundzie")
    check(len(agent.client.chat.completions.calls_seen) == 1, "jedno wywołanie modelu")

    # 2. Dwa narzędzia w jednej rundzie — oba wyniki wracają do modelu.
    #    Wykonanie jest sekwencyjne, bo `AsyncSession` nie znosi współbieżności
    #    (pierwsza wersja szła przez `gather` i padała na drugim zapytaniu).
    agent = _StubAgent([
        ("tools", [("_t_echo", '{"value":"a"}'), ("_t_echo", '{"value":"b"}')]),
        ("text", "odpowiedź po narzędziach"),
    ])
    out = await agent._agentic_complete([{"role": "user", "content": "?"}],
                                        ToolContext(session=None))
    check(out["answer"] == "odpowiedź po narzędziach", "model odpowiada po wynikach narzędzi")
    check(len(out["sources"]) == 2, "źródła z obu narzędzi trafiają obok odpowiedzi")
    second = agent.client.chat.completions.calls_seen[1]["messages"]
    tool_msgs = [m for m in second if m.get("role") == "tool"]
    check(len(tool_msgs) == 2, "oba wyniki wróciły do modelu jako wiadomości `tool`")
    check(all("echo" in m["content"] for m in tool_msgs), "treść wyniku dociera do modelu")

    # 3. Błąd narzędzia nie wywraca rozmowy — wraca do modelu jako fakt.
    agent = _StubAgent([("tools", [("_t_boom", "{}")]), ("text", "przyznaję się do błędu")])
    out = await agent._agentic_complete([{"role": "user", "content": "?"}],
                                        ToolContext(session=None))
    check(out["answer"] == "przyznaję się do błędu", "błąd narzędzia nie przerywa odpowiedzi")
    err_msg = [m for m in agent.client.chat.completions.calls_seen[1]["messages"]
               if m.get("role") == "tool"][0]
    check("blad" in err_msg["content"], "model DOWIADUJE SIĘ o błędzie narzędzia")

    # 4. Nieznane narzędzie — model dostaje odmowę, nie wyjątek.
    agent = _StubAgent([("tools", [("nie_ma_takiego", "{}")]), ("text", "ok")])
    out = await agent._agentic_complete([{"role": "user", "content": "?"}],
                                        ToolContext(session=None))
    check(out["answer"] == "ok", "nieznane narzędzie nie wywraca rozmowy")

    # 5. Pętla MUSI się kończyć: model prosi o narzędzia w każdej rundzie.
    agent = _StubAgent([("tools", [("_t_echo", '{"value":"x"}')])] * 10)
    out = await agent._agentic_complete([{"role": "user", "content": "?"}],
                                        ToolContext(session=None))
    rounds = len(agent.client.chat.completions.calls_seen)
    check(rounds <= agent.max_tool_rounds,
          f"pętla kończy się po {agent.max_tool_rounds} rundach (było {rounds})")
    check("tools" not in agent.client.chat.completions.calls_seen[-1],
          "ostatnia runda leci BEZ narzędzi — model musi odpowiedzieć")

    # 6. Strumień: statusy przed treścią, `done` na końcu, `sources` osobno.
    agent = _StubAgent([("tools", [("_t_echo", '{"value":"s"}')]), ("text", "strumień")])

    class _StreamFake(FakeCompletions):
        async def create(self, **kwargs):
            resp = await FakeCompletions.create(self, **kwargs)
            msg = resp.choices[0].message

            async def gen():
                class _D:
                    def __init__(s, content=None, tool_calls=None):
                        s.content, s.tool_calls = content, tool_calls

                class _C:
                    def __init__(s, delta):
                        s.delta = delta

                class _Ch:
                    def __init__(s, delta):
                        s.choices, s.usage = [_C(delta)], None

                if msg.tool_calls:
                    yield _Ch(_D(tool_calls=msg.tool_calls))
                else:
                    for ch in (msg.content or ""):
                        yield _Ch(_D(content=ch))
            return gen()

    agent.client.chat.completions = _StreamFake([
        ("tools", [("_t_echo", '{"value":"s"}')]), ("text", "strumień"),
    ])
    events = []
    stream = await agent._agentic_stream([{"role": "user", "content": "?"}],
                                         ToolContext(session=None))
    async for line in stream:
        events.append(json.loads(line))
    kinds = [e["type"] for e in events]
    check("status" in kinds, "użytkownik widzi, JAKIE narzędzie pracuje")
    check(kinds.index("status") < kinds.index("chunk"), "status idzie PRZED treścią")
    check(kinds[-1] == "done", "strumień domyka się zdarzeniem `done`")
    check("".join(e["content"] for e in events if e["type"] == "chunk") == "strumień",
          "treść dociera w całości")

    # 7. Limit czasu — wolne narzędzie nie trzyma mieszkańca w nieskończoność.
    agent = _StubAgent([("text", "x")])
    agent.tools = ["_t_slow"]
    import src.ai.agents.base_agent as ba
    original = ba.TOOL_TIMEOUT_S
    ba.TOOL_TIMEOUT_S = 0.05
    try:
        result = await agent._call_tool(ToolContext(session=None), "_t_slow", "{}")
        check(result.error == "timeout", "narzędzie po limicie czasu zwraca błąd, nie zawiesza")
    finally:
        ba.TOOL_TIMEOUT_S = original


# ------------------------------------------------------- składanie prognozy
def run_forecast_unit_tests():
    """Bez bazy — te reguły muszą działać niezależnie od tego, co w niej stoi."""
    from datetime import datetime, timedelta, timezone
    from src.ai.tools.weather import build_days

    print("\n== Składanie prognozy ==")
    now = datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc)

    def slot(hours_from_now, temp, pop=0.0, desc="pochmurno"):
        return {
            "dt": int((now + timedelta(hours=hours_from_now)).timestamp()),
            "temp": temp, "pop": pop, "description": desc, "wind_speed": 3.0,
        }

    dni, charts = build_days(
        [slot(1, 20), slot(4, 24, 0.4), slot(7, 18),          # dziś
         slot(25, 15), slot(28, 22, 0.9, "deszcz")],           # jutro
        now, days=3,
    )
    check(len(dni) == 2, f"sloty grupują się w doby ({len(dni)})")
    check(dni[0]["dzien"] == "dziś" and dni[1]["dzien"] == "jutro",
          "pierwsze dwa dni etykietowane jako dziś i jutro")
    check(dni[0]["temp_min_c"] == 18 and dni[0]["temp_max_c"] == 24,
          "min/max liczone ze wszystkich slotów doby")
    check(dni[1]["szansa_opadow_proc"] == 90,
          "szansa opadów to MAKSIMUM z doby, nie średnia")
    check(len(charts) == len(dni), "widget dostaje tyle samo dni co tekst")

    # Prognoza sprzed trzech dni — dokładnie stan lokalnej bazy 22.08.
    stale = [slot(-72 + i * 3, 20) for i in range(8)]
    dni_stale, _ = build_days(stale, now, days=3)
    check(dni_stale == [],
          "prognoza z przeszłości NIE wraca jako aktualna",
          "bez tego agent podałby pogodę sprzed trzech dni jako jutrzejszą")

    # Slot trwający właśnie teraz musi przetrwać — inaczej o 11:59 znika
    # prognoza na godziny 9-12.
    dni_now, _ = build_days([slot(-1, 21)], now, days=1)
    check(len(dni_now) == 1, "slot trwający TERAZ zostaje w prognozie")

    # Limit dni respektowany nawet przy pełnym pakiecie z OWM.
    full = [slot(i * 3, 20) for i in range(40)]
    check(len(build_days(full, now, days=2)[0]) == 2, "parametr `days` ogranicza wynik")


# -------------------------------------------------------------- baza (--db)
async def run_db_tests():
    print("\n== Pogoda z bazy (--db) ==")
    from src.database.connection import async_session
    from src.ai.tools.weather import current_weather, weather_forecast

    async with async_session() as session:
        ctx = ToolContext(session=session)

        now = await current_weather(ctx)
        check(not now.empty, "pomiar bieżący jest w bazie",
              "uruchom weather_job albo POST /api/weather/update")
        if not now.empty:
            check("temperatura_c" in now.content, "pomiar zawiera temperaturę")

        fc = await weather_forecast(ctx, days=3)
        if fc.empty:
            # Lokalnie `SCHEDULER_ENABLED=false`, więc prognoza bywa sprzed dni.
            # To nie porażka narzędzia — narzędzie zachowało się poprawnie,
            # odmawiając podania przeterminowanych danych.
            print("  UWAGA prognoza w bazie jest przeterminowana — narzędzie "
                  "poprawnie odmawia. Odśwież: POST /api/weather/update")
            check("co_powiedziec" in fc.content,
                  "pusta prognoza mówi modelowi, co zrobić zamiast zgadywać")
        else:
            dni = fc.content["dni"]
            check(1 <= len(dni) <= 3, f"prognoza respektuje `days` ({len(dni)} dni)")
            check(dni[0]["dzien"] in ("dziś", "jutro"),
                  f"pierwszy dzień jest etykietowany po ludzku ({dni[0]['dzien']})")
            check(all(d["temp_min_c"] <= d["temp_max_c"] for d in dni),
                  "min nie przekracza max w żadnym dniu")
            check(all(0 <= d["szansa_opadow_proc"] <= 100 for d in dni),
                  "szansa opadów mieści się w 0-100%")
            check(bool(fc.charts) and fc.charts[0]["chart_type"] == "forecast",
                  "prognoza niesie dane widgetu obok tekstu")

        # Miejscowość bez stacji — mieszkaniec Dębienia nie może zostać z pustką.
        # Sprawdzane na pomiarze bieżącym, bo ten nie zależy od świeżości prognozy.
        deb = await current_weather(ctx, location="Dębień")
        check(not deb.empty, "miejscowość bez czujnika dostaje najbliższą stację")
        if not deb.empty:
            check(deb.content["lokalizacja"] == "Rybno", "podstawiona stacja to Rybno")
            check("uwaga" in deb.content, "podstawienie stacji jest powiedziane wprost")


async def run_live_tests():
    """Prawdziwy model, prawdziwa baza — czy narzędzia są wołane WTEDY, KIEDY TRZEBA.

    Atrapa sprawdza mechanikę pętli, ale nie odpowiada na pytanie, które
    zdecydowało o całej tej pracy: czy model sam z siebie sięgnie po prognozę,
    gdy mieszkaniec pyta o jutro. Cztery pytania, w tym jedno kontrolne —
    agent, który woła narzędzia na wszystko, jest tak samo zepsuty jak ten,
    który nie woła ich wcale, tylko drożej.

    Koszt: kilka wywołań gpt-4o-mini, rzędu jednego centa.
    """
    from src.ai.agents.przewodnik import PrzewodnikAgent
    from src.database.connection import async_session

    print("\n== Model na żywo (--live) ==")

    cases = [
        ("Jak pogoda będzie jutro?", {"weather_forecast"}, None),
        ("Co robić w weekend w Rybnie?", {"weather_forecast", "upcoming_events"}, None),
        ("Gdzie zjeść w okolicy?", {"local_places"}, None),
        # Kontrolne: odpowiedź jest w karcie gminy, żadne narzędzie nie pomoże.
        ("Kto jest wójtem gminy Rybno?", set(), "Węgrzynowski"),
    ]

    for question, expected_any, must_contain in cases:
        agent = PrzewodnikAgent()
        used: list = []
        original = agent._call_tool

        async def spy(ctx, name, args, _orig=original, _used=used):
            _used.append(name)
            return await _orig(ctx, name, args)

        agent._call_tool = spy

        async with async_session() as session:
            out = await agent._agentic_complete(
                [
                    {"role": "system", "content": agent.system_prompt},
                    *__import__("src.ai.agents.base_agent", fromlist=["x"]).base_context_messages(),
                    {"role": "system", "content": describe_for(agent.tools)},
                    {"role": "user", "content": question},
                ],
                ToolContext(session=session),
            )

        print(f"\n  „{question}”")
        print(f"    narzędzia: {used or '—'}")
        print(f"    odpowiedź: {(out['answer'] or '')[:150]}…")

        if expected_any:
            check(bool(set(used) & expected_any),
                  f"„{question[:32]}…” → sięga po {' lub '.join(sorted(expected_any))}",
                  f"zawołał: {used}")
        else:
            check(not used,
                  f"„{question[:32]}…” → NIE woła narzędzi bez potrzeby",
                  f"zawołał: {used}")
        if must_contain:
            check(must_contain.lower() in (out["answer"] or "").lower(),
                  f"odpowiedź zawiera: {must_contain}")
        check(bool((out["answer"] or "").strip()), "odpowiedź nie jest pusta")


async def main():
    run_forecast_unit_tests()
    await run_loop_tests()
    if "--db" in sys.argv or "--live" in sys.argv:
        await run_db_tests()
    else:
        print("\n(pomijam testy bazy — dodaj --db)")

    if "--live" in sys.argv:
        await run_live_tests()
    else:
        print("(pomijam testy z modelem — dodaj --live, kosztuje ~1 grosz)")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"BŁĘDY: {len(failures)}")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Wszystko OK")


if __name__ == "__main__":
    asyncio.run(main())
