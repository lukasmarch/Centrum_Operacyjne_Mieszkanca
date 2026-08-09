"""
BaseAgent - abstract base for all specialized AI agents
"""
import json
import openai
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator, Union
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.embeddings import embedding_service
from src.config import settings
from src.services.gmina_facts import gmina_facts
from src.services.search_synonyms import expand_query
from src.utils.logger import setup_logger

logger = setup_logger("BaseAgent")

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
        """Generate a response using RAG context"""
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
                if context_count > 0:
                    step = f"Przeszukałem bazę wiedzy — {context_count} trafnych materiałów źródłowych"
                else:
                    step = "Brak trafnych materiałów w bazie — odpowiadam na podstawie wiedzy ogólnej"
                yield json.dumps({"type": "status", "message": step}) + "\n"

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
