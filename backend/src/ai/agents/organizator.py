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
- Harmonogram przyjęć lekarzy w poradniach SPGZOZ Rybno (POZ, Stomatologiczna, Ginekologiczna, Logopedyczna, Gabinet Zabiegowy, USG)
- Dyżury aptek w powiecie działdowskim

ZASADY:
- Odpowiadaj WYŁĄCZNIE na podstawie dostarczonego kontekstu
- Zawsze podawaj KONKRETNE daty (format DD.MM.YYYY) i godziny
- Ton: ciepły, przyjazny, pomocny
- Przy śmieciach: podaj ile dni pozostało do odbioru
- Przy kinie: podaj pełny repertuar z godzinami seansów
- Przy lekarzach: podaj imię i nazwisko lekarza, specjalizację oraz godziny przyjęć; jeśli są uwagi o zmianach — koniecznie je zaznacz
- Przy aptekach: podaj nazwę, adres i numer telefonu jeśli dostępny
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
        "Repertuar kina na weekend?",
        "Kiedy przyjmuje lekarz POZ?",
        "Ktora apteka dzis dyzuruje?",
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
        clinics = await self._fetch_clinic_schedule(session)
        pharmacies = await self._fetch_pharmacies(session)

        context = self._build_context(waste, cinema, town, clinics, pharmacies)

        user_info = ""
        if user:
            safe_name = self._sanitize_for_prompt(user.full_name or "")
            safe_location = self._sanitize_for_prompt(user.location or "")
            user_info = f"Zalogowany użytkownik: {safe_name} (miejscowość: {safe_location})\n"

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

    @staticmethod
    def _sanitize_for_prompt(value: str, max_len: int = 100) -> str:
        """Strip control characters and newlines to prevent prompt injection."""
        return "".join(ch for ch in value if ch >= " ").strip()[:max_len]

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

    async def _fetch_clinic_schedule(self, session: AsyncSession) -> list[dict]:
        """Pobiera harmonogram przyjęć lekarzy na dziś (day_of_week lub specific_date)."""
        from datetime import date
        today = date.today()
        dow = today.weekday()
        result = await session.execute(
            text("""
                SELECT clinic_name, doctor_name, doctor_role, hours_from, hours_to, notes, source_url
                FROM clinic_schedules
                WHERE day_of_week = :dow OR specific_date = :today
                ORDER BY clinic_name, hours_from
            """),
            {"dow": dow, "today": today},
        )
        return [dict(row._mapping) for row in result]

    async def _fetch_pharmacies(self, session: AsyncSession) -> list[dict]:
        """Pobiera dyżurujące apteki na dziś."""
        from datetime import date
        today = date.today()
        dow = today.weekday()
        result = await session.execute(
            text("""
                SELECT pharmacy_name, address, phone, hours_from, hours_to, duty_type, notes
                FROM pharmacy_duties
                WHERE valid_year = :year
                  AND (
                      duty_type = 'weekday'
                      OR (duty_type = 'weekend' AND (:dow = 5 OR :dow = 6))
                      OR (duty_type = 'holiday' AND :dow = 6)
                      OR day_of_week = :dow
                  )
                ORDER BY pharmacy_name
            """),
            {"year": today.year, "dow": dow},
        )
        return [dict(row._mapping) for row in result]

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

    def _build_context(self, waste: list[dict], cinema: list[dict], town: str, clinics: list[dict], pharmacies: list[dict]) -> str:
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

        # --- Harmonogram poradni (dziś) ---
        DAY_NAMES_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
        day_name = DAY_NAMES_PL[today.weekday()]
        parts.append(f"\n[HARMONOGRAM PORADNI SPGZOZ RYBNO - {day_name.upper()} {today.strftime('%d.%m.%Y')}]")
        if clinics:
            current_clinic = None
            for row in clinics:
                if row["clinic_name"] != current_clinic:
                    current_clinic = row["clinic_name"]
                    parts.append(f"\n  Poradnia {current_clinic}:")
                doctor = row["doctor_name"] or "—"
                role = f" ({row['doctor_role']})" if row.get("doctor_role") else ""
                hours = f"{row['hours_from']}-{row['hours_to']}"
                notes = f" ⚠ {row['notes']}" if row.get("notes") else ""
                parts.append(f"    • {doctor}{role} | {hours}{notes}")
        else:
            parts.append(f"  Brak zaplanowanych przyjęć na dziś ({day_name})")
        if clinics:
            parts.append(f"  Źródło: https://www.spgzozrybno.pl")

        # --- Dyżury aptek (dziś) ---
        parts.append(f"\n[DYŻURY APTEK - {today.strftime('%d.%m.%Y')}]")
        if pharmacies:
            seen = set()
            for row in pharmacies:
                key = f"{row['pharmacy_name']}_{row['hours_from']}"
                if key in seen:
                    continue
                seen.add(key)
                name = row["pharmacy_name"]
                addr = f" | {row['address']}" if row.get("address") else ""
                phone = f" | tel. {row['phone']}" if row.get("phone") else ""
                hours = f"{row['hours_from']}-{row['hours_to']}"
                parts.append(f"  • {name}{addr}{phone} | {hours}")
        else:
            parts.append("  Brak danych o dyżurach aptek na dziś")

        return "\n".join(parts)
