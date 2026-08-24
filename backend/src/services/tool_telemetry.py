"""
Telemetria narzędzi agentów (etap 6, 2026-08-24)

**Po co.** Do 22.08 wiedza o tym, że agent czegoś nie znalazł, brała się
z przypadku: ktoś kliknął podpowiedź, zobaczył „nie mam prognozy w bazie"
i zgłosił. Prognoza była w bazie od godziny. Po przejściu na narzędzia ten
sam błąd ma wreszcie kształt, który da się zliczyć — narzędzie zawołane,
`ToolResult.empty = True` — więc przestaje zależeć od tego, czy ktoś patrzył.

**Dlaczego OSOBNA sesja bazy, a nie ta z requestu.** Trzy powody, każdy
wystarczający:

1. `AsyncSession` obsługuje jedną operację naraz. Sesja requestu należy
   w tym momencie do pętli narzędziowej — to ta sama pułapka, na której
   22.08 padło `asyncio.gather` (`concurrent operations are not permitted`);
2. `commit()` na sesji requestu zatwierdziłby wszystko, co ten request miał
   w locie. Log narzędzia nie ma prawa decydować o cudzej transakcji;
3. telemetria, która wywraca odpowiedź, jest gorsza od braku telemetrii.
   Osobna sesja + `try` wokół zapisu znaczy, że najgorsze, co się może stać,
   to brak wiersza w tabeli.

**Dlaczego zapis po każdej rundzie, a nie na końcu odpowiedzi.** Strumień
kończy się też wtedy, gdy przeglądarka się rozłączy, a `finally` w generatorze
asynchronicznym nie może bezpiecznie czekać na `await` po `GeneratorExit`.
Runda to najwyżej kilka wierszy i jeden INSERT obok głównego połączenia —
przy rundzie modelu liczonej w sekundach to koszt niemierzalny.
"""
from dataclasses import dataclass, field
from typing import Optional

from src.database.connection import async_session
from src.database.vectors import AgentToolCall
from src.utils.logger import setup_logger

logger = setup_logger("ToolTelemetry")

# Tyle pytania trafia do bazy. Skrót ma wystarczyć do rozpoznania intencji
# („kiedy wywóz w Hartowcu"), nie do odtworzenia rozmowy — pełna treść leży
# i tak w `chat_messages`, a duplikowanie danych osobowych bez potrzeby jest
# dokładnie tym, czego RODO zabrania (art. 5 ust. 1 lit. c).
QUESTION_LIMIT = 200

# Argumenty bywają długie (przepisane zapytanie do RAG). Obcinamy wartości,
# nie klucze — bo to nazwa parametru mówi, czy model dobrał właściwe pole.
ARG_VALUE_LIMIT = 120


@dataclass
class ToolTelemetry:
    """Bufor wywołań z JEDNEJ odpowiedzi agenta.

    Nie jest współdzielony między requestami i nie ma stanu poza listą —
    dzięki temu nie trzeba się zastanawiać, co się stanie przy dwóch
    rozmowach naraz.
    """
    agent_name: str
    question: Optional[str] = None
    user_id: Optional[int] = None
    pending: list = field(default_factory=list)

    def record(
        self,
        tool_name: str,
        state: str,
        error: Optional[str],
        args: Optional[dict],
        duration_ms: int,
    ) -> None:
        self.pending.append(AgentToolCall(
            agent_name=self.agent_name[:50],
            tool_name=tool_name[:60],
            state=state[:20],
            error=error[:30] if error else None,
            args=_trim_args(args),
            duration_ms=duration_ms,
            question=(self.question or "")[:QUESTION_LIMIT] or None,
            user_id=self.user_id,
        ))

    async def flush(self) -> int:
        """Zapisuje bufor i go opróżnia. Nigdy nie rzuca wyjątkiem."""
        if not self.pending:
            return 0
        rows, self.pending = self.pending, []
        try:
            async with async_session() as session:
                session.add_all(rows)
                await session.commit()
            return len(rows)
        except Exception as e:
            # Świadomie tylko log: brak wiersza w tabeli diagnostycznej nie
            # jest powodem, żeby mieszkaniec nie dostał odpowiedzi.
            logger.error(f"Nie zapisano telemetrii ({len(rows)} wywołań): {e}")
            return 0


def _trim_args(args: Optional[dict]) -> Optional[dict]:
    if not args:
        return None
    trimmed = {}
    for key, value in list(args.items())[:10]:
        if isinstance(value, str):
            trimmed[key] = value[:ARG_VALUE_LIMIT]
        elif isinstance(value, (int, float, bool)) or value is None:
            trimmed[key] = value
        else:
            trimmed[key] = str(value)[:ARG_VALUE_LIMIT]
    return trimmed
