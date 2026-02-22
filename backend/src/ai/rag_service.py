"""
RAGService - Retrieval Augmented Generation for the chat system
Embeds query -> vector search -> builds context -> GPT-4o response with source attribution
"""
import json
import openai
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.embeddings import embedding_service
from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("RAGService")

SYSTEM_PROMPT = """Jestes asystentem Centrum Operacyjnego Mieszkanca - RybnoLive.
Odpowiadasz WYLACZNIE na podstawie dostarczonego kontekstu.
Jesli nie masz odpowiedzi w kontekscie - poinformuj ze nie dysponujesz takimi danymi.
ZAWSZE cytuj zrodla w formacie [Zrodlo: nazwa]. Odpowiadaj po polsku, zwiezle i praktycznie.
Jesli pytanie dotyczy pogody, wydarzen lub statystyk - podaj konkretne dane liczbowe.
Nie wymyslaj informacji. Bazuj tylko na faktach z kontekstu."""

CHAT_MODEL = "gpt-4o"
CHAT_MODEL_MINI = "gpt-4o-mini"
MAX_CONTEXT_TOKENS = 4000


class RAGService:
    """RAG pipeline: query -> retrieve -> generate with source attribution"""

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def query(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: list[dict] = None,
        source_types: Optional[list[str]] = None,
        model: str = CHAT_MODEL,
        stream: bool = False
    ) -> dict | AsyncGenerator:
        """
        Full RAG pipeline.
        Returns: {answer, sources, tokens_used, model}
        """
        # 1. Retrieve relevant context
        context_docs = await embedding_service.semantic_search(
            session=session,
            query=user_message,
            top_k=6,
            source_types=source_types,
            similarity_threshold=0.25
        )

        # 2. Build context string
        context_parts = []
        sources = []
        seen_sources = set()

        for doc in context_docs:
            context_parts.append(f"---\n{doc['chunk_text']}\n[Zrodlo: {doc['metadata'].get('source_name', doc['source_type'])}]")

            source_key = f"{doc['source_type']}:{doc['source_id']}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                sources.append({
                    "type": doc["source_type"],
                    "id": doc["source_id"],
                    "title": doc["metadata"].get("title", ""),
                    "url": doc["metadata"].get("url", ""),
                    "similarity": doc["similarity"]
                })

        context_text = "\n\n".join(context_parts) if context_parts else "Brak kontekstu - nie znaleziono powiazanych dokumentow."

        # 3. Build messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"KONTEKST:\n{context_text}"}
        ]

        # Add conversation history (last 6 messages)
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        # 4. Generate response
        if stream:
            return self._stream_response(messages, sources, model)

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )

        answer = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0

        return {
            "answer": answer,
            "sources": sources,
            "tokens_used": tokens_used,
            "model": model
        }

    async def _stream_response(
        self,
        messages: list[dict],
        sources: list[dict],
        model: str
    ) -> AsyncGenerator:
        """Stream response chunks via SSE"""
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
            stream=True
        )

        async def generate():
            full_content = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield json.dumps({
                        "type": "chunk",
                        "content": content
                    }) + "\n"

            # Send sources at the end
            yield json.dumps({
                "type": "sources",
                "sources": sources
            }) + "\n"

            yield json.dumps({
                "type": "done",
                "full_content": full_content,
                "model": model
            }) + "\n"

        return generate()

    async def get_suggestions(self, session: AsyncSession) -> list[str]:
        """Get context-aware chat suggestions"""
        return [
            "Co nowego w Rybnie?",
            "Jaka jest dzisiejsza pogoda?",
            "Jakie wydarzenia odbywaja sie w tym tygodniu?",
            "Jak wyglada demografia gminy?",
            "Co mowi ostatni BIP?",
            "Jakie sa najnowsze inwestycje?"
        ]


# Singleton
rag_service = RAGService()
