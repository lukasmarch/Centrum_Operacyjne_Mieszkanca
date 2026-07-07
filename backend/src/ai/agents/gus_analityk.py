"""
GUS-Analityk.ai - Statistics and data storytelling specialist
Uses direct SQL to gus_gmina_stats — no RAG
"""
import json
from typing import Union, AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.base_agent import BaseAgent
from src.utils.logger import setup_logger

logger = setup_logger("GUSAnalitykAgent")

GUS_CATEGORIES = [
    "demografia", "rynek_pracy", "przedsiebiorczosc",
    "finanse_gminy", "mieszkalnictwo", "edukacja",
    "transport", "bezpieczenstwo", "zdrowie", "turystyka"
]

CATEGORY_CLASSIFY_PROMPT = """Sklasyfikuj pytanie użytkownika do jednej kategorii danych GUS.

Kategorie i ich zakres:
- demografia: liczba ludności, urodzenia, zgony, migracje, wiek mieszkańców, przyrost naturalny
- rynek_pracy: bezrobocie, zatrudnienie, pracujący, wynagrodzenia
- przedsiebiorczosc: firmy, podmioty gospodarcze, REGON, nowe działalności
- finanse_gminy: budżet, dochody i wydatki gminy, subwencje, podatki lokalne
- mieszkalnictwo: mieszkania, budownictwo, pozwolenia na budowę, zasoby mieszkaniowe
- edukacja: szkoły, przedszkola, uczniowie, wyniki egzaminów
- transport: drogi, pojazdy, komunikacja
- bezpieczenstwo: przestępstwa (kryminalne, gospodarcze, drogowe, przeciwko mieniu/rodzinie), wypadki drogowe
- zdrowie: przychodnie, apteki, porady lekarskie
- turystyka: noclegi, turyści, baza turystyczna

Odpowiedz TYLKO nazwą kategorii (np. "bezpieczenstwo"). Jeśli pytanie dotyczy kilku — wybierz główną. Jeśli żadna nie pasuje — "demografia"."""


class GUSAnalitykAgent(BaseAgent):
    name = "gus_analityk"
    display_name = "GUS-Analityk.ai"
    description = "Analityk danych statystycznych. Interpretuje dane GUS, pokazuje trendy demograficzne i ekonomiczne gminy."
    avatar = "bar-chart"
    model = "gpt-4o"
    temperature = 0.2
    source_types = []  # Direct SQL to gus_gmina_stats, no RAG

    system_prompt = """Jestes GUS-Analitykiem - ekspertem od danych statystycznych Centrum Operacyjnego Mieszkanca RybnoLive.
Twoja specjalizacja: dane GUS BDL, demografia, rynek pracy, finanse gminy, przedsiebiorczosc, porownania z innymi gminami.

ZASADY:
- Analizuj dane liczbowe w kontekscie (trendy, porownania, anomalie)
- Ton: analityczny, rzeczowy, z elementami Data Storytelling
- ZAWSZE podawaj konkretne liczby i lata
- Porownuj z powiatem i srednia krajowa jesli dostepne
- Wyciagaj wnioski: "To oznacza, ze Rybno..."
- Jesli nie masz danych - powiedz wprost i zaproponuj sprawdzenie innej kategorii
- Formatuj dane w tabelach lub punktach dla czytelnosci
- Uzywaj markdown: **pogrubienie**, # naglowki, - listy
- Odpowiadaj po polsku"""

    example_questions = [
        "Ile osob mieszka w Rybnie?",
        "Jak wyglada demografia gminy?",
        "Jakie sa dochody gminy?",
        "Ile firm dziala w Rybnie?"
    ]

    async def respond(
        self,
        session: AsyncSession,
        user_message: str,
        conversation_history: list[dict] = None,
        stream: bool = False,
        user=None
    ) -> Union[dict, AsyncGenerator]:
        """Generate response using GUS DB data — no RAG, no embed_text call"""
        from src.ai.agents.base_agent import get_datetime_context
        # 1. Classify query to GUS category
        category = await self._classify_gus_query(user_message)
        logger.info(f"GUS query classified as: {category}")

        # 2. Fetch GUS data
        rows = await self._fetch_gus_rows(session, category)
        context = self._format_gus_context(rows, category)
        charts = self._build_chart_data(rows)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": get_datetime_context()},
            {"role": "system", "content": context}
        ]

        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        if stream:
            return await self._stream_with_charts(messages, charts)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        return {
            "answer": response.choices[0].message.content,
            "sources": [],
            "chart_data": charts,
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "model": self.model,
            "agent_name": self.name
        }

    async def _classify_gus_query(self, user_message: str) -> str:
        """Classify user question to GUS category using GPT-4o-mini (fast, temp=0)"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": CATEGORY_CLASSIFY_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0,
                max_tokens=20
            )
            category = response.choices[0].message.content.strip().lower()
            if category in GUS_CATEGORIES:
                return category
            # Try partial match
            for cat in GUS_CATEGORIES:
                if cat in category:
                    return cat
            return "demografia"
        except Exception as e:
            logger.error(f"Category classification failed: {e}")
            return "demografia"

    # Gmina Rybno + Powiat Działdowski. Część kategorii (bezpieczeństwo,
    # transport, turystyka, większość rynku pracy) ma dane WYŁĄCZNIE na
    # poziomie powiatu — filtrowanie po samej gminie zwracało pustkę.
    UNIT_GMINA = "042815403062"
    UNIT_POWIAT = "042815403000"

    async def _fetch_gus_rows(self, session: AsyncSession, category: str) -> list[dict]:
        """Fetch GUS data rows for a category (gmina + powiat), returns list of dicts"""
        try:
            result = await session.execute(text("""
                SELECT g.var_name, g.unit_id, g.unit_name, g.year, g.value,
                       n.value as avg_national
                FROM gus_gmina_stats g
                LEFT JOIN gus_national_averages n
                    ON g.var_id = n.var_id AND g.year = n.year AND n.level = 'national'
                WHERE g.unit_id IN (:unit_gmina, :unit_powiat)
                  AND g.category = :category
                ORDER BY g.unit_id DESC, g.var_name, g.year DESC
            """), {
                "category": category,
                "unit_gmina": self.UNIT_GMINA,
                "unit_powiat": self.UNIT_POWIAT,
            })

            rows = result.all()
            return [
                {
                    "var_name": row.var_name,
                    "unit_id": row.unit_id,
                    "unit_name": row.unit_name,
                    "year": row.year,
                    "value": row.value,
                    "avg_national": row.avg_national
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch GUS rows: {e}")
            return []

    def _format_gus_context(self, rows: list[dict], category: str) -> str:
        """Format rows as text table for LLM context, split per unit (gmina/powiat)"""
        if not rows:
            return (
                f"[DANE GUS - Gmina Rybno | Kategoria: {category}]\n"
                "Brak danych dla tej kategorii w bazie danych.\n"
                f"Dostępne kategorie: {', '.join(GUS_CATEGORIES)}"
            )

        col_sep = " | "
        lines = [f"[DANE GUS | Kategoria: {category}]", ""]

        # Sekcja per jednostka: najpierw gmina Rybno, potem powiat działdowski
        for unit_id, unit_label in [
            (self.UNIT_GMINA, "GMINA RYBNO"),
            (self.UNIT_POWIAT, "POWIAT DZIAŁDOWSKI (dane niedostępne na poziomie gminy)"),
        ]:
            unit_rows = [r for r in rows if r["unit_id"] == unit_id]
            if not unit_rows:
                continue

            data_by_var: dict[str, list] = {}
            for row in unit_rows:
                data_by_var.setdefault(row["var_name"], []).append(row)

            lines.append(f"=== {unit_label} ===")
            lines.append(f"{'Zmienna':<45}{col_sep}{'Rok':>4}{col_sep}{'Wartość':>15}{col_sep}{'Śr. krajowa':>15}")
            lines.append("-" * 88)

            for var_name, var_rows in data_by_var.items():
                for row in var_rows[:3]:  # max 3 years per variable
                    value_str = f"{row['value']:,.1f}" if row['value'] is not None else "brak"
                    national_str = f"{row['avg_national']:,.1f}" if row['avg_national'] is not None else "—"
                    lines.append(
                        f"{var_name[:45]:<45}{col_sep}{row['year']:>4}{col_sep}"
                        f"{value_str:>15}{col_sep}{national_str:>15}"
                    )
            lines.append("")

        lines.append("WAŻNE: przy danych powiatowych zaznacz w odpowiedzi, że dotyczą powiatu działdowskiego, nie samej gminy.")
        return "\n".join(lines)

    def _build_chart_data(self, rows: list[dict]) -> list[dict]:
        """Build chart configs from rows: max 1 TrendChart + 1 KPI.

        Wykresy z JEDNEJ jednostki (preferowana gmina, fallback powiat) —
        mieszanie gminy i powiatu w jednej serii fałszowałoby trend.
        """
        if not rows:
            return []

        gmina_rows = [r for r in rows if r.get("unit_id") == self.UNIT_GMINA]
        chart_rows = gmina_rows or rows
        unit_suffix = "" if gmina_rows else " (powiat działdowski)"

        charts = []
        by_var: dict[str, list] = {}
        for row in chart_rows:
            by_var.setdefault(row["var_name"] + unit_suffix, []).append(row)

        # Sort by number of data points descending (most data first)
        sorted_vars = sorted(by_var.items(), key=lambda x: len(x[1]), reverse=True)

        trend_added = kpi_added = False
        for var_name, var_rows in sorted_vars:
            sorted_rows = sorted(var_rows, key=lambda r: r["year"])
            valid_rows = [r for r in sorted_rows if r["value"] is not None]

            if not trend_added and len(valid_rows) >= 2:
                charts.append({
                    "chart_type": "trend",
                    "title": var_name,
                    "data": [{"year": r["year"], "value": r["value"]} for r in valid_rows]
                })
                trend_added = True

            elif not kpi_added and valid_rows and var_rows[0].get("avg_national") is not None:
                latest = valid_rows[-1]
                prev = valid_rows[-2] if len(valid_rows) >= 2 else None
                trend_pct = None
                if prev and prev["value"]:
                    trend_pct = round((latest["value"] - prev["value"]) / prev["value"] * 100, 1)
                charts.append({
                    "chart_type": "kpi",
                    "title": var_name,
                    "current_value": latest["value"],
                    "national_value": latest["avg_national"],
                    "year": latest["year"],
                    "trend_pct": trend_pct,
                    "sparkline": [{"year": r["year"], "value": r["value"]} for r in valid_rows]
                })
                kpi_added = True

            if trend_added and kpi_added:
                break

        return charts

    async def _stream_with_charts(self, messages: list[dict], charts: list[dict]) -> AsyncGenerator:
        """Stream response, injecting chart_data event before done"""
        base_gen = await self._stream(messages, sources=[])

        async def augmented():
            async for event_str in base_gen:
                parsed = json.loads(event_str.rstrip('\n'))
                if parsed.get("type") == "done" and charts:
                    yield json.dumps({"type": "chart_data", "charts": charts}) + "\n"
                yield event_str

        return augmented()
