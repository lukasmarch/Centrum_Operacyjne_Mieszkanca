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
    rag_top_k: int = 5
    rag_threshold: float = 0.50
    rag_semantic_weight: float = 0.70
    rag_recency_boost: float = 0.0
    # Minimum similarity to show source chip in UI (higher than rag_threshold)
    source_display_threshold: float = 0.60

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
        # 1. Retrieve context
        context_docs = await embedding_service.hybrid_search(
            session=session,
            query=user_message,
            top_k=self.rag_top_k,
            source_types=self.source_types or None,
            similarity_threshold=self.rag_threshold,
            semantic_weight=self.rag_semantic_weight,
            recency_boost=self.rag_recency_boost
        )

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

        # 3. Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": get_datetime_context()},
            {"role": "system", "content": f"KONTEKST:\n{context}\n\nNIE pisz [Zrodlo: ...] ani [Źródło: ...] w treści odpowiedzi — źródła są podawane automatycznie przez system."}
        ]

        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        # 4. Generate
        if stream:
            return await self._stream(messages, sources)

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

    async def _stream(self, messages: list[dict], sources: list[dict]) -> AsyncGenerator:
        """Stream response via SSE"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True
        )

        async def generate():
            full_content = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield json.dumps({"type": "chunk", "content": content}) + "\n"

            yield json.dumps({"type": "sources", "sources": sources}) + "\n"
            yield json.dumps({
                "type": "done",
                "full_content": full_content,
                "model": self.model,
                "agent_name": self.name
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
