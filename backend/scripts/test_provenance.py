"""
Sprawdza warstwę pochodzenia — `python -m scripts.test_provenance`.

Etykieta `zrodlo` dokleja się do KAŻDEGO wyniku narzędzia idącego do modelu,
więc jej błąd jest cichy i działa w najgorszą stronę: zdanie z Facebooka
opisane jako urzędowe brzmi dla mieszkańca jak stanowisko gminy. Test pilnuje
trzech rzeczy — że każde narzędzie ma świadomie wybraną warstwę, że etykieta
faktycznie dociera do modelu, i że narzędzia sterujące jej nie dostają.

⚠️ EXPECTED to nie kopia rejestru, tylko lista DECYZJI. Nowe narzędzie zapali
się tutaj na czerwono i o to chodzi: domyślna warstwa `MEDIA` jest bezpieczna,
ale ma być wyborem, a nie skutkiem przeoczenia.
"""
import json
import sys

# Import modułów narzędzi wypełnia TOOL_REGISTRY (rejestracja przy imporcie).
from src.ai.tools import TOOL_REGISTRY  # noqa: F401
from src.ai.tools import alerts, council, daily, delegation, handoff  # noqa: F401
from src.ai.tools import institutions, knowledge, places, weather  # noqa: F401
from src.ai.agents.base_agent import BaseAgent, base_context_messages
from src.ai.tools import ToolResult
from src.services import provenance as prov

failures: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}{f' — {detail}' if detail else ''}")
        failures.append(label)


# Świadoma decyzja dla każdego narzędzia. Delegacje (`zapytaj_*`) powstają
# w pętli, więc sprawdzamy je osobno, wzorcem nazwy.
EXPECTED = {
    "council_sessions": prov.URZEDOWE,
    "search_legal_acts": prov.URZEDOWE,
    "institution_info": prov.URZEDOWE,
    "search_documents": prov.URZEDOWE,
    "current_weather": prov.POMIAR,
    "weather_forecast": prov.POMIAR,
    "air_quality": prov.POMIAR,
    "waste_schedule": prov.POMIAR,
    "clinic_schedule": prov.POMIAR,
    "pharmacy_duty": prov.POMIAR,
    "search_news": prov.MEDIA,
    "latest_local_news": prov.MEDIA,
    "active_alerts": prov.MEDIA,
    "upcoming_events": prov.MEDIA,
    "cinema_repertoire": prov.MEDIA,
    "citizen_reports": prov.MIESZKANCY,
    "local_places": prov.ZEWNETRZNE,
    "przekaz_dalej": prov.STEROWANIE,
}

print("\n== Każde narzędzie ma świadomą warstwę ==")
for name, tool in sorted(TOOL_REGISTRY.items()):
    if name.startswith("zapytaj_"):
        check(tool.provenance == prov.STEROWANIE,
              f"{name} = sterowanie", f"jest {tool.provenance}")
        continue
    expected = EXPECTED.get(name)
    check(expected is not None, f"{name} ma decyzję w teście",
          "nowe narzędzie — dopisz warstwę do EXPECTED")
    if expected is not None:
        check(tool.provenance == expected, f"{name} = {expected}",
              f"jest {tool.provenance}")

print("\n== Warstwy są znane ==")
for name, tool in sorted(TOOL_REGISTRY.items()):
    if tool.provenance not in prov.LAYERS:
        check(False, f"{name} ma nieznaną warstwę", tool.provenance)
check(all(t.provenance in prov.LAYERS for t in TOOL_REGISTRY.values()),
      "wszystkie warstwy z LAYERS (brak literówki)")

print("\n== Etykieta dociera do modelu ==")
call = {"id": "1", "name": "search_legal_acts"}
msg = BaseAgent._tool_message(call, ToolResult(content={"akty": []}))
payload = json.loads(msg["content"])
check("zrodlo" in payload, "wynik narzędzia niesie pole `zrodlo`")
check("urzędowe" in payload.get("zrodlo", ""),
      "search_legal_acts opisane jako urzędowe", payload.get("zrodlo", ""))

msg = BaseAgent._tool_message({"id": "2", "name": "search_news"},
                              ToolResult(content={"wpisy": []}))
check("media lokalne" in json.loads(msg["content"]).get("zrodlo", ""),
      "search_news opisane jako media lokalne")

print("\n== Narzędzie sterujące nie dostaje źródła ==")
msg = BaseAgent._tool_message({"id": "3", "name": "przekaz_dalej"},
                              ToolResult(content={"czego_brakuje": "x"}))
check("zrodlo" not in json.loads(msg["content"]),
      "przekaz_dalej bez etykiety źródła")

print("\n== Pustka zachowuje oba znaczniki ==")
msg = BaseAgent._tool_message({"id": "4", "name": "active_alerts"},
                              ToolResult(content={"awarie": []}, empty=True))
payload = json.loads(msg["content"])
check(payload.get("pusty_wynik") is True and "zrodlo" in payload,
      "pusty wynik ma i `pusty_wynik`, i `zrodlo`")

print("\n== Narzędzie może nadpisać etykietę ==")
msg = BaseAgent._tool_message({"id": "5", "name": "search_documents"},
                              ToolResult(content={"zrodlo": "własna", "x": 1}))
check(json.loads(msg["content"])["zrodlo"] == "własna",
      "pole ustawione przez narzędzie wygrywa z domyślną warstwą")

print("\n== Reguła precedencji trafia do każdego agenta ==")
blob = " ".join(m["content"] for m in base_context_messages())
check("POCHODZENIE INFORMACJI" in blob, "reguła jest w kontekście bazowym")
check("zgadywaniem" in blob, "reguła zakazuje faktów z pamięci modelu")
check("obie wersje" in blob, "reguła każe pokazać rozbieżność, nie zamilczeć")

print("\n== Nieznana warstwa nie wygląda na pewną ==")
check(prov.label("cokolwiek") == prov.label(prov.MEDIA),
      "nieznana warstwa dostaje etykietę MEDIA")
check(prov.label(prov.STEROWANIE) is None, "sterowanie nie ma etykiety")

print()
if failures:
    print(f"BŁĘDY: {len(failures)}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("Wszystko OK")
