"""
Redaktor.ai - News and articles specialist agent

Dlaczego oprócz RAG dostaje gotowy blok świeżego feedu. Na „Co nowego w gminie?"
(9.08.2026) retrieval zwrócił sześć wpisów: Działdowo z 2.08, Płośnica z 25.02,
Lubowidz z 19.03, Stawiguda z 31.03 — same cudze gminy, najstarszy sprzed pół
roku. Model zachował się poprawnie, nie podając tego jako nowin, i uciekł
w wiedzę ogólną („nie mam aktualnych artykułów"), mając w bazie 16 świeżych
wpisów. Pytanie ogólne nie ma słów, które cokolwiek wyróżniają, więc najbliższymi
sąsiadami wektora są chunki ze słowami „nowe" i „gmina"; `rag_recency_boost`
tego nie przebija. Świeżość nie jest zadaniem dla wyszukiwarki podobieństwa —
to zwykłe zapytanie po dacie, tak samo jak w feedzie i briefingu.
"""
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent
from src.database.schema import Article, Source
from src.services.feed_policy import (
    article_score,
    collapse_duplicates,
    dedup_text,
    is_local_article,
    publishable_conditions,
    time_label,
)

# Okno „co słychać". Dwie doby, bo w sobotę rano pytanie dotyczy też piątku.
FEED_WINDOW_H = 48

# Ile wpisów wchodzi do promptu. Osiem to ~900 znaków — przy kontekście RAG
# rzędu 5–6 tys. znaków to margines, a nie rozdęcie. Podniesienie tej liczby
# odbija się na KAŻDYM pytaniu do Redaktora, także tym o jedną konkretną sprawę.
FEED_MAX_ITEMS = 8

# Streszczenie skracamy — blok ma powiedzieć CO SIĘ DZIEJE, szczegóły dowozi RAG.
FEED_SUMMARY_CHARS = 110

# Blok waży ~1,5 kB, czyli mniej więcej tyle co cały kontekst z RAG. Doklejany
# bezwarunkowo konkurowałby o uwagę modelu przy pytaniu o jedną konkretną sprawę
# („kiedy mecz Delfina") — ten sam argument, przez który karta gminy ma limit 2 kB.
# Wchodzi więc w dwóch sytuacjach: gdy pytanie jest z natury ogólne albo gdy
# retrieval i tak nic sensownego nie przyniósł.
_GENERIC_QUESTION = re.compile(
    r"co (nowego|slychac|sie (dzieje|dzialo|wydarzylo|stalo))"
    r"|nowinki|aktualnosci|najnowsze|ostatnie (wiadomosci|artykuly|wydarzenia)"
    r"|podsumuj|przeglad|co u nas|jakie (sa )?(wiadomosci|newsy)"
)

# Poniżej tylu trafień z RAG uznajemy, że wyszukiwarka nie dowiozła materiału
MIN_RAG_HITS = 3


def _flat(text: str) -> str:
    """Bez ogonków i wielkości liter — „ł" trzeba podmienić ręcznie (patrz `alert_policy`)."""
    import unicodedata

    lowered = (text or "").lower().replace("ł", "l")
    stripped = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in stripped if not unicodedata.combining(c))


class RedaktorAgent(BaseAgent):
    name = "redaktor"
    display_name = "Redaktor.ai"
    description = "Specjalista od wiadomosci lokalnych. Podsumowuje artykuly, informuje o najwazniejszych wydarzeniach w gminie."
    avatar = "newspaper"
    model = "gpt-4o-mini"
    temperature = 0.3
    source_types = ["article"]
    rag_top_k = 8
    rag_threshold = 0.35
    rag_semantic_weight = 0.90  # BM25 bez stemmingu polskiego szkodzi - dominuje semantic
    rag_recency_boost = 0.25

    system_prompt = """Jestes Redaktorem - asystentem informacyjnym Centrum Operacyjnego Mieszkanca RybnoLive.
Twoja specjalizacja: wiadomosci lokalne, artykuly, aktualnosci z gminy Rybno i najblizszych okolic.

ZASADY ODPOWIEDZI:
1. Jesli kontekst zawiera trafne artykuly - odpowiedz na ich podstawie, wymieniajac konkretne nazwy, daty, fakty.
2. Blok "SWIEZY FEED" to najnowsze wpisy z serwisu, uporzadkowane jak na stronie glownej.
   Przy pytaniu ogolnym ("co nowego", "co slychac", "co sie dzialo") odpowiadaj Z NIEGO:
   wymien 3-5 pozycji z datami, zaczynajac od wpisow oznaczonych [gmina Rybno].
   Majac ten blok NIE WOLNO odpowiedziec "nie mam aktualnych artykulow".
3. Jesli kontekst jest slabo trafny i pytanie dotyczy tematu spoza feedu - odpowiedz z WIEDZY OGOLNEJ,
   zaznaczajac to krotko na poczatku, np: "Nie mam aktualnych artykulow na ten temat, ale moge powiedziec:"
4. Pytania o statystyki, dane liczbowe, demografię → zasugeruj skorzystanie z agenta GUS.
5. Nie wymyslaj konkretnych dat, adresow ani danych - mow ogolnie gdy nie masz pewnosci.

STYL: obiektywny, dziennikarski, rzeczowy. Max 3-4 akapity. Odpowiadaj po polsku."""

    example_questions = [
        "Co nowego w Rybnie?",
        "Jakie sa najnowsze wiadomosci?",
        "Co sie dzisiaj wydarzylo?",
        "Podsumuj ostatnie artykuly"
    ]

    async def extra_context(
        self,
        session: AsyncSession,
        user_message: str,
        retrieved_ids: set,
    ) -> Optional[str]:
        """Najświeższe wpisy serwisu — ta sama polityka treści co feed i briefing."""
        generic = bool(_GENERIC_QUESTION.search(_flat(user_message)))
        if not generic and len(retrieved_ids) >= MIN_RAG_HITS:
            return None  # pytanie konkretne, retrieval dowiózł materiał

        now = datetime.utcnow()
        articles = await self._fetch_fresh_feed(session, now)

        rows = []
        for article, source_name in articles:
            if article.id in retrieved_ids:
                continue  # ten sam materiał już wszedł przez RAG
            summary = (article.summary or "").strip().replace("\n", " ")
            if len(summary) > FEED_SUMMARY_CHARS:
                summary = summary[:FEED_SUMMARY_CHARS].rstrip() + "…"
            zasieg = (
                "gmina Rybno"
                if is_local_article(source_name, article.title, article.content)
                else "okolice"
            )
            when = time_label(article.published_at, article.event_at, article.event_until, now)
            title = article.display_title or article.title or ""
            rows.append(f"• {when} | [{zasieg}] {title}" + (f"\n  {summary}" if summary else ""))

        if not rows:
            return None

        return (
            f"SWIEZY FEED (ostatnie {FEED_WINDOW_H} h, kolejność jak na stronie głównej):\n"
            + "\n".join(rows)
        )

    async def _fetch_fresh_feed(self, session: AsyncSession, now: datetime) -> list:
        """
        Wpisy z okna czasowego, przepuszczone przez politykę feedu: bez reklam
        i zapychaczy, bez duplikatów z dwóch źródeł, w kolejności wagi źródła
        × świeżości. Zdarzenie z terminem liczy się od TERMINU (`article_score`),
        więc jutrzejsze wyłączenie prądu nie wypada z „co nowego".
        """
        window_start = now - timedelta(hours=FEED_WINDOW_H)

        result = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.processed == True)  # noqa: E712
            .where(*publishable_conditions(Article))
            .where(
                or_(
                    Article.published_at >= window_start,
                    Article.event_at >= now,
                )
            )
            .order_by(func.coalesce(Article.event_at, Article.published_at).desc())
            .limit(60)
        )
        rows = list(result)

        # Kolejność PRZED deduplikacją, bo `collapse_duplicates` zostawia wpis
        # wcześniejszy — na liście nieposortowanej zostawiłaby przypadkowy.
        rows.sort(
            key=lambda row: article_score(
                row[0].published_at,
                row[0].scraped_at,
                row[1],
                now,
                row[0].event_at,
                row[0].event_until,
                row[0].content_score,
            ),
            reverse=True,
        )
        rows = collapse_duplicates(rows, text_of=lambda row: dedup_text(row[0]))
        return rows[:FEED_MAX_ITEMS]
