import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json

from src.services.road_context import note_is_outdated

class RoadStatus(BaseModel):
    id: str
    name: str
    status: str
    delayMinutes: int
    travelTime: str
    description: Optional[str] = None
    # Skąd model to wie: "M3" (pozycja materiału z feedu), "WWW" (sam Google), None.
    # Po tym `road_reports` liczy wiarygodność — nie po opisie modelu.
    ref: Optional[str] = None

class GroundingSource(BaseModel):
    title: str
    uri: str

class TrafficData(BaseModel):
    roads: List[RoadStatus]
    sources: List[GroundingSource]
    # True = dane zastępcze (typowe czasy przejazdu), NIE odpowiedź modelu.
    # Bez tego job zapisywał atrapę jako dane i logował sukces — awaria Gemini
    # została niezauważona od 07.07 do 29.07.2026.
    is_fallback: bool = False

class TrafficService:
    _cache = None
    _last_update = None
    CACHE_DURATION_SECONDS = 7200  # 2 hours
    MAX_ATTEMPTS = 3           # ponowienia przy 503 UNAVAILABLE
    RETRY_DELAY_SECONDS = 20

    def __init__(self):
        from src.config import settings
        api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.fallback_model = settings.GEMINI_FALLBACK_MODEL
        if not api_key:
            # Fallback to GOOGLE_API_KEY from settings or env if needed
            api_key = os.environ.get("GOOGLE_API_KEY") 
        
        if not api_key:
            print("Warning: GEMINI_API_KEY not set")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    async def get_traffic_data(self, road_context: Optional[str] = None) -> "TrafficData":
        import time
        from datetime import datetime

        # Check cache
        if TrafficService._cache and TrafficService._last_update:
            if time.time() - TrafficService._last_update < TrafficService.CACHE_DURATION_SECONDS:
                print("Returning cached traffic data")
                return TrafficService._cache

        if not self.client:
            return self._get_fallback_data()

        now = datetime.now()
        date_str = now.strftime("%d.%m.%Y %H:%M")
        road_context_block = road_context or "      (brak lokalnych wpisów o drogach z ostatnich tygodni)"

        prompt = f"""
      Jesteś dyspozytorem ruchu dla regionu Rybno (powiat działdowski, Warmia i Mazury).
      Aktualna data i godzina: {date_str}.
      Twoim centrum jest miejscowość RYBNO.

      MATERIAŁ ŹRÓDŁOWY — wpisy lokalne z naszego serwisu, każdy z numerem [M1], [M2]…
      (data publikacji i wiek w nawiasie):
{road_context_block}

      Twoje zadanie: wskazać utrudnienia na czterech trasach. NIE oceniasz, czy
      informacja jest pewna — wiarygodność liczy nasz system na podstawie źródła
      i wieku, a niepewne trafiają do redakcji. Ty masz poprawnie wskazać ŹRÓDŁO.

      Materiał źródłowy ma PIERWSZEŃSTWO przed wynikami wyszukiwania. Jeśli wynika
      z niego, że prace się zakończyły — NIE zgłaszaj utrudnień.

      Następnie poszukaj w Google utrudnień, których w materiale nie ma — osobno dla
      każdej trasy (np. „utrudnienia DW538 Rybno”, „zamknięcie drogi Lubawa”).
      Bierz WYŁĄCZNIE artykuły i komunikaty z ostatnich 14 dni; listy utrudnień
      zarządców dróg zawierają wpisy sprzed lat — sprawdź termin każdego wpisu.

      ZAKAZ ZMYŚLANIA DAT. W NOTE wolno podać wyłącznie datę, która pada
      w materiale źródłowym lub w znalezionym artykule.

      Trasy:
      1. Rybno -> Działdowo (DW538)
      2. Rybno -> Lubawa (DW538/DW541)
      3. Rybno -> Iława (przez Hartowiec)
      4. Rybno -> Olsztyn

      KIEDY WOLNO DAĆ STATUS "Utrudnienia" — wszystkie warunki naraz:
      1. RODZAJ DROGI. Utrudnienie na drodze, którą faktycznie się jedzie tą trasą
         (wojewódzka, krajowa lub powiatowa na przebiegu trasy). ZIGNORUJ drogi gminne,
         dojazdowe, wewnętrzne, transportu rolnego, gruntowe, chodniki, parkingi.
      2. CZAS. Utrudnienie obowiązuje DZIŚ ({date_str}). Umowa, przetarg, plan
         inwestycyjny, zapowiedź bez daty rozpoczęcia — to NIE jest utrudnienie.
      3. MIEJSCE. Na trasie z Rybna w powiecie działdowskim (woj. warmińsko-mazurskie).
         W Polsce jest kilka miejscowości Rybno — ODRZUĆ Rybno Wielkie (gm. Kiszkowo),
         Rybno k. Sochaczewa i inne.
      4. KONKRETNY ODCINEK. Nazwana miejscowość, skrzyżowanie lub numer drogi.
         Komunikaty wojewódzkie, krajowe, pogodowe, ćwiczenia wojskowe — NIE.
      5. JEDNO ZDARZENIE = JEDNA TRASA. Jeśli to samo utrudnienie pasuje do więcej niż
         jednej trasy, nie wiesz, na której leży — wpisz je przy JEDNEJ, najbardziej
         prawdopodobnej, albo przy żadnej.
      6. WIEK. Zdarzenie chwilowe (konar, kolizja, zablokowana droga) — tylko z etykietą "DZIŚ".

      Jeśli którykolwiek warunek nie jest spełniony — STATUS: Płynnie.

      REF — skąd wiesz:
      - numer pozycji materiału, np. REF: M2 (gdy utrudnienie opiera się na materiale),
      - REF: WWW (gdy wyłącznie na wyniku z Google; wtedy w NOTE podaj nazwę serwisu i datę artykułu),
      - REF: - (przy STATUS: Płynnie).

      NOTE: jedno treściwe zdanie. Przy utrudnieniu MUSI paść miejsce i data zdarzenia
      lub źródła, np. "Od 8 lipca zamknięty przejazd w Hartowcu, objazd przez Kostkowo."
      Przy braku utrudnień: "Ruch płynny, brak zgłoszonych utrudnień."

      Format odpowiedzi (każda trasa w osobnej linii, BEZ Markdown):
      ROUTE: Rybno-Działdowo | STATUS: Płynnie | REF: - | NOTE: Ruch płynny, brak zgłoszonych utrudnień.
      ROUTE: Rybno-Lubawa | STATUS: Utrudnienia | REF: M1 | NOTE: Od 3 listopada ruch wahadłowy na DW538 w Tuczkach.

      Status values: Płynnie, Utrudnienia
      Odpowiedz TYLKO liniami ROUTE, bez dodatkowego tekstu.
    """

        try:
            print("Fetching fresh traffic data from Gemini...")
            # 503 UNAVAILABLE ("high demand") potrafi trafić się kilka razy z rzędu.
            # Bez ponawiania pojedynczy skok obciążenia zamieniał cache w atrapę na 4 h.
            # Po ostatniej próbie głównego modelu — jedna próba zapasowego. 503 to
            # przeciążenie KONKRETNEGO modelu: 27.10.2026 trzy przebiegi z rzędu
            # po trzy próby nie dostały odpowiedzi, a pasek stał na odczycie
            # sprzed 14 godzin. Kredyty i limity (402/429) są wspólne dla konta,
            # więc przy nich zapasowy model nic nie da — nadal przerywamy od razu.
            plan = [self.model] * self.MAX_ATTEMPTS
            if self.fallback_model and self.fallback_model != self.model:
                plan.append(self.fallback_model)
            response = None
            last_error = None
            for attempt, model in enumerate(plan, start=1):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                            response_modalities=["TEXT"],
                        )
                    )
                    if model != self.model:
                        print(f"Gemini: odpowiedź z modelu zapasowego {model}")
                    break
                except Exception as api_error:
                    last_error = api_error
                    # Wyczerpany limit albo budżet nie minie przez ponowienie —
                    # przerwij od razu. 402 („prepayment credits are depleted")
                    # dołożone 24.09.2026: tego dnia widget ruchu nie odświeżył
                    # się ANI RAZU w sześciu przebiegach, a log pokazywał wyłącznie
                    # 503 „high demand" z trzema próbami co 20 s. Sprawdzenie klucza
                    # wprost zwróciło 402 dla każdego modelu — kredyty konta Gemini
                    # były wyczerpane. Trzy próby i minuta czekania nic tu nie dają.
                    if any(
                        marker in str(api_error)
                        for marker in ("RESOURCE_EXHAUSTED", "429", "402", "credits are depleted")
                    ):
                        raise
                    if attempt == len(plan):
                        raise
                    next_model = plan[attempt]
                    print(f"Gemini attempt {attempt}/{len(plan)} ({model}) failed ({api_error}); "
                          f"retrying with {next_model} in {self.RETRY_DELAY_SECONDS}s")
                    time.sleep(self.RETRY_DELAY_SECONDS)

            if response is None:
                raise last_error or RuntimeError("Gemini: brak odpowiedzi")

            text = response.text or ""

            # Ile zapytań model faktycznie wysłał do Google. Zero = odpowiedź z pamięci
            # modelu, nie z sieci — wtedy "Ruch płynny" nic nie potwierdza.
            grounding = response.candidates[0].grounding_metadata if response.candidates else None
            queries = getattr(grounding, "web_search_queries", None) or []
            if not queries:
                print("WARNING: Gemini nie wykonał żadnego wyszukiwania — dane bez pokrycia w źródłach")
            else:
                print(f"Gemini wyszukał ({len(queries)}): {queries}")

            # Extract grounding metadata
            sources = []
            if response.candidates and response.candidates[0].grounding_metadata and response.candidates[0].grounding_metadata.grounding_chunks:
                for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                    if chunk.web:
                         sources.append(GroundingSource(
                             title=chunk.web.title or "Źródło WWW",
                             uri=chunk.web.uri
                         ))

            roads = self._parse_response(text)
            
            if not roads:
                print(f"WARNING: No roads parsed from Gemini response. Raw text:\n{text}")
                # Don't cache empty results, or cache for short time?
                # For now, return fallback and don't cache this bad result
                return self._get_fallback_data()

            data = TrafficData(roads=roads, sources=sources)
            
            # Update cache only if we have valid data
            if roads:
                TrafficService._cache = data
                TrafficService._last_update = time.time()
            
            return data

        except Exception as e:
            print(f"Error fetching traffic data: {e}")
            # If rate limited, try to return cache even if expired, or fallback
            if TrafficService._cache:
                print("Returning expired cache due to error")
                # Realne dane, ale nie z tego przebiegu — oznacz, żeby job nie zapisał ich
                # ponownie z bieżącym fetched_at i nie udawał świeżego odczytu.
                return TrafficService._cache.model_copy(update={"is_fallback": True})
            return self._get_fallback_data()

    # Bramka miejsca dla utrudnień — ta sama zasada co w alertach push.
    # Prośby w promkcie nie wystarczyły: model ogłosił "Utrudnienia" na WSZYSTKICH
    # czterech trasach na podstawie komunikatu o ćwiczeniach wojskowych "na drogach
    # województwa warmińsko-mazurskiego od 15 czerwca". Ostrzeżenie bez wskazania
    # odcinka nie mówi mieszkańcowi nic, a psuje zaufanie do widgetu.
    # RDZENIE nazw, nie pełne formy: „w Hartowcu" nie zawiera „hartowiec",
    # a odmiana jest w tych komunikatach regułą („w Rybnie", „do Iławy",
    # „między Truszczynami a Dębieniem"). Pisane bez „ł" (patrz `_flat`).
    _ROUTE_PLACES: tuple[str, ...] = (
        # trasy i cele
        "rybn", "dzialdow", "lubaw", "ilaw", "olsztyn", "nidzic", "szczytn",
        # miejscowości na trasach i w gminie
        "hartow", "rumian", "koszelew", "tuczk", "truszczyn", "debien",
        "zabin", "jezew", "dlutow", "fijew", "kostkow", "gralew", "grunwald",
        "wikielec", "samplaw", "pratnic", "naguszew", "swiniarc",
        # oznaczenia dróg
        "538", "541", "1255", "1313", "dk15", "dk 15", "s7",
    )

    @staticmethod
    def _flat(text: str) -> str:
        """Do porównań: małe litery, „ł" na „l" (nie rozkłada się w NFKD)."""
        import unicodedata
        lowered = (text or "").lower().replace("ł", "l")
        return "".join(
            c for c in unicodedata.normalize("NFKD", lowered)
            if not unicodedata.combining(c)
        )

    def _names_place_on_route(self, note: str) -> bool:
        flat = self._flat(note)
        return any(place in flat for place in self._ROUTE_PLACES)

    def _parse_response(self, text: str) -> List[RoadStatus]:
        """
        Linie „ROUTE: … | STATUS: … | REF: … | NOTE: …” — pola czytane po nazwie,
        nie po pozycji: model bywa niekonsekwentny w kolejności, a do 29.10
        odpowiadał jeszcze z TIME i DELAY (minuty usunięte — Google nie zna ruchu).
        """
        import re

        clean = re.sub(r"\*\*(\w+:)\*\*", r"\1", text)
        roads = []
        for line in clean.splitlines():
            line = line.strip().strip("[]")
            if not line.upper().startswith("ROUTE:"):
                continue
            fields = {}
            for part in line.split("|"):
                key, sep, value = part.partition(":")
                if sep:
                    fields[key.strip().upper()] = value.strip()
            name = fields.get("ROUTE", "")
            note = fields.get("NOTE", "")
            status_text = fields.get("STATUS", "")
            ref = (fields.get("REF") or "").upper().replace(" ", "")
            ref = ref if re.fullmatch(r"M\d+|WWW", ref) else None

            status = "Utrudnienia" if re.search(r"utrud|kork", status_text.lower()) else "Płynnie"

            # Utrudnienie musi wskazać KONKRETNE miejsce na trasie. Komunikat
            # o zasięgu wojewódzkim ("na drogach województwa…") przechodził przez
            # wszystkie prośby w prompcie i trafiał na wszystkie cztery trasy naraz.
            if status != "Płynnie" and not self._names_place_on_route(note):
                print(
                    f"WARNING: odrzucam utrudnienie bez miejsca na trasie "
                    f"({name}): {note[:120]}"
                )
                status, note, ref = "Płynnie", "Ruch płynny, brak potwierdzonych utrudnień.", None

            # Termin, który już minął. Wyniki Google nie przechodzą przez bramki
            # `road_context` — 28.10.2026 pasek ogłosił zamknięcie DW538
            # „do 31 grudnia 2025 roku" jako dzisiejsze utrudnienie.
            if status != "Płynnie" and note_is_outdated(note, datetime.utcnow()):
                print(
                    f"WARNING: odrzucam utrudnienie z minionym terminem "
                    f"({name}): {note[:120]}"
                )
                status, note, ref = "Płynnie", "Ruch płynny, brak potwierdzonych utrudnień.", None

            # Utrudnienie bez wskazania źródła traktujemy jak wynik z Google —
            # najniższe zaufanie, najwyżej do redakcji.
            if status != "Płynnie" and ref is None:
                ref = "WWW"

            roads.append(RoadStatus(
                id=str(len(roads)),
                name=name,
                status=status,
                delayMinutes=0,
                travelTime="",
                description=note if note and len(note) > 5 else None,
                ref=ref if status != "Płynnie" else None,
            ))

        return roads

    def _get_fallback_data(self) -> TrafficData:
        return TrafficData(
            roads=[
                RoadStatus(id='1', name='Rybno -> Działdowo', status='Płynnie', delayMinutes=0, travelTime='', description='Brak aktualnych danych.'),
                RoadStatus(id='2', name='Rybno -> Lubawa', status='Płynnie', delayMinutes=0, travelTime='', description='Brak aktualnych danych.'),
                RoadStatus(id='3', name='Rybno -> Iława', status='Płynnie', delayMinutes=0, travelTime='', description='Brak aktualnych danych.'),
                RoadStatus(id='4', name='Rybno -> Olsztyn', status='Płynnie', delayMinutes=0, travelTime='', description='Brak aktualnych danych.')
            ],
            sources=[],
            is_fallback=True
        )
