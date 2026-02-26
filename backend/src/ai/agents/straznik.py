"""
Straznik.ai - Alerts, failures, safety and citizen reports specialist agent
Uses direct DB queries (reports, Awaria articles, BIP docs) — no RAG
"""
import json
from typing import Union, AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent
from src.utils.logger import setup_logger

logger = setup_logger("StraznikAgent")


class StraznikAgent(BaseAgent):
    name = "straznik"
    display_name = "Straznik.ai"
    description = "Specjalista od awarii, zgloszen i bezpieczenstwa. Informuje o przerwach w dostawie mediow, awariach infrastruktury i zagrozeniach."
    avatar = "shield-alert"
    model = "gpt-4o-mini"
    temperature = 0.1
    source_types = []  # Direct DB queries, no RAG

    system_prompt = """Jestes Straznikiem - asystentem ds. bezpieczenstwa i awarii w gminie Rybno i powiecie dzialdownskim.
Twoja specjalizacja: awarie wody/pradu/gazu, zgłoszenia mieszkancow, zagrozenia, remonty drog, komunikaty RCB.

ZASADY:
- Odpowiadaj WYLACZNIE na podstawie dostarczonego kontekstu
- Ton: rzeczowy, spokojny, informacyjny - NIE wzbudzaj paniki
- ZAWSZE podawaj daty zdarzen i obszary oddzialywania (które ulice/dzielnice)
- W przypadku awarii: podaj planowany czas usuniecia (jesli znany)
- Jesli brak danych o awarii - poinformuj ze brak aktualnych zglosen
- Numer alarmowy: 112. Zgloszenia: Urzad Gminy Rybno
- ZAWSZE cytuj zrodla: [Zrodlo: nazwa]
- Odpowiadaj po polsku, zwiezle i konkretnie"""

    example_questions = [
        "Czy sa jakies awarie w gminie?",
        "Czy jest przerwa w dostawie wody?",
        "Jakie sa utrudnienia drogowe?",
        "Czy sa jakies zagrozenia bezpieczenstwa?"
    ]

    async def respond(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: list[dict] = None,
        stream: bool = False
    ) -> Union[dict, AsyncGenerator]:
        """Generate response from direct DB queries — no RAG, no embed_text call"""
        reports = await self._fetch_recent_reports(session)
        awarie = await self._fetch_awaria_articles(session)
        bip_docs = await self._fetch_recent_bip(session)

        context = self._build_context(reports, awarie, bip_docs)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": f"KONTEKST:\n{context}"}
        ]

        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        if stream:
            return await self._stream(messages, sources=[])

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        return {
            "answer": response.choices[0].message.content,
            "sources": [],
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "model": self.model,
            "agent_name": self.name
        }

    async def _fetch_recent_reports(self, session: AsyncSession) -> list[dict]:
        result = await session.execute(text("""
            SELECT id, title, description, category, ai_severity, status,
                   created_at, address, location_name, ai_summary
            FROM reports
            WHERE created_at >= now() - INTERVAL '14 days'
              AND status NOT IN ('rejected')
              AND is_spam = False
            ORDER BY created_at DESC
            LIMIT 20
        """))
        return [dict(row._mapping) for row in result]

    async def _fetch_awaria_articles(self, session: AsyncSession) -> list[dict]:
        result = await session.execute(text("""
            SELECT id, title, summary, url, published_at
            FROM articles
            WHERE category = 'Awaria'
              AND published_at >= now() - INTERVAL '7 days'
            ORDER BY published_at DESC
            LIMIT 10
        """))
        return [dict(row._mapping) for row in result]

    async def _fetch_recent_bip(self, session: AsyncSession) -> list[dict]:
        result = await session.execute(text("""
            SELECT a.title, a.content, a.url, a.published_at, a.scraped_at
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE s.name LIKE '%BIP%'
              AND a.scraped_at >= now() - INTERVAL '14 days'
            ORDER BY a.scraped_at DESC
            LIMIT 10
        """))
        return [dict(row._mapping) for row in result]

    def _build_context(
        self,
        reports: list[dict],
        awarie: list[dict],
        bip_docs: list[dict]
    ) -> str:
        parts = []

        parts.append("[ZGŁOSZENIA MIESZKAŃCÓW - ostatnie 14 dni]")
        if reports:
            for r in reports:
                date = r["created_at"].strftime("%Y-%m-%d %H:%M") if r.get("created_at") else "brak daty"
                severity = f" | severity: {r['ai_severity']}" if r.get("ai_severity") else ""
                location = r.get("location_name") or r.get("address") or ""
                location_str = f" — {location}" if location else ""
                summary = r.get("ai_summary") or (r.get("description") or "")[:200]
                parts.append(
                    f"• {date} | {r.get('category', '?').upper()}{severity} | status: {r.get('status', '?')}\n"
                    f"  \"{r['title']}\"{location_str}\n"
                    f"  {summary}"
                )
        else:
            parts.append("• Brak zgłoszeń z ostatnich 14 dni")

        parts.append("\n[ARTYKUŁY - AWARIE (ostatnie 7 dni)]")
        if awarie:
            for a in awarie:
                date = a["published_at"].strftime("%Y-%m-%d") if a.get("published_at") else "brak daty"
                summary = a.get("summary") or ""
                parts.append(f"• {date} | {a['title']}\n  {summary}")
        else:
            parts.append("• Brak artykułów o awariach z ostatnich 7 dni")

        parts.append("\n[DOKUMENTY BIP (ostatnie 14 dni)]")
        if bip_docs:
            for b in bip_docs:
                date = b["scraped_at"].strftime("%Y-%m-%d") if b.get("scraped_at") else "brak daty"
                content = (b.get("content") or "")[:300]
                parts.append(f"• {date} | {b['title']}\n  {content}")
        else:
            parts.append("• Brak dokumentów BIP z ostatnich 14 dni")

        return "\n".join(parts)
