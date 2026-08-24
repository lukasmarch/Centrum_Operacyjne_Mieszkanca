"""
Orchestrator — wybiera agenta i, gdy trzeba, zmienia zdanie (etap 7)

Do 24.08.2026 była tu wyłącznie klasyfikacja: `route()` wskazywał jednego
agenta, `handle()` go wołał i oddawał wynik. Decyzja zapadała RAZ, na podstawie
samego brzmienia pytania, zanim ktokolwiek zajrzał do danych — i nie było jej
jak cofnąć. Pytanie „sprawdź kondycję Rybna, mocne i słabe strony, bieżące
i historyczne" trafiło do Redaktora (bo „bieżące" brzmi najgłośniej) i dostało
„nie mam możliwości" przy bazie pełnej szeregów GUS i 430 uchwał.

`run()` dokłada nad agentem to, co `BaseAgent` ma pod nim od 22.08: pętlę.
Agent, któremu brakuje zasięgu, woła `przekaz_dalej` (`tools/handoff.py`),
a orkiestrator oddaje pytanie następnemu. Najwyżej `MAX_HANDOFFS` razy.

**Czego to NIE robi.** Nie ocenia gotowej odpowiedzi ani nie „poprawia" jej
drugim modelem. Sygnał przychodzi od agenta, który właśnie czytał pytanie
i zna swoje narzędzia — jest tańszy i uczciwszy niż klasyfikator zgadujący
z prozy, czy „nie mam danych o wywozie w Płośnicy, ale mam w Rybnie" to odmowa.

**Koszt.** Pytanie bez handoffu kosztuje dokładnie tyle co wcześniej — pętla
nie ma się od czego uruchomić. Płacimy tylko tam, gdzie dziś i tak
przegrywaliśmy: przy odmowie.
"""
import json
import openai
from typing import AsyncGenerator, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent
from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("Orchestrator")

# Ile razy pytanie może zmienić agenta. Dwa, bo tyle wystarcza na realny błąd
# routingu (specjalista → właściwy specjalista) i na eskalację do koordynatora
# (specjalista → koordynator → jego delegacje). Trzeci przeskok nie zdarza się
# w scenariuszu, który potrafimy opisać — a zdarza się w pętli, która się
# zapętliła. Do tego `_next_agent` nie wraca do agenta, który już odpowiadał.
MAX_HANDOFFS = 2

ROUTING_PROMPT = """Jestes routerem zapytan. Przeanalizuj INTENCJE pytania i zwroc TYLKO nazwe agenta.

ZASADA KLUCZOWA: kieruj sie tym CO UZYTKOWNIK CHCE ZROBIC, nie slowami kluczowymi.

Dostepni agenci i ich INTENCJE:

- redaktor: szuka AKTUALNYCH INFORMACJI z lokalnych mediow
  Przykladowe pytania: "co nowego?", "jakie sa oferty pracy w firmach?", "czy jest przetarg na droge?",
  "co sie wydarzylo?", "jakie firmy szukaja pracownikow?", "aktualnosci z gminy"
  UWAGA: oferty pracy, ogloszenia o zatrudnienie, rekrutacja w firmach -> redaktor (nie gus_analityk!)

- urzednik: szuka DOKUMENTOW URZEDOWYCH, FORMALNYCH PROCEDUR lub USTROJU GMINY
  Przykladowe pytania: "jaka jest uchwala w sprawie...", "gdzie zlozym wniosek o...", "przetarg nr...",
  "kiedy wchodzi w zycie regulamin...", "co mowi BIP o...", "program Czyste Powietrze",
  "dofinansowanie na usuniecie eternitu", "jak zlozyc deklaracje smieciowa"
  TU TEZ trafiaja pytania o to, JAK GMINA JEST ZBUDOWANA I KTO NIA KIERUJE:
  "ile gmina ma solectw", "jakie sa solectwa", "kto jest wojtem", "ilu jest radnych",
  "gdzie jest urzad gminy", "jakie sa jednostki organizacyjne", "jaki jest statut gminy"

- gus_analityk: chce STATYSTYK HISTORYCZNYCH I DANYCH LICZBOWYCH z GUS
  Przykladowe pytania: "ile wynosi bezrobocie w powiecie?", "jaki jest PKB gminy?",
  "ile ludzi pracuje na 1000 mieszkancow?", "jak zmienila sie demografia?", "dane o finansach gminy"
  UWAGA: pytania o konkretne oferty pracy lub firmy szukajace pracownikow -> redaktor, NIE tutaj!
  UWAGA: samo slowo "ile" NIE oznacza statystyki. GUS opisuje zjawiska MIERZONE W CZASIE
  (ludnosc, bezrobocie, budzet, liczba firm). Pytania o ustroj i organizacje gminy
  ("ile solectw", "ilu radnych", "ile szkol prowadzi gmina") -> urzednik, NIE tutaj!

- przewodnik: pyta o MIEJSCA, WYDARZENIA lub POGODE
  Przykladowe pytania: "co robic w weekend?", "gdzie zjesc?", "jaka bedzie pogoda?",
  "jakie imprezy sa w gminie?", "gdzie mozna poplywac?"

- straznik: ZGLASZA PROBLEM lub pyta o BEZPIECZENSTWO I AWARIE
  Przykladowe pytania: "jest awaria wody na ulicy...", "gdzie zglasza sie usterke?",
  "czy sa jakies ostrzezenia?", "wypadek na drodze..."

- organizator: pyta o HARMONOGRAMY ODBIORU SMIECI, REPERTUAR KINA, ZDROWIE/LEKARZY
  lub GODZINY PRACY URZEDU I GOPS
  Przykladowe pytania: "kiedy wywoz smieci?", "co gra w kinie?", "harmonogram odpadow dla...",
  "kiedy przyjmuje lekarz?", "godziny poradni stomatologicznej", "ktora apteka dzis dyzuruje?",
  "dyzur apteki w weekend", "godziny POZ", "harmonogram poradni ginekologicznej",
  "do ktorej pracuje GOPS", "kiedy czynny urzad gminy", "telefon do urzedu"

- koordynator: pytanie wymaga KILKU DZIEDZIN NARAZ albo prosi o OCENE/ANALIZE/POROWNANIE
  Przykladowe pytania: "jaka jest kondycja gminy?", "mocne i slabe strony Rybna",
  "czy gmina sie wyludnia i co z tym robi?", "podsumuj sytuacje w gminie",
  "czy warto tu otworzyc firme?", "jak wypadamy na tle innych gmin?"
  ROZPOZNASZ GO PO TYM, ze zadna pojedyncza dziedzina nie wystarczy: odpowiedz
  potrzebuje i danych liczbowych, i dokumentow, i biezacych wiadomosci.
  UWAGA: to NIE jest agent od pytan trudnych ani dlugich. "Jakie sa najnowsze
  uchwaly" jest jednodziedzinowe (urzednik), choc brzmi powaznie. Pytanie
  z JEDNEJ dziedziny kieruj do specjalisty - koordynator kosztuje wielokrotnie
  wiecej i odpowiada wolniej.

KONTYNUACJA ROZMOWY: jesli pytanie jest doprecyzowaniem lub kontynuacja
poprzedniego watku (np. "a w zeszlym roku?", "a ile dokladnie?", "powiedz wiecej",
"a w Hartowcu?"), zwroc agenta ktory obslugiwal poprzednia wiadomosc
(podany jako OSTATNI AGENT) — chyba ze intencja WYRAZNIE sie zmienila.

Odpowiedz TYLKO jedna nazwa agenta (np. "redaktor"). Nic wiecej."""


class Orchestrator:
    """Routes queries to specialized agents"""

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent):
        """Register a specialized agent"""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} ({agent.display_name})")

    async def route(
        self,
        user_message: str,
        conversation_history: list[dict] = None,
        last_agent: Optional[str] = None,
    ) -> str:
        """Determine which agent should handle the query.

        Router widzi krótki kontekst rozmowy — bez niego pytania
        kontynuacyjne ("a w zeszłym roku?") trafiały do złego agenta.
        """
        try:
            routing_input = ""
            if conversation_history:
                prev_user = [m["content"] for m in conversation_history if m["role"] == "user"][-2:]
                if prev_user:
                    prev = "\n".join(f"- {q[:150]}" for q in prev_user)
                    routing_input += f"POPRZEDNIE PYTANIA W ROZMOWIE:\n{prev}\n"
            if last_agent:
                routing_input += f"OSTATNI AGENT: {last_agent}\n"
            routing_input += f"AKTUALNE PYTANIE: {user_message}"

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ROUTING_PROMPT},
                    {"role": "user", "content": routing_input}
                ],
                temperature=0,
                max_tokens=20
            )

            agent_name = response.choices[0].message.content.strip().lower()

            # Validate agent name
            if agent_name in self.agents:
                logger.info(f"Routed '{user_message[:50]}...' -> {agent_name}")
                return agent_name

            # Fallback to redaktor for general queries
            logger.warning(f"Unknown agent '{agent_name}', falling back to redaktor")
            return "redaktor"

        except Exception as e:
            logger.error(f"Routing error: {e}")
            return "redaktor"

    async def handle(
        self,
        session: AsyncSession,
        user_message: str,
        agent_name: Optional[str] = None,
        conversation_history: list[dict] = None,
        stream: bool = False,
        user=None,
        last_agent: Optional[str] = None,
    ) -> dict:
        """Route and handle a user query"""
        # Auto-route if no agent specified
        if not agent_name:
            agent_name = await self.route(user_message, conversation_history, last_agent)

        agent = self.agents.get(agent_name)
        if not agent:
            agent = self.agents.get("redaktor")  # Fallback

        return await agent.respond(
            session=session,
            user_message=user_message,
            conversation_history=conversation_history,
            stream=stream,
            user=user
        )

    # ------------------------------------------------------------------
    # Pętla orkiestracji
    # ------------------------------------------------------------------

    async def run(
        self,
        session: AsyncSession,
        user_message: str,
        agent_name: Optional[str] = None,
        conversation_history: list[dict] = None,
        stream: bool = False,
        user=None,
        last_agent: Optional[str] = None,
    ) -> Union[dict, AsyncGenerator]:
        """Jak `handle()`, ale z prawem do zmiany agenta w trakcie.

        Wejście i wyjście są takie same jak w `handle()` — endpoint czatu nie
        odróżnia jednej ścieżki od drugiej poza dodatkowym zdarzeniem `handoff`
        w strumieniu.
        """
        if not agent_name:
            agent_name = await self.route(user_message, conversation_history, last_agent)

        if stream:
            return self._run_stream(
                session, user_message, agent_name, conversation_history, user
            )
        return await self._run_complete(
            session, user_message, agent_name, conversation_history, user
        )

    def _agent_or_fallback(self, name: Optional[str]):
        """Agent o tej nazwie albo Redaktor. `None`, gdy rejestr jest PUSTY.

        `self.agents.get(x) or self.agents.get("redaktor")` wyglądało na
        bezpieczne i takie nie było: przy pustym rejestrze oddaje `None`,
        a linijkę niżej `agent.name` wywracało rozmowę na `AttributeError`
        zamiast powiedzieć, co się stało. Rejestr bywa pusty poza serwerem —
        wypełnia go start FastAPI, więc każdy skrypt, który zapomni
        o `register_agent`, dostawał komunikat nie mówiący nic o przyczynie.
        """
        agent = self.agents.get(name) if name else None
        if agent is not None:
            return agent
        fallback = self.agents.get("redaktor")
        if fallback is None:
            logger.error(
                f"Rejestr agentów PUSTY — nie ma kogo zapytać o '{name}'. "
                "Poza API trzeba wywołać orchestrator.register_agent() ręcznie."
            )
            return None
        logger.warning(f"Agent '{name}' nieznany — odpowiada redaktor")
        return fallback

    def _next_agent(self, handoff: dict, visited: list[str]) -> Optional[str]:
        """Kto przejmuje pytanie. `None` = nie ma dokąd, kończymy.

        Agent raz odwiedzony nie wraca do gry: to jedyne miejsce, w którym
        odbijanie pytania w kółko („to nie ja" ↔ „ja też nie") kończy się samo,
        niezależnie od tego, co wymyśli model.
        """
        target = (handoff or {}).get("to")
        if target and target in self.agents and target not in visited:
            return target

        if target and target in visited:
            logger.warning(f"Handoff do '{target}', który już odpowiadał — pomijam")
        elif target:
            logger.warning(f"Handoff do nieznanego agenta '{target}'")
        return None

    async def _run_complete(
        self,
        session: AsyncSession,
        user_message: str,
        agent_name: str,
        conversation_history: Optional[list[dict]],
        user,
    ) -> dict:
        """Wariant bez streamu — używany przez testy i wywołania non-stream."""
        visited: list[str] = []
        sources, charts, tokens = [], [], 0
        last_reason: Optional[str] = None

        for _ in range(MAX_HANDOFFS + 1):
            agent = self._agent_or_fallback(agent_name)
            if agent is None:
                return {
                    "answer": self._dead_end_message(None), "sources": sources,
                    "chart_data": charts, "tokens_used": tokens, "model": "n/a",
                    "agent_name": agent_name, "handoff_path": visited,
                }
            visited.append(agent.name)

            result = await agent.respond(
                session=session,
                user_message=user_message,
                conversation_history=conversation_history,
                stream=False,
                user=user,
            )
            # Materiał zebrany po drodze zostaje, nawet jeśli agent oddał
            # pytanie: Strażnik potrafi znaleźć awarię i dopiero potem uznać,
            # że reszta pytania go przerasta.
            sources.extend(result.get("sources") or [])
            charts.extend(result.get("chart_data") or [])
            tokens += result.get("tokens_used") or 0

            handoff = result.get("handoff")
            if not handoff:
                result["sources"] = sources
                result["chart_data"] = charts
                result["tokens_used"] = tokens
                result["handoff_path"] = visited
                return result

            last_reason = handoff.get("reason")
            nxt = self._next_agent(handoff, visited)
            if nxt is None:
                break
            logger.info(f"Handoff {agent.name} → {nxt}: {last_reason}")
            agent_name = nxt

        # Wyczerpane przeskoki albo brak celu. Mieszkaniec ma usłyszeć, czego
        # zabrakło — cisza po dwóch przekazaniach jest gorsza od odmowy.
        return {
            "answer": self._dead_end_message(last_reason),
            "sources": sources,
            "chart_data": charts,
            "tokens_used": tokens,
            "model": "n/a",
            "agent_name": visited[-1] if visited else "redaktor",
            "handoff_path": visited,
        }

    async def _run_stream(
        self,
        session: AsyncSession,
        user_message: str,
        agent_name: str,
        conversation_history: Optional[list[dict]],
        user,
    ) -> AsyncGenerator:
        """Strumień, który potrafi przełączyć agenta w połowie.

        Zdarzenia agenta lecą do przeglądarki bez zmian — poza `done`, które
        przy przekazaniu pytania NIE MOŻE polecieć, bo zamknęłoby odpowiedź
        w interfejsie. Zamiast niego idzie `handoff` z `discard_text`
        (`base_agent`), na które front kasuje to, co zdążył pokazać.
        """
        visited: list[str] = []
        tokens = 0
        last_reason: Optional[str] = None
        current = agent_name

        for _ in range(MAX_HANDOFFS + 1):
            agent = self._agent_or_fallback(current)
            if agent is None:
                break
            visited.append(agent.name)

            generator = await agent.respond(
                session=session,
                user_message=user_message,
                conversation_history=conversation_history,
                stream=True,
                user=user,
            )

            handoff = None
            async for line in generator:
                data = json.loads(line)
                if data.get("type") == "handoff":
                    handoff = data
                    tokens += data.get("tokens_used") or 0
                    continue
                if data.get("type") == "done":
                    data["tokens_used"] = (data.get("tokens_used") or 0) + tokens
                    data["handoff_path"] = visited
                    yield json.dumps(data) + "\n"
                    return
                yield line

            if handoff is None:
                # Generator skończył się bez `done` — awaryjnie, ale strumień
                # musi zostać domknięty, inaczej przeglądarka wisi na SSE.
                logger.error(f"Agent[{agent.name}] zamknął strumień bez 'done'")
                break

            nxt = self._next_agent(handoff, visited)
            last_reason = handoff.get("reason")
            yield json.dumps({
                "type": "status",
                "state": "running" if nxt else "warning",
                "message": (
                    f"Pytanie przejmuje {self.agents[nxt].display_name}"
                    if nxt else "Nie znalazłem agenta, który to obsłuży"
                ),
                "detail": last_reason or "",
                # Front kasuje na to bufor tekstu — patrz `discard_text`.
                "handoff": True,
                "discard_text": bool(handoff.get("discard_text")),
            }) + "\n"

            if nxt is None:
                break
            logger.info(f"Handoff {agent.name} → {nxt}: {last_reason}")
            current = nxt

        message = self._dead_end_message(last_reason)
        yield json.dumps({"type": "chunk", "content": message}) + "\n"
        yield json.dumps({"type": "sources", "sources": []}) + "\n"
        yield json.dumps({
            "type": "done",
            "full_content": message,
            "model": "n/a",
            "agent_name": visited[-1] if visited else "redaktor",
            "tokens_used": tokens,
            "handoff_path": visited,
        }) + "\n"

    @staticmethod
    def _dead_end_message(reason: Optional[str]) -> str:
        """Odpowiedź, gdy nikt nie przejął pytania.

        Pisze ją KOD, nie model: w tym miejscu nie ma już materiału, a model
        bez materiału produkuje dokładnie tę odmowę, od której zaczęliśmy.
        Zdanie ma powiedzieć, czego zabrakło, i wskazać człowieka.
        """
        brak = f" Zabrakło: {reason}." if reason else ""
        return (
            "Nie mam danych, żeby odpowiedzieć na to pytanie w całości."
            f"{brak} Spróbuj zapytać o mniejszy fragment — albo skontaktuj się "
            "z Urzędem Gminy Rybno (tel. 23 696 60 55, ul. Lubawska 15)."
        )

    def get_agents(self) -> list[dict]:
        """Get all registered agents info"""
        return [agent.to_dict() for agent in self.agents.values()]


# Singleton - agents registered at startup
orchestrator = Orchestrator()
