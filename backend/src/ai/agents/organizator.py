"""
Organizator.ai — praktyczny organizator codziennego życia
Harmonogram śmieci, repertuar kina, atrakcje i co robić w wolnym czasie.
Używa bezpośrednich zapytań SQL (bez RAG).
"""
from typing import Union, AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent, get_datetime_context
from src.utils.logger import setup_logger

logger = setup_logger("OrganizatorAgent")

# Wszystkie miejscowości w harmonogramie śmieci
KNOWN_TOWNS = [
    "Rybno R1", "Rybno R2", "Rybno",
    "Jeglia", "Gralewo Stacja", "Gronowo", "Grądy", "Wery",
    "Kopaniarze", "Grabacz", "Koszelewki", "Koszelewy", "Żabiny",
    "Rapaty", "Prusy", "Szczupliny", "Nowa Wieś", "Groszki",
    "Naguszewo", "Rumian", "Truszczyny", "Dębień", "Hartowiec",
    "Tuczki", "Domki letniskowe",
]

SYSTEM_PROMPT = """Jesteś Organizatorem — praktycznym asystentem codziennego życia mieszkańców Gminy Rybno i powiatu działdowskiego.

Twoje specjalizacje:
- Harmonogram wywozu śmieci (konkretne daty dla każdej miejscowości)
- Repertuar kina (Działdowo, Lubawa)

ZASADY:
- Odpowiadaj WYŁĄCZNIE na podstawie dostarczonego kontekstu
- Zawsze podawaj KONKRETNE daty (format DD.MM.YYYY)
- Ton: ciepły, przyjazny, pomocny
- Przy śmieciach: podaj ile dni pozostało do odbioru
- Przy kinie: podaj pełny repertuar z godzinami seansów
- Jeśli ktoś pyta o atrakcje, restauracje, co robić w wolnym czasie — powiedz że to domena Przewodnika i zasugeruj zmianę agenta
- Jeśli brak danych w bazie — powiedz wprost i zaproponuj alternatywę
- Odpowiadaj po polsku, zwięźle i konkretnie"""


class OrganizatorAgent(BaseAgent):
    name = "organizator"
    display_name = "Organizator.ai"
    description = "Praktyczny organizator: harmonogram smieci i repertuar kina."
    avatar = "calendar-check"
    model = "gpt-4o-mini"
    temperature = 0.4
    source_types = []  # direct SQL, brak RAG

    example_questions = [
        "Kiedy wywoz smieci w Rybnie?",
        "Co gra dzis w kinie w Dzialowie?",
        "Jaki typ smieci odbieraja w tym tygodniu?",
        "Repertuar kina na weekend?"
    ]

    async def respond(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: list[dict] = None,
        stream: bool = False,
        user=None,
    ) -> Union[dict, AsyncGenerator]:
        """Generate response from direct DB queries — no RAG"""
        # Determine default town from user profile if logged in
        default_town = "Rybno R1"
        if user and getattr(user, "location", None):
            # Normalize user.location to match KNOWN_TOWNS
            user_loc = user.location.strip()
            for t in KNOWN_TOWNS:
                if t.lower() == user_loc.lower():
                    default_town = t
                    break
            else:
                # Partial match - e.g. "Rybno" → "Rybno R1"
                if user_loc.lower() == "rybno":
                    default_town = "Rybno R1"

        town = self._extract_town(user_message, default_town=default_town)
        waste = await self._fetch_waste(session, town=town, days=30)
        cinema = await self._fetch_cinema(session)

        context = self._build_context(waste, cinema, town)

        user_info = ""
        if user:
            user_info = f"Zalogowany użytkownik: {user.full_name} (miejscowość: {user.location})\n"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": get_datetime_context() + (f"\n{user_info}" if user_info else "")},
            {"role": "system", "content": f"KONTEKST:\n{context}"},
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
            max_tokens=self.max_tokens,
        )

        return {
            "answer": response.choices[0].message.content,
            "sources": [],
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "model": self.model,
            "agent_name": self.name,
        }

    def _extract_town(self, user_message: str, default_town: str = "Rybno R1") -> str:
        """Heurystyka: szukaj nazwy miejscowości w treści wiadomości. Default z profilu użytkownika."""
        msg_lower = user_message.lower()
        for town in KNOWN_TOWNS:
            if town.lower() in msg_lower:
                # "Rybno" alone → default to R1 unless R2 explicitly mentioned
                if town == "Rybno":
                    if "r2" in msg_lower or "rejon 2" in msg_lower:
                        return "Rybno R2"
                    return "Rybno R1"
                return town
        return default_town

    async def _fetch_waste(self, session: AsyncSession, town: str = "Rybno R1", days: int = 30) -> list[dict]:
        """Pobiera harmonogram śmieci dla danej miejscowości (najbliższe N dni)."""
        result = await session.execute(
            text("""
                SELECT waste_type, collection_date
                FROM waste_schedule
                WHERE town = :town
                  AND collection_date >= CURRENT_DATE
                  AND collection_date <= CURRENT_DATE + :days * INTERVAL '1 day'
                ORDER BY collection_date, waste_type
            """),
            {"town": town, "days": days},
        )
        return [{"waste_type": row[0], "collection_date": row[1]} for row in result]

    async def _fetch_cinema(self, session: AsyncSession) -> list[dict]:
        """Pobiera repertuar kin na dziś i jutro."""
        result = await session.execute(
            text("""
                SELECT cinema_name, date, title, genre, showtimes, link
                FROM cinema_showtimes
                WHERE date IN (
                    TO_CHAR(CURRENT_DATE, 'DD.MM.YYYY'),
                    TO_CHAR(CURRENT_DATE + INTERVAL '1 day', 'DD.MM.YYYY')
                )
                ORDER BY cinema_name, date, title
            """)
        )
        return [
            {
                "cinema_name": row[0],
                "date": row[1],
                "title": row[2],
                "genre": row[3],
                "showtimes": row[4],
                "link": row[5],
            }
            for row in result
        ]

    def _build_context(self, waste: list[dict], cinema: list[dict], town: str) -> str:
        """Formatuje dane dla LLM."""
        from datetime import date
        today = date.today()
        parts = []

        # --- Harmonogram śmieci ---
        parts.append(f"[HARMONOGRAM ŚMIECI - Gmina Rybno | {town} | Najbliższe 30 dni]")
        if waste:
            # Grupuj po dacie
            by_date: dict[str, list[str]] = {}
            for row in waste:
                col_date = row["collection_date"]
                days_left = (col_date - today).days
                date_str = col_date.strftime("%d.%m.%Y")
                label = f"{date_str} (za {days_left} dni)" if days_left > 0 else f"{date_str} (DZIŚ)"
                by_date.setdefault(label, []).append(row["waste_type"])
            for label, types in by_date.items():
                parts.append(f"  {label}: {', '.join(types)}")
        else:
            parts.append(f"  Brak zaplanowanych odbiorów w najbliższych 30 dniach dla: {town}")

        # --- Repertuar kina ---
        parts.append("\n[REPERTUAR KIN - dziś i jutro]")
        if cinema:
            current_cinema = None
            current_date = None
            for row in cinema:
                if row["cinema_name"] != current_cinema:
                    current_cinema = row["cinema_name"]
                    parts.append(f"\n  {current_cinema}")
                if row["date"] != current_date:
                    current_date = row["date"]
                    parts.append(f"  {current_date}:")
                showtimes_str = ", ".join(row["showtimes"]) if row["showtimes"] else "brak godzin"
                parts.append(f'    • "{row["title"]}" ({row["genre"]}) | Seanse: {showtimes_str}')
        else:
            parts.append("  Brak danych o repertuarze kin na dziś/jutro")

        return "\n".join(parts)
