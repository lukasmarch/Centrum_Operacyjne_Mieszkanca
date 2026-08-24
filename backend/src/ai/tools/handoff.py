"""
`przekaz_dalej` — rezygnacja jako sygnał, nie jako zdanie (etap 7, 24.08.2026)

**Skąd to się wzięło.** Pytanie „czy jesteś w stanie sprawdzić kondycję Rybna,
podsumować mocne i słabe strony, masz informacje bieżące i historyczne" trafiło
do Redaktora i dostało odpowiedź:

    „Nie mam możliwości przeszukiwania historycznych danych ani analizy
     kondycji gminy Rybno w kontekście mocnych i słabych stron."

Redaktor ma dwa narzędzia i blok „TWOJE NARZĘDZIA", który kończy się instrukcją
„powiedz WPROST, czego nie masz. Nie udawaj, że sprawdziłeś" — więc wykonał ją
co do joty. Dane BYŁY: szeregi GUS to dosłownie „historyczne", 430 aktów
w rejestrze opisuje budżet i inwestycje, `latest_local_news` ma bieżące.
Odmowa padła nad pełną bazą, bo router wybiera JEDNEGO agenta, raz, zanim
zobaczy jakiekolwiek dane — i nie da się tego cofnąć.

**Dlaczego narzędziem, a nie wykrywaniem odmowy w tekście.** Kusi, żeby
przepuścić gotową odpowiedź przez klasyfikator „czy to odmowa". Trzy powody
przeciw:

1. wyrzuciliśmy sześć heurystyk na słowach kluczowych (`INTENT_KEYWORDS`,
   `_GENERIC_QUESTION`, `_is_place_query`…) i nie wracamy po siódmą — tym razem
   na własnym tekście, gdzie „nie mam danych o wywozie w Płośnicy, ale mam
   w Rybnie" jest odpowiedzią, a nie odmową;
2. sygnał strukturalny wchodzi do `agent_tool_calls`. Do dziś klasa porażki
   „agent poddał się, nie zawoławszy NICZEGO" była dla pomiaru niewidzialna —
   wiersz telemetrii powstaje w `_call_tool`, a tu nie było żadnego wywołania.
   Od teraz rezygnacja jest wywołaniem i widać ją w raporcie;
3. orkiestrator dostaje `czego_brakuje` i `sugerowany_agent` wprost od modelu,
   który właśnie czytał pytanie — zamiast zgadywać kierunek z prozy.

**Kiedy wolno.** Dopiero gdy własne narzędzie wróciło puste ALBO gdy dziedzina
jawnie leży poza zasięgiem (pytanie o szereg GUS u Organizatora). Nigdy zamiast
sprawdzenia — inaczej proste pytanie kosztuje dwa razy tyle bez żadnego zysku.
Regułę niesie prompt, a nadużycia widać w telemetrii od pierwszego dnia.

⚠️ To narzędzie NIE zmienia agenta samo z siebie. Ono tylko mówi „nie ja" —
decyzję o tym, kto przejmuje pytanie, podejmuje `Orchestrator.run()`, bo tylko
on wie, ilu przeskoków już użyliśmy i kto był po drodze.
"""
from typing import Optional

from src.ai.tools import Tool, ToolContext, ToolResult, register

# Cel przekazania musi być nazwą agenta z rejestru. Lista jest tu jawna, a nie
# czytana z `orchestrator.agents`, bo trafia do JSON Schema — model ma widzieć
# dopuszczalne wartości w momencie wyboru, a nie dowiadywać się po fakcie, że
# wymyślił nieistniejącego agenta. Rozjazd z rejestrem łapie
# `scripts/test_agent_tools.py`.
HANDOFF_TARGETS = (
    "redaktor",
    "urzednik",
    "gus_analityk",
    "przewodnik",
    "straznik",
    "organizator",
    "koordynator",
)


async def przekaz_dalej(
    ctx: ToolContext,
    czego_brakuje: str,
    sugerowany_agent: Optional[str] = None,
) -> ToolResult:
    """Oddaje pytanie orkiestratorowi wraz z powodem i kierunkiem."""
    # Nazwy NIE sprawdzamy wobec `HANDOFF_TARGETS`. Ta lista jest podpowiedzią
    # dla modelu (idzie do `enum` w schemacie), a nie rejestrem prawdy —
    # prawdziwy rejestr agentów zna wyłącznie `Orchestrator._next_agent` i to
    # on odrzuca cel, którego nie ma. Druga walidacja tutaj wyglądałaby na
    # ostrożność, a robiłaby coś przeciwnego: nowy agent, którego ktoś zapomniał
    # dopisać do tej stałej, byłby po cichu wycinany z kierunków, mimo że
    # istnieje i działa.
    target = (sugerowany_agent or "").strip().lower() or None
    reason = (czego_brakuje or "").strip() or "pytanie poza zakresem tego agenta"

    return ToolResult(
        content={
            "przekazano": True,
            "powod": reason,
            "do": target or "(wybierze orkiestrator)",
        },
        handoff={"to": target, "reason": reason},
        summary=f"przekazuję dalej: {reason[:60]}",
    )


register(Tool(
    name="przekaz_dalej",
    description=(
        "Przekaż pytanie innemu agentowi, gdy NIE MASZ narzędzia, żeby na nie "
        "odpowiedzieć. Użyj tego ZAMIAST pisać, że czegoś nie potrafisz "
        "sprawdzić — inny agent ma te dane i mieszkaniec dostanie odpowiedź. "
        "Wywołaj dopiero wtedy, gdy twoje własne narzędzie wróciło puste albo "
        "gdy pytanie oczywiście dotyczy nie twojej dziedziny. Gdy pytanie "
        "wymaga KILKU dziedzin naraz (np. dane liczbowe + dokumenty + bieżące "
        "wiadomości), wskaż agenta 'koordynator'. Nie pisz przy tym żadnego "
        "tekstu — sam wywołaj narzędzie."
    ),
    short="przekaż pytanie innemu agentowi, gdy brakuje ci narzędzi",
    parameters={
        "type": "object",
        "properties": {
            "czego_brakuje": {
                "type": "string",
                "description": (
                    "Czego konkretnie nie masz, po polsku, jednym zdaniem — "
                    "np. „szeregów GUS o demografii” albo „harmonogramu wywozu”. "
                    "To zdanie zobaczy następny agent."
                ),
            },
            "sugerowany_agent": {
                "type": "string",
                "enum": list(HANDOFF_TARGETS),
                "description": (
                    "Kto powinien to przejąć: redaktor (bieżące wiadomości), "
                    "urzednik (uchwały, BIP, procedury), gus_analityk "
                    "(statystyki i szeregi czasowe), przewodnik (miejsca, "
                    "wydarzenia, pogoda), straznik (awarie, zgłoszenia), "
                    "organizator (odpady, kino, przychodnia, apteka, godziny "
                    "pracy urzędu i GOPS), koordynator (pytanie wymaga kilku "
                    "dziedzin naraz). Pomiń, jeśli nie wiesz."
                ),
            },
        },
        "required": ["czego_brakuje"],
    },
    fn=przekaz_dalej,
    status_message="Przekazuję pytanie dalej…",
))
