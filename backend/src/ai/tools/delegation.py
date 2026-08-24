"""
`zapytaj_*` — agent specjalistyczny jako narzędzie koordynatora (etap 7)

**Dlaczego agent, a nie jego narzędzia.** Kusi, żeby dać koordynatorowi po
prostu wszystkie 17 narzędzi naraz. Trzy powody przeciw:

1. definicje wchodzą do KAŻDEJ rundy (~80 tokenów sztuka) — 17 narzędzi to
   ~1,4 kB przy każdym obrocie pętli, czyli tyle co cała karta gminy;
2. przepadłaby wiedza, która siedzi w promptach specjalistów, nie w narzędziach:
   okna czasowe Strażnika, zakaz „nie mam wiadomości" u Redaktora przy niepustym
   feedzie, obsługa numerów uchwał u Urzędnika. To wnioski z konkretnych awarii
   (7.08, 9.08, 24.08) i nie da się ich przenieść do opisu narzędzia;
3. GUS-Analityk ma własny `respond()` z wykresami — jako zbiór narzędzi
   nie istnieje w ogóle.

Delegacja zachowuje specjalistę w całości: pytanie idzie do niego z jego
promptem, jego narzędziami i jego pętlą, a wraca gotowa odpowiedź plus źródła
i wykresy.

**Głębokość jeden — twardo.** Koordynatora nie ma na liście celów delegacji,
a delegowany agent dostaje `allow_handoff=False`, więc nie odbije pytania
z powrotem. Bez tych dwóch rzeczy pierwsze niejasne pytanie krąży między
agentami, aż skończą się pieniądze. Sprawdza to `scripts/test_agent_tools.py`.

**Sekwencyjnie, nie równolegle** — z tego samego powodu co zwykłe narzędzia
(`_execute_tool_calls`): `AsyncSession` obsługuje jedną operację naraz, a tu
w grę wchodzi cała pętla narzędziowa agenta, nie pojedyncze zapytanie.
Tu cena jest realna (kilka sekund na delegację, nie milisekundy), ale
równoległość na wspólnej sesji to nie optymalizacja, tylko wyścig.
"""
from src.ai.tools import Tool, ToolContext, ToolResult, register

# Agent → (etykieta w UI, co potrafi). Koordynatora tu NIE MA i to jest
# zabezpieczenie, nie przeoczenie — patrz „Głębokość jeden" w docstringu.
DELEGATES: dict[str, tuple[str, str]] = {
    "redaktor": (
        "Redaktora",
        "bieżące wiadomości lokalne z gminy Rybno i okolic, świeży feed, "
        "wyszukiwarka artykułów",
    ),
    "urzednik": (
        "Urzędnika",
        "uchwały Rady i zarządzenia Wójta (rejestr 2024–2026), skróty obrad, "
        "statut, procedury, podatki, programy dotacyjne, dokumenty BIP",
    ),
    "gus_analityk": (
        "GUS-Analityka",
        "dane liczbowe GUS w SZEREGACH CZASOWYCH: demografia, bezrobocie, "
        "budżet gminy, przedsiębiorczość, mieszkalnictwo, edukacja — "
        "wraz z wykresami i porównaniem do średniej krajowej",
    ),
    "przewodnik": (
        "Przewodnika",
        "miejsca w gminie, kalendarz wydarzeń, prognoza pogody, jakość powietrza",
    ),
    "straznik": (
        "Strażnika",
        "awarie i ostrzeżenia (prąd, woda, pogoda) oraz zgłoszenia mieszkańców",
    ),
    "organizator": (
        "Organizatora",
        "harmonogram wywozu odpadów, repertuar kina, godziny przychodni, "
        "dyżury aptek, godziny pracy Urzędu Gminy i GOPS",
    ),
}


def _make_delegate(agent_name: str):
    """Buduje funkcję narzędzia dla jednego agenta."""

    async def delegate(ctx: ToolContext, pytanie: str) -> ToolResult:
        # Import leniwy: `orchestrator` importuje `base_agent`, a ten importuje
        # ten pakiet. Na poziomie modułu byłby cykl.
        from src.ai.agents.orchestrator import orchestrator

        agent = orchestrator.agents.get(agent_name)
        if agent is None:
            return ToolResult(
                content={"blad": f"Agent '{agent_name}' nie jest zarejestrowany."},
                error="unknown_agent",
                summary=f"{agent_name} niedostępny",
            )

        question = (pytanie or "").strip()
        if not question:
            return ToolResult(
                content={"blad": "Puste pytanie do agenta."},
                error="bad_arguments",
                summary="puste pytanie",
            )

        # Historia rozmowy NIE jest przekazywana. Specjalista ma dostać jedno,
        # samodzielne pytanie ułożone przez koordynatora — z historią zaczyna
        # odpowiadać na pierwotne pytanie mieszkańca zamiast na zadany mu
        # wycinek, a to jest dokładnie ta odpowiedź, którą już mamy.
        result = await agent.respond(
            session=ctx.session,
            user_message=question,
            conversation_history=None,
            stream=False,
            user=ctx.user,
            allow_handoff=False,
        )

        answer = (result.get("answer") or "").strip()
        label = DELEGATES[agent_name][0]
        if not answer:
            return ToolResult(
                content={"agent": agent_name, "odpowiedz": "", "pusty_wynik": True},
                empty=True,
                summary=f"{label} nie ustalił odpowiedzi",
            )

        return ToolResult(
            content={"agent": agent_name, "pytanie": question, "odpowiedz": answer},
            # Źródła i wykresy wędrują OBOK modelu, prosto do interfejsu —
            # koordynator nie musi przepisywać adresów ani serii danych, żeby
            # mieszkaniec je zobaczył. Przepisywanie było jedynym powodem,
            # dla którego mógłby je przekręcić.
            sources=result.get("sources") or [],
            charts=result.get("chart_data") or [],
            summary=f"{label}: {len(answer)} zn. odpowiedzi",
        )

    return delegate


for _name, (_label, _zakres) in DELEGATES.items():
    register(Tool(
        name=f"zapytaj_{_name}",
        description=(
            f"Zadaj pytanie agentowi {_label}. Jego zakres: {_zakres}. "
            "Zadaj JEDNO konkretne pytanie dotyczące wyłącznie jego dziedziny — "
            "nie przekazuj całego pytania mieszkańca, tylko tę część, na którą "
            "ten agent potrafi odpowiedzieć."
        ),
        short=f"zapytaj {_label} — {_zakres.split(':')[0][:60]}",
        parameters={
            "type": "object",
            "properties": {
                "pytanie": {
                    "type": "string",
                    "description": (
                        "Samodzielne pytanie po polsku, zrozumiałe bez kontekstu "
                        "rozmowy — agent nie widzi ani wcześniejszych wiadomości, "
                        "ani pytania mieszkańca."
                    ),
                },
            },
            "required": ["pytanie"],
        },
        fn=_make_delegate(_name),
        status_message=f"Pytam {_label}…",
        # Delegacja to CAŁA pętla innego agenta: jego wywołania modelu (Urzędnik
        # i GUS chodzą na gpt-4o) plus jego własne narzędzia. Wspólne 15 s,
        # skalibrowane dla zapytania do bazy, ucinało Urzędnika w połowie pracy
        # — koordynator dostawał pustkę i pisał o kondycji gminy bez ani jednego
        # zdania o finansach. Pomiar 24.08: delegacja trwa 6–20 s.
        # 45 s to sufit awaryjny, nie oczekiwany czas.
        timeout_s=45.0,
    ))
