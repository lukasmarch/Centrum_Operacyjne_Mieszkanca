"""
BaseAgent — wspólna pętla narzędziowa wszystkich agentów

Model sam decyduje, czego mu trzeba, widzi wynik i może dobrać następne
narzędzie (`ai/tools/__init__.py`). Migracja szła agentem po agencie, bo każdy
niósł własne wnioski z awarii (okna czasowe Strażnika, blok świeżego feedu
Redaktora), a przenoszenie ich hurtem oznaczałoby powtórzenie tych awarii naraz.

**Klasyczna ścieżka RAG zniknęła 24.08.2026** — retrieval przed pytaniem,
rerank, jeden strzał do modelu. Przez dwa dni była „ścieżką dla agentów jeszcze
nieprzeniesionych"; po Redaktorze i Urzędniku takich agentów nie ma. Kod bez
użytkowników, który wygląda na żywy, jest gorszy od jego braku: następna osoba
naprawiałaby ścieżkę, której nikt nie wywołuje i której nic nie sprawdza.

Wyszukiwarka nie zniknęła — stała się narzędziem (`ai/tools/knowledge.py`),
razem z rerankiem i synonimami. Zniknęło przepisywanie pytania: w tej ścieżce
zapytanie układa model, który ma przed sobą historię rozmowy.

`_stream` zostaje, bo używa go GUS-Analityk (własne `respond()` z wykresami).
"""
import asyncio
import json
import time
import openai
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator, Union
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import tools as agent_tools
from src.ai.tools import ToolContext, ToolResult
from src.services import provenance as prov
from src.config import settings
from src.services.gmina_facts import gmina_facts
from src.services.tool_telemetry import ToolTelemetry
from src.utils.logger import setup_logger

logger = setup_logger("BaseAgent")

# Ile sekund czekamy na jedno narzędzie. Zapytanie do bazy idzie w milisekundach;
# powyżej tego progu coś jest nie tak i lepiej odpowiedzieć bez tego narzędzia
# niż trzymać mieszkańca na wirującym kółku.
TOOL_TIMEOUT_S = 15.0

_POLISH_DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
_POLISH_MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
                  "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]


def get_datetime_context() -> str:
    """Return current date/time info in Polish for agent system messages."""
    now = datetime.now()
    day_name = _POLISH_DAYS[now.weekday()]
    month_name = _POLISH_MONTHS[now.month - 1]
    month = now.month
    if month in (12, 1, 2):
        season = "zima"
    elif month in (3, 4, 5):
        season = "wiosna"
    elif month in (6, 7, 8):
        season = "lato"
    else:
        season = "jesień"
    return (
        f"AKTUALNA DATA I CZAS: {day_name}, {now.day} {month_name} {now.year}, "
        f"godz. {now.strftime('%H:%M')} | Pora roku: {season}"
    )


# Reguła kompletności — dlaczego istnieje i dlaczego stoi TUTAJ.
#
# 5.09.2026, pomiar na produkcji: to samo pytanie („napisz szczegóły
# dzisiejszego nocnego biegu") puszczone przez cztery konfiguracje agenta.
# W dwóch z nich Przewodnik miał komplet narzędzi — kalendarz ORAZ wyszukiwarkę
# artykułów — i użył wyłącznie pierwszego. Odpowiedź niosła datę i organizatora,
# nie niosła miejsca ani godziny, czyli tego, o co pytano. Dołożenie narzędzia
# nie zmieniło NICZEGO, bo pętla kończy się wtedy, gdy model przestaje wołać
# narzędzia — a nie wtedy, gdy odpowiedź pokrywa pytanie.
#
# To jest różnica między „mam jakiś materiał" a „mam odpowiedź". Kod jej nie
# rozstrzygnie: tylko model wie, o co pytano. Może natomiast dostać polecenie,
# żeby zadał sobie to pytanie, zanim zacznie pisać.
#
# ⚠️ Stoi tu, a nie w bloku „TWOJE NARZĘDZIA", bo tamten ma twardy limit 2 kB
# (rozdęty konkuruje o uwagę z materiałem źródłowym) i jest go dziś 1976 B.
COMPLETENESS = """ZANIM ODPOWIESZ — sprawdź, czy masz to, O CO PYTANO:
- Wypisz sobie w myśli, czego dotyczyło pytanie (co? gdzie? kiedy? o której?).
  Jeśli któregoś z tych elementów nie ma w wynikach narzędzi, a mieszkaniec
  o niego pytał — zawołaj kolejne narzędzie, zanim zaczniesz pisać.
- Pierwszy niepusty wynik NIE kończy pracy. Kalendarz zna termin, wiadomości
  znają szczegóły, dokumenty znają procedurę — jedno pytanie często wymaga dwóch.
- Czego i tak nie znalazłeś, nazwij WPROST („godziny startu nie ma w ogłoszeniu”)
  i wskaż, gdzie mieszkaniec to sprawdzi. Nie zastępuj brakującego szczegółu
  ogólnikiem ani własnym domysłem."""


def base_context_messages() -> list[dict]:
    """Wiadomości `system`, które dostaje KAŻDY agent, zanim zobaczy KONTEKST.

    Pięciu agentów składa `messages` samodzielnie (GUS, Strażnik, Przewodnik,
    Organizator mają własne `respond()`), więc karta gminy dopisana ręcznie
    w jednym z nich prędzej czy później ominęłaby pozostałe. Jedno źródło
    zamiast pięciu kopii: nowy agent, który użyje tego helpera, dostaje
    komplet automatycznie.

    Kolejność jest znacząca — fakty stałe idą PRZED blokiem KONTEKST, żeby
    świeższy materiał źródłowy mógł je nadpisać (patrz `gmina_facts`).
    """
    return [
        {"role": "system", "content": get_datetime_context()},
        {"role": "system", "content": gmina_facts()},
        # Reguła pochodzenia idzie PO karcie gminy: karta jest materiałem,
        # a to jest instrukcja, co wolno zrobić z materiałem. Jedna kopia dla
        # wszystkich siedmiu agentów — patrz `services/provenance.py`.
        prov.precedence_message(),
        # Pochodzenie mówi, CZY wolno użyć materiału. Kompletność — czy materiału
        # w ogóle WYSTARCZA. Dwie różne bramki, obie przed pisaniem odpowiedzi.
        {"role": "system", "content": COMPLETENESS},
    ]


class BaseAgent:
    """Base class for all AI agents in the system"""

    name: str = "base"
    display_name: str = "Agent"
    description: str = ""
    avatar: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1500
    system_prompt: str = ""
    example_questions: list[str] = []

    # Nazwy narzędzi z `ai.tools.TOOL_REGISTRY`. Lista jest per agent, nie
    # globalna: definicje narzędzi wchodzą do KAŻDEGO wywołania (~80 tokenów
    # sztuka), a Urzędnik i GUS chodzą na gpt-4o.
    tools: list[str] = []

    # Ile razy model może sięgnąć po narzędzia, zanim musi odpowiedzieć.
    # Trzy, bo tyle wymaga realne złożenie odpowiedzi z dwóch źródeł: pobrać
    # dokument, zobaczyć czego w nim brakuje, dobrać dane liczbowe. Ostatnia
    # runda leci BEZ narzędzi, więc pętla nie ma jak się zapętlić.
    max_tool_rounds: int = 3

    # Czy agent może oddać pytanie innemu (`tools/handoff.py`). Domyślnie tak —
    # wyłącza to koordynator (on deleguje, nie przekazuje) oraz KAŻDY agent
    # wywołany w ramach delegacji, przez `allow_handoff=False`. Bez tego
    # drugiego pytanie odbijałoby się między agentami po okręgu.
    can_handoff: bool = True

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def respond(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: list[dict] = None,
        stream: bool = False,
        user=None,
        allow_handoff: bool = True,
    ) -> Union[dict, AsyncGenerator]:
        """Generate a response using RAG context (albo pętlę narzędziową)"""
        # Agent z narzędziami nie robi retrievalu na zapas — o materiał prosi
        # model, wtedy gdy go potrzebuje. Wyszukiwarka jest wówczas jednym
        # z narzędzi, a nie podatkiem doliczanym do każdego pytania.
        if self.tools:
            return await self._respond_with_tools(
                session, user_message, conversation_history, stream, user,
                allow_handoff,
            )

        # Agent BEZ narzędzi nie ma dziś czego robić: wszyscy sześciu albo mają
        # `tools`, albo własne `respond()` (GUS). Klasyczna ścieżka RAG —
        # retrieval przed pytaniem, rerank, jeden strzał — została usunięta
        # 24.08.2026 wraz z przeniesieniem Redaktora i Urzędnika, bo od tej
        # chwili nie miała ANI JEDNEGO użytkownika, a wyglądała na żywą.
        # Wyszukiwarka żyje dalej jako narzędzie: `ai/tools/knowledge.py`.
        raise NotImplementedError(
            f"Agent {self.name} nie ma narzędzi ani własnego respond(). "
            "Dodaj `tools = [...]` — patrz ai/tools/knowledge.py."
        )
    # ------------------------------------------------------------------
    # Ścieżka narzędziowa
    # ------------------------------------------------------------------

    async def _respond_with_tools(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: Optional[list[dict]],
        stream: bool,
        user,
        allow_handoff: bool = True,
    ) -> Union[dict, AsyncGenerator]:
        """Rozmowa, w której o dane prosi model, a nie wzorzec słów kluczowych."""
        tool_names = self._effective_tools(allow_handoff)
        messages = [
            {"role": "system", "content": self.system_prompt},
            *base_context_messages(),
        ]
        tools_block = agent_tools.describe_for(tool_names)
        if tools_block:
            messages.append({"role": "system", "content": tools_block})

        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        # Pomiar towarzyszy rozmowie od początku, bo interesują nas także
        # wywołania, po których nie ma odpowiedzi (timeout, rozłączony klient).
        ctx = ToolContext(
            session=session,
            user=user,
            telemetry=ToolTelemetry(
                agent_name=self.name,
                question=user_message,
                user_id=getattr(user, "id", None),
            ),
        )

        if stream:
            return await self._agentic_stream(messages, ctx, tool_names)
        return await self._agentic_complete(messages, ctx, tool_names)

    def _effective_tools(self, allow_handoff: bool) -> list[str]:
        """Narzędzia tej rozmowy = własne agenta + ewentualnie `przekaz_dalej`.

        Handoff dopisujemy TU, a nie do `tools` w każdej klasie agenta, bo
        inaczej sześć list trzeba by pamiętać przy każdej zmianie, a jedna
        zapomniana oznaczałaby agenta, który jako jedyny nadal odmawia.
        """
        if allow_handoff and self.can_handoff:
            return [*self.tools, "przekaz_dalej"]
        return list(self.tools)

    async def _call_tool(self, ctx: ToolContext, name: str, raw_args: str) -> ToolResult:
        """Wywołanie narzędzia opakowane pomiarem.

        Pomiar siedzi TU, a nie w każdej gałęzi `_run_tool`, bo interesuje nas
        także wywołanie, które padło — timeout i złe argumenty są najcenniejszą
        częścią tych danych, a to właśnie one wychodzą wcześniejszym `return`.
        """
        started = time.perf_counter()
        result = await self._run_tool(ctx, name, raw_args)
        duration_ms = int((time.perf_counter() - started) * 1000)

        telemetry = getattr(ctx, "telemetry", None)
        if telemetry is not None:
            if result.error:
                state = "error"
            elif result.empty:
                state = "empty"
            else:
                state = "done"
            try:
                parsed = json.loads(raw_args) if raw_args else {}
            except Exception:
                # Argumenty nie do sparsowania to sam w sobie wynik pomiaru:
                # znaczy, że model produkuje niepoprawny JSON dla tego schematu.
                parsed = {"_surowe": (raw_args or "")[:120]}
            telemetry.record(
                tool_name=name,
                state=state,
                error=result.error,
                args=parsed if isinstance(parsed, dict) else {"_surowe": str(parsed)[:120]},
                duration_ms=duration_ms,
            )
        return result

    async def _run_tool(self, ctx: ToolContext, name: str, raw_args: str) -> ToolResult:
        """Jedno wywołanie narzędzia — z limitem czasu i bez prawa do wywrócenia rozmowy.

        Każdy błąd wraca do modelu jako treść wiadomości `tool`, a nie jako
        wyjątek. Model, który wie, że narzędzie zawiodło, powie o tym
        mieszkańcowi; wyjątek zostawiłby go z komunikatem o błędzie serwera.
        """
        tool = agent_tools.get(name)
        if tool is None:
            logger.error(f"Model[{self.name}] zawołał nieznane narzędzie '{name}'")
            return ToolResult(content={"blad": f"Narzędzie '{name}' nie istnieje."},
                              error="unknown_tool")
        try:
            args = json.loads(raw_args) if raw_args else {}
            if not isinstance(args, dict):
                raise ValueError("argumenty muszą być obiektem JSON")
        except Exception as e:
            logger.warning(f"Tool[{name}] złe argumenty: {raw_args[:120]} ({e})")
            return ToolResult(content={"blad": f"Nieprawidłowe argumenty: {e}"},
                              error="bad_arguments")

        timeout = tool.timeout_s or TOOL_TIMEOUT_S
        try:
            result = await asyncio.wait_for(tool.fn(ctx, **args), timeout=timeout)
            logger.info(
                f"Tool[{self.name}:{name}] args={args} "
                f"{'PUSTO' if result.empty else 'ok'}"
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Tool[{name}] przekroczyło {timeout}s")
            return ToolResult(content={"blad": "Narzędzie nie odpowiedziało na czas."},
                              error="timeout")
        except TypeError as e:
            # Model podał argument spoza schematu — jego błąd, nie nasz crash.
            logger.warning(f"Tool[{name}] złe wywołanie: {e}")
            return ToolResult(content={"blad": f"Nieprawidłowe argumenty: {e}"},
                              error="bad_arguments")
        except Exception as e:
            logger.error(f"Tool[{name}] błąd: {e}", exc_info=True)
            return ToolResult(content={"blad": "Narzędzie zwróciło błąd."},
                              error="exception")

    @staticmethod
    def _tool_message(call: dict, result: ToolResult) -> dict:
        """Wynik narzędzia w postaci wiadomości `tool` dla modelu.

        Tu doklejamy `zrodlo` — jedyne przewężenie, przez które przechodzi
        KAŻDY wynik idący do modelu (obie ścieżki, strumień i non-stream,
        wszystkie gałęzie błędów). Bez tego „6682 osoby z GUS" i „około 180 km
        znikąd" docierają do modelu jako dwa nieodróżnialne obiekty JSON —
        patrz `services/provenance.py`.
        """
        payload = result.content
        if result.empty and isinstance(payload, dict):
            # Rozróżnienie, na którym stoi cała wiarygodność odpowiedzi:
            # „szukałem i nie ma" to fakt do zakomunikowania, a nie powód,
            # żeby model sięgnął po wiedzę ogólną i zgadywał.
            payload = {**payload, "pusty_wynik": True}
        tool = agent_tools.get(call["name"])
        zrodlo = prov.label(tool.provenance) if tool is not None else None
        if zrodlo and isinstance(payload, dict):
            # Etykieta NIE nadpisuje pola, które narzędzie ustawiło samo —
            # narzędzie zna swój materiał lepiej niż jego domyślna warstwa
            # (np. wynik mieszający uchwałę z artykułem prasowym).
            payload = {"zrodlo": zrodlo, **payload}
        return {
            "role": "tool",
            "tool_call_id": call["id"],
            "content": json.dumps(payload, ensure_ascii=False, default=str),
        }

    @staticmethod
    def _result_event(call: dict, result: ToolResult) -> dict:
        """Zdarzenie `status` opisujące, CO narzędzie zastało.

        Trzy stany, bo dla użytkownika to trzy różne sytuacje: znalazłem
        (można ufać odpowiedzi), nie ma tego w bazie (odpowiedź będzie
        ostrożna — i wiadomo dlaczego), narzędzie padło (to nasz problem,
        nie brak danych).
        """
        if result.error:
            state, message = "error", "nie udało się sprawdzić"
        elif result.empty:
            state = "empty"
            message = result.summary or "nie znalazłem tego w bazie"
        else:
            state = "done"
            message = result.summary or "gotowe"
        return {
            "type": "status",
            "tool": call["name"],
            "state": state,
            "message": message,
        }

    async def _execute_tool_calls(self, ctx: ToolContext, calls: list[dict]) -> dict:
        """Wykonuje komplet wywołań z jednej rundy i zbiera z nich trzy warstwy.

        **Po kolei, nie równolegle — i to nie jest przeoczenie.** Pierwsza wersja
        szła przez `asyncio.gather` i pierwszy test na żywym modelu ją obalił:
        „Co robić w weekend" wywołało prognozę i kalendarz naraz, a drugie
        zapytanie dostało `InvalidRequestError: This session is provisioning
        a new connection; concurrent operations are not permitted`.
        `AsyncSession` obsługuje jedną operację naraz — wszystkie narzędzia
        dzielą sesję requestu, więc równoległość oznaczałaby tu wyścig.

        Cena jest znikoma: to zapytania do lokalnej bazy, kilka milisekund
        każde. Gdyby pojawiło się narzędzie naprawdę wolne (HTTP do obcego API),
        wtedy — i tylko wtedy — warto dać mu własne połączenie.
        """
        tool_messages, sources, charts = [], [], []
        handoff = None
        for call in calls:
            result = await self._call_tool(ctx, call["name"], call["arguments"])
            tool_messages.append(self._tool_message(call, result))
            sources.extend(result.sources)
            charts.extend(result.charts)
            # Pierwszy handoff wygrywa i reszta rundy i tak przestaje mieć
            # znaczenie — pytanie przejmuje inny agent. Nie przerywamy jednak
            # pętli: wywołania z tej samej rundy mają się domknąć i zostawić
            # ślad w telemetrii, inaczej mierzylibyśmy tylko część prawdy.
            if result.handoff and handoff is None:
                handoff = result.handoff

        return {"messages": tool_messages, "sources": sources, "charts": charts,
                "handoff": handoff}

    @staticmethod
    def _accumulate_tool_calls(acc: dict, deltas) -> None:
        """Skleja wywołania narzędzi rozsypane po chunkach strumienia.

        OpenAI tnie `arguments` na kawałki, a `index` jest jedynym stabilnym
        identyfikatorem, dopóki nie dojdzie `id`.
        """
        for tc in deltas:
            slot = acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if tc.id:
                slot["id"] = tc.id
            if tc.function:
                if tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function.arguments:
                    slot["arguments"] += tc.function.arguments

    def _round_kwargs(self, messages: list[dict], allow_tools: bool,
                      tool_names: Optional[list[str]] = None) -> dict:
        """Argumenty jednej rundy. Ostatnia leci bez `tools` — model nie ma
        wtedy wyjścia poza napisaniem odpowiedzi, więc pętla zawsze się kończy."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if allow_tools:
            schemas = agent_tools.schemas_for(
                self.tools if tool_names is None else tool_names
            )
            if schemas:
                kwargs["tools"] = schemas
                kwargs["tool_choice"] = "auto"
        return kwargs

    async def _agentic_complete(self, messages: list[dict], ctx: ToolContext,
                                tool_names: Optional[list[str]] = None) -> dict:
        """Wariant bez streamu — używany przez testy i wywołania non-stream."""
        messages = list(messages)
        sources, charts, tokens = [], [], 0

        for round_idx in range(self.max_tool_rounds):
            allow_tools = round_idx < self.max_tool_rounds - 1
            response = await self.client.chat.completions.create(
                **self._round_kwargs(messages, allow_tools, tool_names)
            )
            tokens += response.usage.total_tokens if response.usage else 0
            choice = response.choices[0].message

            if not choice.tool_calls:
                return {
                    "answer": choice.content or "",
                    "sources": sources,
                    "chart_data": charts,
                    "tokens_used": tokens,
                    "model": self.model,
                    "agent_name": self.name,
                }

            calls = [
                {"id": c.id, "name": c.function.name, "arguments": c.function.arguments}
                for c in choice.tool_calls
            ]
            messages.append({
                "role": "assistant",
                "content": choice.content,
                "tool_calls": [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in calls
                ],
            })
            executed = await self._execute_tool_calls(ctx, calls)
            messages.extend(executed["messages"])
            sources.extend(executed["sources"])
            charts.extend(executed["charts"])
            if ctx.telemetry is not None:
                await ctx.telemetry.flush()

            # Agent oddał pytanie — dalsze rundy byłyby pisaniem odpowiedzi,
            # której nie ma z czego napisać. Decyzję, kto przejmuje, podejmuje
            # `Orchestrator.run()`; tu tylko meldujemy fakt.
            if executed["handoff"]:
                return {
                    "answer": "", "sources": sources, "chart_data": charts,
                    "tokens_used": tokens, "model": self.model,
                    "agent_name": self.name, "handoff": executed["handoff"],
                }

        return {
            "answer": "", "sources": sources, "chart_data": charts,
            "tokens_used": tokens, "model": self.model, "agent_name": self.name,
        }

    async def _agentic_stream(self, messages: list[dict], ctx: ToolContext,
                              tool_names: Optional[list[str]] = None) -> AsyncGenerator:
        """Pętla narzędziowa ze strumieniem — bez dopłaty, gdy narzędzia nie są potrzebne.

        Strumień rusza OD RAZU z definicjami narzędzi. Gdy model postanawia
        odpowiedzieć tekstem, litery lecą do przeglądarki tak samo jak dotąd —
        żadnej dodatkowej rundy „czy potrzebujesz narzędzia". Dopiero gdy w
        strumieniu pojawią się `tool_calls`, dokładamy kolejny przebieg,
        przykryty widocznym krokiem pracy.
        """
        agent_self = self
        outer_messages = list(messages)

        async def generate():
            messages = outer_messages
            sources, charts, tokens = [], [], 0

            for round_idx in range(agent_self.max_tool_rounds):
                allow_tools = round_idx < agent_self.max_tool_rounds - 1
                stream = await agent_self.client.chat.completions.create(
                    **agent_self._round_kwargs(messages, allow_tools, tool_names),
                    stream=True,
                    stream_options={"include_usage": True},
                )

                text_buf = ""
                calls_acc: dict = {}
                async for chunk in stream:
                    if chunk.usage:
                        tokens += chunk.usage.total_tokens
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta.tool_calls:
                        agent_self._accumulate_tool_calls(calls_acc, delta.tool_calls)
                    if delta.content:
                        text_buf += delta.content
                        yield json.dumps({"type": "chunk", "content": delta.content}) + "\n"

                if not calls_acc:
                    if charts:
                        yield json.dumps({"type": "chart_data", "charts": charts}) + "\n"
                    yield json.dumps({"type": "sources", "sources": sources}) + "\n"
                    yield json.dumps({
                        "type": "done",
                        "full_content": text_buf,
                        "model": agent_self.model,
                        "agent_name": agent_self.name,
                        "tokens_used": tokens,
                    }) + "\n"
                    return

                calls = [calls_acc[i] for i in sorted(calls_acc)]
                messages.append({
                    "role": "assistant",
                    "content": text_buf or None,
                    "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": c["arguments"]}}
                        for c in calls
                    ],
                })

                # Praca agenta na żywo: przed każdym narzędziem CO sprawdza
                # i CZEGO w nim szuka, po nim — co zastał. Użytkownik, który
                # widzi „Szukam miejsc w okolicy · Działdowo", gdy pytał
                # o Rybno, wie od razu, że został źle zrozumiany — i poprawia
                # pytanie, zamiast czytać odpowiedź nie na temat.
                empty_count = 0
                handoff = None
                for call in calls:
                    tool = agent_tools.get(call["name"])
                    try:
                        parsed_args = json.loads(call["arguments"] or "{}")
                    except Exception:
                        parsed_args = {}
                    yield json.dumps({
                        "type": "status",
                        "tool": call["name"],
                        "state": "running",
                        "message": tool.status_message if tool else f"Wywołuję {call['name']}…",
                        "detail": agent_tools.args_label(parsed_args if isinstance(parsed_args, dict) else {}),
                    }) + "\n"

                    result = await agent_self._call_tool(ctx, call["name"], call["arguments"])
                    yield json.dumps(agent_self._result_event(call, result)) + "\n"

                    if result.empty or result.error:
                        empty_count += 1
                    if result.handoff and handoff is None:
                        handoff = result.handoff
                    messages.append(agent_self._tool_message(call, result))
                    sources.extend(result.sources)
                    charts.extend(result.charts)

                # Zapis PO RUNDZIE, nie na końcu odpowiedzi: strumień kończy się
                # też przez rozłączenie przeglądarki, a `finally` generatora
                # asynchronicznego nie może wtedy bezpiecznie czekać na `await`
                # (`GeneratorExit`). Rundy jest najwyżej trzy.
                if ctx.telemetry is not None:
                    await ctx.telemetry.flush()

                # Agent oddaje pytanie. Strumień kończy się TU — odpowiedź
                # napisze następny agent, a ten nie ma z czego jej napisać.
                #
                # `discard_text` mówi frontowi, żeby skasował to, co już
                # pokazał. Prompt zabrania pisać cokolwiek przed wywołaniem
                # `przekaz_dalej`, ale model bywa rozmowny: gdyby zdążył
                # wypuścić „Niestety nie mam…", mieszkaniec zobaczyłby odmowę
                # sklejoną z odpowiedzią, czyli dokładnie to, co naprawiamy.
                if handoff:
                    yield json.dumps({
                        "type": "handoff",
                        "from": agent_self.name,
                        "to": handoff.get("to"),
                        "reason": handoff.get("reason"),
                        "discard_text": bool(text_buf.strip()),
                        "tokens_used": tokens,
                    }) + "\n"
                    return

                # Wszystko puste = odpowiedź powstanie mimo braku materiału.
                # Lepiej uprzedzić, niż zostawić użytkownika z wrażeniem, że
                # agent coś sprawdził i potwierdził.
                if calls and empty_count == len(calls):
                    yield json.dumps({
                        "type": "status",
                        "state": "warning",
                        "message": "Nie znalazłem tego w danych — odpowiadam ostrożnie",
                    }) + "\n"

            # Wyjście awaryjne: ostatnia runda leci bez `tools`, więc tu nie
            # powinniśmy trafić. Gdyby jednak — strumień musi zostać domknięty,
            # inaczej przeglądarka wisi na otwartym SSE.
            logger.error(f"Agent[{agent_self.name}] wyczerpał rundy narzędziowe")
            yield json.dumps({
                "type": "done", "full_content": "", "model": agent_self.model,
                "agent_name": agent_self.name, "tokens_used": tokens,
            }) + "\n"

        return generate()

    async def _stream(
        self,
        messages: list[dict],
        sources: list[dict],
        context_count: Optional[int] = None,
    ) -> AsyncGenerator:
        """Stream response via SSE"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            stream_options={"include_usage": True}
        )

        async def generate():
            # Widoczny krok pracy agenta (wzorzec Perplexity) — przed pierwszym
            # chunkiem, żeby użytkownik widział co się wydarzyło w tle
            if context_count is not None:
                # Krok dokonany, nie trwający — stąd jawny `state`, inaczej
                # interfejs pokazywałby przy nim kręcące się kółko.
                if context_count > 0:
                    step = f"Przeszukałem bazę wiedzy — {context_count} trafnych materiałów źródłowych"
                    state = "done"
                else:
                    step = "Brak trafnych materiałów w bazie — odpowiadam na podstawie wiedzy ogólnej"
                    state = "empty"
                yield json.dumps({"type": "status", "state": state, "message": step}) + "\n"

            full_content = ""
            total_tokens = 0
            async for chunk in stream:
                if chunk.usage:
                    total_tokens = chunk.usage.total_tokens
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield json.dumps({"type": "chunk", "content": content}) + "\n"

            yield json.dumps({"type": "sources", "sources": sources}) + "\n"
            yield json.dumps({
                "type": "done",
                "full_content": full_content,
                "model": self.model,
                "agent_name": self.name,
                "tokens_used": total_tokens
            }) + "\n"

        return generate()

    def to_dict(self) -> dict:
        """Serialize agent info for API response"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "avatar": self.avatar,
            "example_questions": self.example_questions
        }
