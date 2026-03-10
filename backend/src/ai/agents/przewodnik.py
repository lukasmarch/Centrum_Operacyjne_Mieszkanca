"""
Przewodnik.ai - Events, weather, culture, restaurants, attractions specialist agent
Uses live weather/airly/events from DB + RAG for event text search + local_places from Gemini Maps
"""
from typing import Union, AsyncGenerator, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent, get_datetime_context
from src.ai.embeddings import embedding_service
from src.utils.logger import setup_logger

logger = setup_logger("PrzewodnikAgent")

# Keywords -> category mapping for local_places
PLACE_KEYWORDS = {
    "restaurant": ["restaurac", "jedzeni", "jeść", "jesc", "pizza", "obiad", "kolacj", "bar ", "knajp", "kuchni"],
    "cafe": ["kawiar", "kawa", "cukiern", "lodziar", "lody", "ciast", "deser"],
    "hotel": ["hotel", "nocleg", "pensjonat", "agroturyst", "pokój", "pokoj", "zakwaterow", "spać", "spac"],
    "attraction": ["atrakcj", "muzeum", "zabyt", "zwiedzić", "zwiedzic", "histor", "zamek", "kościół", "kosciol"],
    "sport": ["sport", "boisko", "siłown", "silown", "basen", "kąpielis", "kapielis", "fitness", "hala sport"],
    "nature": ["jezior", "szlak", "las ", "lasy", "rezerw", "przyrод", "rower", "kajak", "spacer", "wycieczk", "pieszy"],
}


class PrzewodnikAgent(BaseAgent):
    name = "przewodnik"
    display_name = "Przewodnik.ai"
    description = "Specjalista od wydarzen, pogody, restauracji, atrakcji i miejsc do odwiedzenia. Podpowie co robic w gminie, gdzie zjesc i jakie imprezy sa planowane."
    avatar = "map-pin"
    model = "gpt-4o-mini"
    temperature = 0.4
    source_types = ["event"]  # RAG only for event text search

    system_prompt = """Jestes Przewodnikiem - asystentem ds. wydarzen, aktywnosci, restauracji i atrakcji turystycznych w gminie Rybno i powiecie dzialdownskim.
Twoja specjalizacja: wydarzenia kulturalne, sportowe, festyny, pogoda, restauracje, kawiarnie, hotele, atrakcje turystyczne, co robic w wolnym czasie.

ZASADY:
- Odpowiadaj na podstawie dostarczonego kontekstu (pogoda, jakosc powietrza, wydarzenia, lokalne miejsca)
- Ton: przyjazny, zachecajacy, entuzjastyczny
- ZAWSZE podawaj daty i miejsca wydarzen
- Interpretuj dane pogodowe i jakosci powietrza dla uzytkownika
- Znasz restauracje, kawiarnie, hotele, atrakcje turystyczne w okolicach Rybna i powiatu dzialdownskiego
- Przy rekomendacji miejsc: podaj nazwe, adres (jesli znany) i link do Google Maps jesli dostepny [Zrodlo: Google Maps]
- Znasz okolice Rybna: jeziora (Rumian, Hartowieckie), lasy, szlaki piesze/rowerowe, PKK Rybno
- Jesli nie ma blizszych wydarzen - zaproponuj wyszukanie alternatyw
- Odpowiadaj po polsku, zwiezle i praktycznie
- ZAWSZE cytuj zrodla: [Zrodlo: nazwa]

SEZONOWOSC - KLUCZOWE:
- Znasz aktualny dzien tygodnia, date i pore roku (podane w kontekscie)
- NIE proponuj aktywnosci niezgodnych z pora roku: np. kapielisko/plywanie w jeziorze w zimie lub na wiosnie
- Zima (grudzien-luty): proponuj spacery w zimowej scenerii, lodowisko w Dzialowie, kuligi, goraca herbate przy kominku
- Wiosna (marzec-maj): piesze wedrowki, rowerowe wycieczki, obserwacja przyrody budzacej sie do zycia
- Lato (czerwiec-sierpien): kapielisko Rybno, kajakarstwo, grzybobranie (sierpien+), pikniki
- Jesien (wrzesien-listopad): grzybobranie, spacery lesne, jesienna kolorystyka
- Uwzgledniaj temperatura z danych pogodowych przy rekomendacjach aktywnosci na zewnatrz"""

    example_questions = [
        "Co mozna robic w weekend w Rybnie?",
        "Jakie wydarzenia sa planowane w tym miesiacu?",
        "Gdzie zjesc w okolicach Rybna?",
        "Jakie atrakcje turystyczne sa w powiecie?",
        "Jak wygladaja warunki pogodowe?",
        "Czy sa jakies imprezy dla dzieci?"
    ]

    async def respond(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: list[dict] = None,
        stream: bool = False,
        user=None
    ) -> Union[dict, AsyncGenerator]:
        """Generate response with live weather/airly/events + RAG + local places"""
        # 1. RAG for event text matching
        event_docs = await embedding_service.semantic_search(
            session=session,
            query=user_message,
            top_k=4,
            source_types=["event"],
            similarity_threshold=0.25
        )

        # 2. Live structured data from DB
        weather = await self._fetch_current_weather(session)
        weather_week = await self._fetch_weekly_weather_summary(session)
        air = await self._fetch_current_air_quality(session)
        events = await self._fetch_upcoming_events(session)

        # 3. Local places from DB (Gemini Maps cache)
        place_category = self._detect_place_category(user_message)
        places = await self._fetch_local_places(session, category=place_category)

        # 4. Build context
        context = self._build_context(weather, weather_week, air, events, event_docs, places)

        # 5. Collect sources from RAG
        sources = []
        seen = set()
        for doc in event_docs:
            key = f"{doc['source_type']}:{doc['source_id']}"
            if key not in seen:
                seen.add(key)
                sources.append({
                    "type": doc["source_type"],
                    "id": doc["source_id"],
                    "title": doc["metadata"].get("title", ""),
                    "url": doc["metadata"].get("url", ""),
                    "similarity": doc["similarity"]
                })

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": get_datetime_context()},
            {"role": "system", "content": f"KONTEKST:\n{context}"}
        ]

        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        if stream:
            return await self._stream(messages, sources=sources)

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

    def _detect_place_category(self, user_message: str) -> Optional[str]:
        """Detect which place category the user is asking about."""
        msg_lower = user_message.lower()
        for category, keywords in PLACE_KEYWORDS.items():
            for kw in keywords:
                if kw in msg_lower:
                    return category
        # Generic "co robic", "gdzie isc" → return None to fetch all
        generic_keywords = ["co robic", "co robić", "gdzie isc", "gdzie iść", "wolny czas", "weekend", "spędz"]
        for kw in generic_keywords:
            if kw in msg_lower:
                return None  # fetch all categories
        return None

    async def _fetch_local_places(self, session: AsyncSession, category: Optional[str] = None) -> list[dict]:
        """Fetch local places from DB (cached Gemini Maps data)."""
        if category:
            result = await session.execute(
                text("""
                    SELECT name, category, description, address, maps_uri
                    FROM local_places
                    WHERE active = TRUE AND category = :cat
                    ORDER BY updated_at DESC
                    LIMIT 15
                """),
                {"cat": category}
            )
        else:
            result = await session.execute(text("""
                SELECT name, category, description, address, maps_uri
                FROM local_places
                WHERE active = TRUE
                ORDER BY category, updated_at DESC
                LIMIT 20
            """))
        return [dict(row._mapping) for row in result]

    async def _fetch_current_weather(self, session: AsyncSession) -> Optional[dict]:
        result = await session.execute(text("""
            SELECT temperature, feels_like, description, humidity,
                   wind_speed, pressure, clouds, rain_1h, fetched_at
            FROM weather
            WHERE is_current = True AND location = 'Rybno'
            ORDER BY fetched_at DESC
            LIMIT 1
        """))
        row = result.first()
        return dict(row._mapping) if row else None

    async def _fetch_weekly_weather_summary(self, session: AsyncSession) -> Optional[dict]:
        result = await session.execute(text("""
            SELECT
                ROUND(AVG(temperature)::numeric, 1) as avg_temp,
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                ROUND(AVG(humidity)::numeric, 0) as avg_humidity,
                COUNT(*) FILTER (WHERE rain_1h > 0) as rainy_hours
            FROM weather
            WHERE fetched_at >= now() - INTERVAL '7 days'
              AND location = 'Rybno'
        """))
        row = result.first()
        return dict(row._mapping) if row else None

    async def _fetch_current_air_quality(self, session: AsyncSession) -> Optional[dict]:
        result = await session.execute(text("""
            SELECT pm25, pm10, caqi, caqi_level, fetched_at
            FROM air_quality
            WHERE is_current = True AND location = 'Rybno'
            ORDER BY fetched_at DESC
            LIMIT 1
        """))
        row = result.first()
        return dict(row._mapping) if row else None

    async def _fetch_upcoming_events(self, session: AsyncSession) -> list[dict]:
        result = await session.execute(text("""
            SELECT title, description, event_date, location, category, organizer
            FROM events
            WHERE event_date >= now()
              AND event_date <= now() + INTERVAL '14 days'
            ORDER BY event_date ASC
            LIMIT 10
        """))
        return [dict(row._mapping) for row in result]

    def _build_context(
        self,
        weather: Optional[dict],
        weather_week: Optional[dict],
        air: Optional[dict],
        events: list,
        event_docs: list,
        places: list[dict]
    ) -> str:
        parts = []

        if weather:
            fetched = weather["fetched_at"].strftime("%Y-%m-%d %H:%M") if weather.get("fetched_at") else ""
            rain = f" | Opady: {weather['rain_1h']} mm/h" if weather.get("rain_1h") else ""
            parts.append(
                f"[POGODA AKTUALNA - Rybno, {fetched}]\n"
                f"Temperatura: {weather['temperature']}°C (odczuwalna {weather['feels_like']}°C) | Opis: {weather['description']}\n"
                f"Wilgotność: {weather['humidity']}% | Wiatr: {weather['wind_speed']} m/s | "
                f"Ciśnienie: {weather['pressure']} hPa{rain}"
            )
        else:
            parts.append("[POGODA AKTUALNA]\nBrak danych pogodowych")

        if weather_week and weather_week.get("avg_temp") is not None:
            parts.append(
                f"\n[POGODA - OSTATNIE 7 DNI]\n"
                f"Średnia: {weather_week['avg_temp']}°C | Min: {weather_week['min_temp']}°C | "
                f"Max: {weather_week['max_temp']}°C | Godziny z deszczem: {weather_week['rainy_hours'] or 0}"
            )

        if air:
            fetched = air["fetched_at"].strftime("%H:%M") if air.get("fetched_at") else ""
            parts.append(
                f"\n[JAKOŚĆ POWIETRZA - Rybno]\n"
                f"PM2.5: {air['pm25']} µg/m³ | PM10: {air['pm10']} µg/m³ | "
                f"CAQI: {air['caqi']} ({air['caqi_level']}) | Aktualizacja: {fetched}"
            )
        else:
            parts.append("\n[JAKOŚĆ POWIETRZA]\nBrak danych")

        parts.append("\n[NADCHODZĄCE WYDARZENIA - 14 dni]")
        if events:
            for ev in events:
                date = ev["event_date"].strftime("%Y-%m-%d") if ev.get("event_date") else "brak daty"
                loc = ev.get("location") or ""
                organizer = f" | org: {ev['organizer']}" if ev.get("organizer") else ""
                cat = f" [{ev['category']}]" if ev.get("category") else ""
                desc = (ev.get("description") or "")[:150]
                parts.append(f"• {date}{cat} | {ev['title']}{organizer}\n  {loc}{' — ' + desc if desc else ''}")
        else:
            parts.append("• Brak zaplanowanych wydarzeń w ciągu 14 dni")

        if event_docs:
            parts.append("\n[KONTEKST RAG - więcej wydarzeń]")
            for doc in event_docs:
                parts.append(f"---\n{doc['chunk_text']}")

        # Local places section
        if places:
            parts.append("\n[LOKALNE MIEJSCA I RESTAURACJE]")
            current_cat = None
            cat_labels = {
                "restaurant": "Restauracje i lokale",
                "cafe": "Kawiarnie i cukiernie",
                "hotel": "Noclegi",
                "attraction": "Atrakcje turystyczne",
                "sport": "Obiekty sportowe",
                "nature": "Przyroda i szlaki",
            }
            for place in places:
                cat = place.get("category", "")
                if cat != current_cat:
                    current_cat = cat
                    parts.append(f"\n  {cat_labels.get(cat, cat)}:")
                name = place["name"]
                addr = f" | {place['address']}" if place.get("address") else ""
                maps = f" | Maps: {place['maps_uri']}" if place.get("maps_uri") else ""
                desc = f"\n    {place['description'][:150]}" if place.get("description") else ""
                parts.append(f"  • {name}{addr}{maps}{desc}")

        return "\n".join(parts)
