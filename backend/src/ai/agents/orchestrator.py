"""
Orchestrator - routes user queries to the appropriate specialized agent
Uses GPT-4o-mini for fast, cheap classification
"""
import openai
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent
from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("Orchestrator")

ROUTING_PROMPT = """Jestes routerem zapytan. Przeanalizuj INTENCJE pytania i zwroc TYLKO nazwe agenta.

ZASADA KLUCZOWA: kieruj sie tym CO UZYTKOWNIK CHCE ZROBIC, nie slowami kluczowymi.

Dostepni agenci i ich INTENCJE:

- redaktor: szuka AKTUALNYCH INFORMACJI z lokalnych mediow
  Przykladowe pytania: "co nowego?", "jakie sa oferty pracy w firmach?", "czy jest przetarg na droge?",
  "co sie wydarzylo?", "jakie firmy szukaja pracownikow?", "aktualnosci z gminy"
  UWAGA: oferty pracy, ogloszenia o zatrudnienie, rekrutacja w firmach -> redaktor (nie gus_analityk!)

- urzednik: szuka DOKUMENTOW URZEDOWYCH lub FORMALNYCH PROCEDUR
  Przykladowe pytania: "jaka jest uchwala w sprawie...", "gdzie zlozym wniosek o...", "przetarg nr...",
  "kiedy wchodzi w zycie regulamin...", "co mowi BIP o..."

- gus_analityk: chce STATYSTYK HISTORYCZNYCH I DANYCH LICZBOWYCH z GUS
  Przykladowe pytania: "ile wynosi bezrobocie w powiecie?", "jaki jest PKB gminy?",
  "ile ludzi pracuje na 1000 mieszkancow?", "jak zmienila sie demografia?", "dane o finansach gminy"
  UWAGA: pytania o konkretne oferty pracy lub firmy szukajace pracownikow -> redaktor, NIE tutaj!

- przewodnik: pyta o MIEJSCA, WYDARZENIA lub POGODE
  Przykladowe pytania: "co robic w weekend?", "gdzie zjesc?", "jaka bedzie pogoda?",
  "jakie imprezy sa w gminie?", "gdzie mozna poplywac?"

- straznik: ZGLASZA PROBLEM lub pyta o BEZPIECZENSTWO I AWARIE
  Przykladowe pytania: "jest awaria wody na ulicy...", "gdzie zglasza sie usterke?",
  "czy sa jakies ostrzezenia?", "wypadek na drodze..."

- organizator: pyta o HARMONOGRAMY ODBIORU SMIECI lub REPERTUAR KINA
  Przykladowe pytania: "kiedy wywoz smieci?", "co gra w kinie?", "harmonogram odpadow dla..."

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

    async def route(self, user_message: str) -> str:
        """Determine which agent should handle the query"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ROUTING_PROMPT},
                    {"role": "user", "content": user_message}
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
        user=None
    ) -> dict:
        """Route and handle a user query"""
        # Auto-route if no agent specified
        if not agent_name:
            agent_name = await self.route(user_message)

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

    def get_agents(self) -> list[dict]:
        """Get all registered agents info"""
        return [agent.to_dict() for agent in self.agents.values()]


# Singleton - agents registered at startup
orchestrator = Orchestrator()
