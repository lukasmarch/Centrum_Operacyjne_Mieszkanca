"""
BaseAgent - abstract base for all specialized AI agents

Dwie ścieżki odpowiedzi, świadomie obie utrzymywane:

* **`tools` puste** → dotychczasowa ścieżka RAG: retrieval przed rozmową,
  rerank, jeden strzał do modelu. Tak działają agenci, których jeszcze nie
  przeniesiono;
* **`tools` niepuste** → pętla narzędziowa: model sam decyduje, czego mu trzeba,
  widzi wynik i może dobrać następne narzędzie (`ai/tools/__init__.py`).

Migracja idzie agentem po agencie, bo każdy niesie własne wnioski z awarii
(okna czasowe Strażnika, blok świeżego feedu Redaktora) i przenoszenie ich
hurtem oznaczałoby powtórzenie tych awarii naraz.
"""
import asyncio
import json
import openai
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator, Union
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import tools as agent_tools
from src.ai.embeddings import embedding_service
from src.ai.tools import ToolContext, ToolResult
from src.config import settings
from src.services.gmina_facts import gmina_facts
from src.services.search_synonyms import expand_query
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
    source_types: list[str] = []  # RAG filter
    example_questions: list[str] = []

    # Nazwy narzędzi z `ai.tools.TOOL_REGISTRY`. Puste = dotychczasowa ścieżka RAG.
    # Lista jest per agent, nie globalna: definicje narzędzi wchodzą do KAŻDEGO
    # wywołania (~80 tokenów sztuka), a Urzędnik i GUS chodzą na gpt-4o.
    tools: list[str] = []

    # Ile razy model może sięgnąć po narzędzia, zanim musi odpowiedzieć.
    # Trzy, bo tyle wymaga realne złożenie odpowiedzi z dwóch źródeł: pobrać
    # dokument, zobaczyć czego w nim brakuje, dobrać dane liczbowe. Ostatnia
    # runda leci BEZ narzędzi, więc pętla nie ma jak się zapętlić.
    max_tool_rounds: int = 3

    # RAG parameters (per-agent overrides)
    # Progi skalibrowane na realnym korpusie (07.2026): trafne wyniki mają
    # kosinus 0.43-0.63, więc 0.50 odcinało połowę trafień.
    rag_top_k: int = 5
    rag_threshold: float = 0.35
    rag_semantic_weight: float = 0.70
    rag_recency_boost: float = 0.0
    # Minimum similarity to show source chip in UI (higher than rag_threshold)
    source_display_threshold: float = 0.50

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def respond(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: list[dict] = None,
        stream: bool = False,
        user=None
    ) -> Union[dict, AsyncGenerator]:
        """Generate a response using RAG context (albo pętlę narzędziową)"""
        # Agent z narzędziami nie robi retrievalu na zapas — o materiał prosi
        # model, wtedy gdy go potrzebuje. Wyszukiwarka jest wówczas jednym
        # z narzędzi, a nie podatkiem doliczanym do każdego pytania.
        if self.tools:
            return await self._respond_with_tools(
                session, user_message, conversation_history, stream, user
            )

        # 0. Pytania kontynuacyjne ("a w zeszłym roku?") są bezużyteczne jako
        # zapytanie do wyszukiwarki — przepisz na samodzielne z kontekstem rozmowy
        search_query = user_message
        if conversation_history:
            search_query = await self._rewrite_query(user_message, conversation_history)

        # 0b. Mieszkaniec mówi „eternit", BIP pisze „azbest" — embedding tych
        # dwóch nie łączy (0,674 dla „azbest", zero trafień dla „eternit").
        # Zapytanie musi zostać poprawione TU, przed retrievalem: model dostaje
        # już tylko to, co wyszukiwarka znalazła.
        search_query = expand_query(search_query)

        # 1. Retrieve candidates (szerzej niż top_k — reranker zawęzi)
        candidates = await embedding_service.hybrid_search(
            session=session,
            query=search_query,
            top_k=max(self.rag_top_k * 2, 12),
            source_types=self.source_types or None,
            similarity_threshold=self.rag_threshold,
            semantic_weight=self.rag_semantic_weight,
            recency_boost=self.rag_recency_boost
        )

        # 1b. Rerank: GPT-4o-mini odrzuca kandydatów niezwiązanych z pytaniem.
        # To on decyduje, czy odpowiadamy "z bazy" czy z wiedzy ogólnej —
        # kosinus ~0.5 przepuszczał szum (np. ogłoszenia sesji rady przy
        # pytaniu o dowód osobisty).
        context_docs = await self._rerank(search_query, candidates, keep=self.rag_top_k)

        # Log RAG metrics
        if context_docs:
            scores = [d['similarity'] for d in context_docs]
            logger.info(
                f"RAG[{self.name}] docs={len(context_docs)} "
                f"sim: min={min(scores):.3f} max={max(scores):.3f} avg={sum(scores)/len(scores):.3f}"
            )
        else:
            logger.warning(f"RAG[{self.name}] NO RESULTS for query='{user_message[:60]}'")

        # 2. Build context
        context_parts = []
        sources = []
        seen = set()

        for doc in context_docs:
            meta = doc['metadata']
            published_raw = meta.get('published_at', '') or meta.get('event_date', '')
            date_str = ""
            if published_raw:
                try:
                    dt = datetime.fromisoformat(published_raw.replace('Z', '+00:00'))
                    date_str = f" | Data: {dt.strftime('%d.%m.%Y')}"
                except Exception:
                    date_str = f" | Data: {published_raw[:10]}"

            context_parts.append(
                f"---\n{doc['chunk_text']}\n"
                f"[Zrodlo: {meta.get('source_name', doc['source_type'])}"
                f"{date_str} | Trafnosc: {doc['similarity']:.2f}]"
            )
            key = f"{doc['source_type']}:{doc['source_id']}"
            if key not in seen and doc["similarity"] >= self.source_display_threshold:
                seen.add(key)
                sources.append({
                    "type": doc["source_type"],
                    "id": doc["source_id"],
                    "title": meta.get("title", ""),
                    "url": meta.get("url", ""),
                    "similarity": doc["similarity"]
                })

        context = "\n\n".join(context_parts) if context_parts else "Brak kontekstu."

        # 2b. Materiał, którego wyszukiwarka z definicji nie znajdzie. Pytanie
        # „co nowego" nie ma słów, które cokolwiek wyróżniają — najbliższymi
        # sąsiadami wektora są wpisy zawierające „nowe" i „gmina", więc Redaktor
        # dostawał inwestycje w Stawigudzie sprzed pół roku i odpowiadał
        # „nie mam aktualnych artykułów" przy pełnej bazie. Agent, który tego
        # potrzebuje, dopisuje własny blok; reszta nie płaci nic.
        extra = await self.extra_context(
            session, user_message, {d["source_id"] for d in context_docs}
        )

        # 3. Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            *base_context_messages(),
            {"role": "system", "content": f"KONTEKST:\n{context}\n\nNIE pisz [Zrodlo: ...] ani [Źródło: ...] w treści odpowiedzi — źródła są podawane automatycznie przez system."}
        ]
        if extra:
            messages.append({"role": "system", "content": extra})

        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        # 4. Generate
        if stream:
            return await self._stream(messages, sources, context_count=len(context_docs))

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        return {
            "answer": response.choices[0].message.content,
            "sources": sources,
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "model": self.model,
            "agent_name": self.name
        }

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
    ) -> Union[dict, AsyncGenerator]:
        """Rozmowa, w której o dane prosi model, a nie wzorzec słów kluczowych."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            *base_context_messages(),
        ]
        tools_block = agent_tools.describe_for(self.tools)
        if tools_block:
            messages.append({"role": "system", "content": tools_block})

        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        ctx = ToolContext(session=session, user=user)

        if stream:
            return await self._agentic_stream(messages, ctx)
        return await self._agentic_complete(messages, ctx)

    async def _call_tool(self, ctx: ToolContext, name: str, raw_args: str) -> ToolResult:
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

        try:
            result = await asyncio.wait_for(tool.fn(ctx, **args), timeout=TOOL_TIMEOUT_S)
            logger.info(
                f"Tool[{self.name}:{name}] args={args} "
                f"{'PUSTO' if result.empty else 'ok'}"
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Tool[{name}] przekroczyło {TOOL_TIMEOUT_S}s")
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
        """Wynik narzędzia w postaci wiadomości `tool` dla modelu."""
        payload = result.content
        if result.empty and isinstance(payload, dict):
            # Rozróżnienie, na którym stoi cała wiarygodność odpowiedzi:
            # „szukałem i nie ma" to fakt do zakomunikowania, a nie powód,
            # żeby model sięgnął po wiedzę ogólną i zgadywał.
            payload = {**payload, "pusty_wynik": True}
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
        for call in calls:
            result = await self._call_tool(ctx, call["name"], call["arguments"])
            tool_messages.append(self._tool_message(call, result))
            sources.extend(result.sources)
            charts.extend(result.charts)

        return {"messages": tool_messages, "sources": sources, "charts": charts}

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

    def _round_kwargs(self, messages: list[dict], allow_tools: bool) -> dict:
        """Argumenty jednej rundy. Ostatnia leci bez `tools` — model nie ma
        wtedy wyjścia poza napisaniem odpowiedzi, więc pętla zawsze się kończy."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if allow_tools:
            schemas = agent_tools.schemas_for(self.tools)
            if schemas:
                kwargs["tools"] = schemas
                kwargs["tool_choice"] = "auto"
        return kwargs

    async def _agentic_complete(self, messages: list[dict], ctx: ToolContext) -> dict:
        """Wariant bez streamu — używany przez testy i wywołania non-stream."""
        messages = list(messages)
        sources, charts, tokens = [], [], 0

        for round_idx in range(self.max_tool_rounds):
            allow_tools = round_idx < self.max_tool_rounds - 1
            response = await self.client.chat.completions.create(
                **self._round_kwargs(messages, allow_tools)
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

        return {
            "answer": "", "sources": sources, "chart_data": charts,
            "tokens_used": tokens, "model": self.model, "agent_name": self.name,
        }

    async def _agentic_stream(self, messages: list[dict], ctx: ToolContext) -> AsyncGenerator:
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
                    **agent_self._round_kwargs(messages, allow_tools),
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
                    messages.append(agent_self._tool_message(call, result))
                    sources.extend(result.sources)
                    charts.extend(result.charts)

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

    async def extra_context(
        self,
        session: AsyncSession,
        user_message: str,
        retrieved_ids: set,
    ) -> Optional[str]:
        """
        Dodatkowy blok `system` poza RAG-iem — pusty, dopóki agent go nie nadpisze.

        `retrieved_ids` to ID wpisów, które już weszły przez retrieval; agent ma
        ich NIE powtarzać, żeby ten sam artykuł nie zajmował miejsca dwa razy.
        """
        return None

    async def _rewrite_query(self, user_message: str, conversation_history: list[dict]) -> str:
        """Przepisuje pytanie kontynuacyjne na samodzielne zapytanie do wyszukiwarki."""
        recent = conversation_history[-4:]
        convo = "\n".join(
            f"{'Użytkownik' if m['role'] == 'user' else 'Asystent'}: {m['content'][:300]}"
            for m in recent
        )
        try:
            resp = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Przekształć ostatnie pytanie użytkownika w samodzielne zapytanie "
                        "do wyszukiwarki (po polsku), uzupełniając brakujący kontekst z rozmowy. "
                        "Jeśli pytanie jest już samodzielne — zwróć je bez zmian. "
                        "Zwróć TYLKO treść zapytania, nic więcej."
                    )},
                    {"role": "user", "content": f"ROZMOWA:\n{convo}\n\nOSTATNIE PYTANIE: {user_message}"},
                ],
                temperature=0,
                max_tokens=80,
            )
            rewritten = (resp.choices[0].message.content or "").strip().strip('"')
            if rewritten:
                if rewritten != user_message:
                    logger.info(f"Query rewrite: '{user_message[:40]}' -> '{rewritten[:60]}'")
                return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")
        return user_message

    async def _rerank(self, query: str, docs: list[dict], keep: int) -> list[dict]:
        """Listwise rerank przez GPT-4o-mini: zostawia tylko fragmenty, które
        faktycznie pomagają odpowiedzieć. Pusta lista = odpowiedź z wiedzy ogólnej.
        Przy błędzie API zachowuje oryginalną kolejność (graceful fallback)."""
        if len(docs) <= 1:
            return docs
        items = "\n".join(
            f"[{i}] {d['metadata'].get('title', '')} — {d['chunk_text'][:200]}"
            for i, d in enumerate(docs)
        )
        try:
            resp = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Oceń, które fragmenty FAKTYCZNIE pomagają odpowiedzieć na pytanie. "
                        "Zwróć TYLKO JSON: listę indeksów trafnych fragmentów od najtrafniejszego, "
                        "np. [3,0,5]. Pomiń fragmenty niezwiązane z pytaniem (podobny temat to za mało "
                        "— fragment musi zawierać informację przydatną do odpowiedzi). "
                        "Jeśli żaden nie pasuje, zwróć []."
                    )},
                    {"role": "user", "content": f"PYTANIE: {query}\n\nFRAGMENTY:\n{items}"},
                ],
                temperature=0,
                max_tokens=60,
            )
            raw = (resp.choices[0].message.content or "").strip()
            start, end = raw.find("["), raw.rfind("]")
            indices = json.loads(raw[start:end + 1]) if start != -1 and end > start else []
            picked = [docs[i] for i in indices if isinstance(i, int) and 0 <= i < len(docs)]
            logger.info(f"Rerank[{self.name}]: {len(docs)} kandydatów -> {len(picked)} trafnych")
            return picked[:keep]
        except Exception as e:
            logger.warning(f"Rerank failed, keeping original order: {e}")
            return docs[:keep]

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
