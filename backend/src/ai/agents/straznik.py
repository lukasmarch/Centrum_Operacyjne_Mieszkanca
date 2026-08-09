"""
Straznik.ai - Alerts, failures, safety and citizen reports specialist agent
Uses direct DB queries (reports, Awaria articles, BIP docs) — no RAG

7.08.2026, 8:21 — mieszkaniec pyta „czy dziś nie będzie prądu", a Strażnik
odpowiada, że nie ma żadnych zgłoszeń. Wyłączenie zaczynało się o 9:00 i stało
w bazie (art. 5060, `event_at` 7.08 09:00–14:00, kategoria Awaria, osadzone
w RAG). Nie weszło do kontekstu, bo zapytanie agenta filtrowało po DACIE
OGŁOSZENIA (`published_at >= now() - 7 dni`), a Energa ogłosiła je 28.07 —
dziesięć dni wcześniej. Feed i briefing dostały na to `event_at` w lipcu,
agent został z oknem publikacji. Stąd dwa okna w `_fetch_alert_articles`.
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Union, AsyncGenerator
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent
from src.database.schema import Article, Source
from src.services.feed_policy import is_local_article, publishable_conditions, time_label
from src.utils.logger import setup_logger

logger = setup_logger("StraznikAgent")

# Baza trzyma naiwny UTC, mieszkaniec pyta o godziny lokalne.
LOCAL_TZ = ZoneInfo("Europe/Warsaw")

# Zdarzenie z terminem: ile do przodu jeszcze o nim mówimy. Trzy doby to
# horyzont pytania „czy w tym tygodniu wyłączą prąd"; briefing ma własne 36 h,
# bo tam chodzi o jeden nagłówek, a tu o kompletną odpowiedź.
EVENT_LOOKAHEAD_H = 72

# Ile po zakończeniu wpis jeszcze coś wyjaśnia („wróciłem, było ciemno — czemu?")
EVENT_KEEP_AFTER_H = 6

# Wpisy BEZ terminu (awaria, która po prostu się wydarzyła) — jak dotąd
PUBLISHED_WINDOW_D = 7

def _local(value: datetime) -> datetime:
    return value.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ)


class StraznikAgent(BaseAgent):
    name = "straznik"
    display_name = "Straznik.ai"
    description = "Specjalista od awarii, zgloszen i bezpieczenstwa. Informuje o przerwach w dostawie mediow, awariach infrastruktury i zagrozeniach."
    avatar = "shield-alert"
    model = "gpt-4o-mini"
    temperature = 0.1
    source_types = []  # Direct DB queries, no RAG

    system_prompt = """Jestes Straznikiem - asystentem ds. bezpieczenstwa i awarii w gminie Rybno i najblizszych okolicach.
Twoja specjalizacja: awarie wody/pradu/gazu, zgłoszenia mieszkancow, zagrozenia, remonty drog, komunikaty RCB.

ZASADY:
- Odpowiadaj WYLACZNIE na podstawie dostarczonego kontekstu
- Ton: rzeczowy, spokojny, informacyjny - NIE wzbudzaj paniki
- ZAWSZE podawaj daty zdarzen i obszary oddzialywania (które ulice/dzielnice)
- Wpis oznaczony "ZDARZENIE dziś/jutro ..." opisuj po TERMINIE ZDARZENIA
  i podaj godziny. Data w nawiasie "(ogłoszono ...)" to tylko dzien zapowiedzi —
  wyłączenie zapowiedziane dwa tygodnie temu jest tak samo aktualne jak wczorajsze
  i NIE WOLNO go pominac ani nazwac stara informacja
- Jesli w kontekscie stoi JAKIEKOLWIEK zdarzenie zapowiedziane albo trwajace,
  NIE WOLNO odpowiedziec "brak awarii/zgloszen" bez jego wymienienia — takze gdy
  pytanie brzmi ogolnie ("czy sa awarie"). Poprawna odpowiedz to:
  "teraz nic nie trwa, ale zapowiedziano <co> <kiedy> w <gdzie>"
- Wpis "poza gminą Rybno" wymien tylko, gdy pytanie dotyczy okolic lub powiatu;
  przy pytaniu o gmine Rybno zaznacz wyraznie, ze zdarzenie jej nie obejmuje
- W przypadku awarii: podaj planowany czas usuniecia (jesli znany)
- Jesli brak danych o awarii - poinformuj ze brak aktualnych zglosen
- Numer alarmowy: 112. Zgloszenia: Urzad Gminy Rybno
- NIE pisz [Zrodlo: ...] w tekscie - zrodla sa podawane automatycznie przez system
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
        stream: bool = False,
        user=None
    ) -> Union[dict, AsyncGenerator]:
        """Generate response from direct DB queries — no RAG, no embed_text call"""
        from src.ai.agents.base_agent import base_context_messages
        reports = await self._fetch_recent_reports(session)
        awarie = await self._fetch_alert_articles(session)
        bip_docs = await self._fetch_recent_bip(session)

        context = self._build_context(reports, awarie, bip_docs)

        messages = [
            {"role": "system", "content": self.system_prompt},
            *base_context_messages(),
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

    async def _fetch_alert_articles(
        self, session: AsyncSession, now: Optional[datetime] = None
    ) -> list[dict]:
        """
        Awarie i zdarzenia z terminem — DWA okna, bo to dwa różne rodzaje wpisu:

        * awaria bez terminu (pękł wodociąg) żyje datą publikacji → 7 dni wstecz;
        * zdarzenie z terminem (wyłączenie prądu, ostrzeżenie IMGW) żyje datą
          ZDARZENIA → od 6 h po zakończeniu do 72 h w przód, bez względu na to,
          jak dawno je ogłoszono. Energa zapowiada wyłączenia i z dwutygodniowym
          wyprzedzeniem, a mieszkaniec pyta o nie w dniu wyłączenia.

        Kolejność: najbliższe zdarzeniu, nie najświeższe ogłoszeniem — to, co
        dzieje się teraz, ma być pierwsze w kontekście.

        `now` (naiwny UTC) wstrzykuje walidator, żeby odtworzyć konkretną chwilę
        — inaczej regresji z 7.08 nie da się powtórzyć po fakcie.
        """
        now = now or datetime.utcnow()

        result = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.processed == True)  # noqa: E712
            .where(*publishable_conditions(Article))
            .where(
                or_(
                    (Article.category == "Awaria")
                    & (Article.published_at >= now - timedelta(days=PUBLISHED_WINDOW_D)),
                    Article.event_at.is_not(None)
                    & (Article.event_at <= now + timedelta(hours=EVENT_LOOKAHEAD_H))
                    & (
                        func.coalesce(Article.event_until, Article.event_at)
                        >= now - timedelta(hours=EVENT_KEEP_AFTER_H)
                    ),
                )
            )
            .limit(20)
        )

        articles: list[dict] = []
        for article, source_name in result:
            stamp = article.event_at or article.published_at or now
            articles.append({
                "id": article.id,
                "title": article.display_title or article.title,
                "summary": article.summary or "",
                "url": article.url,
                "published_at": article.published_at,
                "event_at": article.event_at,
                "event_until": article.event_until,
                "source_name": source_name,
                # Feed Energi obejmuje CAŁY powiat — bez tego wyłączenie
                # w Płośnicy szło do mieszkańca Rybna jako jego awaria.
                "is_local": is_local_article(source_name, article.title, article.content),
                "when": time_label(
                    article.published_at,
                    article.event_at,
                    article.event_until,
                    now,
                    published_prefix="zgłoszono ",
                ),
                "_distance": abs((stamp - now).total_seconds()),
            })

        articles.sort(key=lambda a: a["_distance"])
        return articles[:10]

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

        parts.append("\n[AWARIE I ZDARZENIA Z TERMINEM (7 dni wstecz, 72 h w przód)]")
        if awarie:
            for a in awarie:
                zasieg = "gmina Rybno" if a.get("is_local") else "poza gminą Rybno"
                ogloszono = (
                    f" (ogłoszono {_local(a['published_at']):%d.%m.%Y})"
                    if a.get("event_at") and a.get("published_at")
                    else ""
                )
                summary = a.get("summary") or ""
                parts.append(
                    f"• {a['when']} | {zasieg} | {a['title']}{ogloszono}\n  {summary}"
                )
        else:
            parts.append("• Brak awarii i zapowiedzianych zdarzeń w tym oknie")

        parts.append("\n[DOKUMENTY BIP (ostatnie 14 dni)]")
        if bip_docs:
            for b in bip_docs:
                date = b["scraped_at"].strftime("%Y-%m-%d") if b.get("scraped_at") else "brak daty"
                content = (b.get("content") or "")[:300]
                parts.append(f"• {date} | {b['title']}\n  {content}")
        else:
            parts.append("• Brak dokumentów BIP z ostatnich 14 dni")

        return "\n".join(parts)
