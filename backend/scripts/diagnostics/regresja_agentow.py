"""
Regresja agentów — 30 pytań kampanijnych przez orchestrator (routing + odpowiedź).

Mierzy wskaźnik odmów ("nie znalazłem", "nie posiadam informacji", ślepe zaułki).
Uruchamiać po każdej zmianie w RAG/promptach, żeby porównać przed/po.

Uruchomienie (w kontenerze backendu na prod):
  docker compose -f docker-compose.prod.yml exec -T backend \
      python -u -m scripts.diagnostics.regresja_agentow

Lokalnie: cd backend && python -u -m scripts.diagnostics.regresja_agentow
Koszt: ~30 zapytań GPT-4o-mini/GPT-4o (kilka groszy).
"""
import asyncio
import re
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.ai.agents import (
    orchestrator, RedaktorAgent, UrzednikAgent, GUSAnalitykAgent,
    PrzewodnikAgent, StraznikAgent, OrganizatorAgent,
)

# Pytania z kampanii "Twoja gmina. Na żywo." + realne pytania mieszkańców
PYTANIA = [
    # Procedury urzędowe (przypadek ze zrzutu kampanii)
    "Jak wyrobić dowód osobisty w gminie Rybno?",
    "Gdzie złożyć deklarację śmieciową?",
    "Jak zameldować się w gminie Rybno?",
    "Ile kosztuje podatek od nieruchomości?",
    "Jak zapisać dziecko do przedszkola?",
    # Śmieci — z odmianą miejscowości (przypadek ze zrzutu)
    "kiedy wywóz śmieci w hartowcu",
    "Kiedy wywóz śmieci w Rybnie?",
    "harmonogram śmieci dla Żabin",
    "kiedy zabierają plastik w Koszelewkach",
    "wywóz śmieci Nowa Wieś",
    # Organizator — kino, lekarze, apteki
    "Co gra dziś w kinie?",
    "Kiedy przyjmuje lekarz POZ?",
    "Która apteka dziś dyżuruje?",
    # Wiadomości lokalne
    "Co nowego w gminie Rybno?",
    "Co się wydarzyło w Działdowie w tym tygodniu?",
    "Czy są jakieś oferty pracy w okolicy?",
    "Jakie inwestycje planuje gmina?",
    # Urzędnik — dokumenty
    "Jakie są najnowsze uchwały rady gminy?",
    "Czy są aktualne przetargi?",
    "Co mówi BIP o budowie dróg?",
    # GUS
    "Ile mieszkańców ma gmina Rybno?",
    "Jakie jest bezrobocie w powiecie działdowskim?",
    "Jak zmienia się liczba ludności w gminie?",
    # Przewodnik
    "Co robić w weekend w okolicy Rybna?",
    "Gdzie można zjeść obiad w Rybnie?",
    "Jaka będzie pogoda jutro?",
    "Gdzie można popływać w okolicy?",
    # Strażnik
    "Czy są jakieś awarie prądu?",
    "Czy są utrudnienia na drogach?",
    "Gdzie zgłosić uszkodzoną latarnię?",
]

# Wzorce odmowy/ślepego zaułka — odpowiedź nieprzydatna dla mieszkańca
REFUSAL_PATTERNS = [
    r"nie znalaz\w+",
    r"nie posiadam informacji",
    r"nie mam (?:aktualnych |dostępnych )?(?:informacji|danych)(?! .*(?:ale|jednak|natomiast))",
    r"niestety,? nie",
    r"brak (?:informacji|danych) (?:w bazie|na ten temat)\.?\s*$",
    r"proszę sprawdzić lokalne źródła",
    r"skontaktować się z urzędem.{0,40}$",
]


def is_refusal(answer: str) -> bool:
    low = answer.lower()
    return any(re.search(p, low) for p in REFUSAL_PATTERNS)


async def main():
    # Rejestracja agentów (poza FastAPI startup)
    if not orchestrator.agents:
        for cls in (RedaktorAgent, UrzednikAgent, GUSAnalitykAgent,
                    PrzewodnikAgent, StraznikAgent, OrganizatorAgent):
            orchestrator.register_agent(cls())

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results = []
    start = datetime.utcnow()

    for i, pytanie in enumerate(PYTANIA, 1):
        async with async_session() as session:
            try:
                res = await orchestrator.handle(
                    session=session, user_message=pytanie, stream=False
                )
                answer = res.get("answer", "")
                agent = res.get("agent_name", "?")
                refusal = is_refusal(answer)
                results.append((pytanie, agent, refusal, answer))
                mark = "ODMOWA" if refusal else "OK    "
                print(f"[{i:2}/{len(PYTANIA)}] {mark} ({agent:12}) {pytanie}")
                if refusal:
                    print(f"         → {answer[:160]}")
            except Exception as e:
                results.append((pytanie, "ERROR", True, str(e)))
                print(f"[{i:2}/{len(PYTANIA)}] ERROR  {pytanie}: {e}")

    await engine.dispose()

    refusals = sum(1 for _, _, r, _ in results if r)
    elapsed = (datetime.utcnow() - start).total_seconds()
    print("\n" + "=" * 60)
    print(f"WYNIK: {len(results) - refusals}/{len(results)} przydatnych odpowiedzi")
    print(f"Wskaźnik odmów: {100 * refusals / len(results):.0f}% ({refusals}/{len(results)})")
    print(f"Czas: {elapsed:.0f}s")
    if refusals:
        print("\nODMOWY:")
        for pytanie, agent, r, _ in results:
            if r:
                print(f"  - ({agent}) {pytanie}")


if __name__ == "__main__":
    asyncio.run(main())
