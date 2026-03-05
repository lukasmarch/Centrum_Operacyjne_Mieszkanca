"""
Przewodnik.ai - Events, weather, culture and activities specialist agent
Uses live weather/airly/events from DB + RAG for event text search
"""
from typing import Union, AsyncGenerator, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent, get_datetime_context
from src.ai.embeddings import embedding_service
from src.utils.logger import setup_logger

logger = setup_logger("PrzewodnikAgent")


class PrzewodnikAgent(BaseAgent):
    name = "przewodnik"
    display_name = "Przewodnik.ai"
    description = "Specjalista od wydarzen, pogody i rekreacji. Podpowie co robic w gminie, jakie imprezy sa planowane i jak wygladaja warunki pogodowe."
    avatar = "map-pin"
    model = "gpt-4o-mini"
    temperature = 0.4
    source_types = ["event"]  # RAG only for event text search

    system_prompt = """Jestes Przewodnikiem - asystentem ds. wydarzen i aktywnosci w gminie Rybno i powiecie dzialdownskim.
Twoja specjalizacja: wydarzenia kulturalne, sportowe, festyny, pogoda, kino, co robic w wolnym czasie.

ZASADY:
- Odpowiadaj na podstawie dostarczonego kontekstu (pogoda, jakosc powietrza, wydarzenia)
- Ton: przyjazny, zachecajacy, entuzjastyczny
- ZAWSZE podawaj daty i miejsca wydarzen
- Interpretuj dane pogodowe i jakosci powietrza dla uzytkownika
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
        """Generate response with live weather/airly/events + RAG for event text search"""
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

        # 3. Build context
        context = self._build_context(weather, weather_week, air, events, event_docs)

        # 4. Collect sources from RAG
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
        event_docs: list
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

        return "\n".join(parts)
