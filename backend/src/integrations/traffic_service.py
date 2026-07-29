import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List, Optional
import json

class RoadStatus(BaseModel):
    id: str
    name: str
    status: str
    delayMinutes: int
    travelTime: str
    description: Optional[str] = None

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

      MATERIAŁ ŹRÓDŁOWY — zweryfikowane wpisy lokalne z naszego serwisu
      (data publikacji w nawiasie; to są fakty, nie domysły):
{road_context_block}

      Materiał źródłowy ma PIERWSZEŃSTWO przed wynikami wyszukiwania. Jeśli wynika
      z niego, że prace się zakończyły albo dobiegają końca — NIE zgłaszaj utrudnień.
      Jeśli mówi o zamknięciu drogi w konkretnym terminie — sprawdź, czy {date_str}
      mieści się w tym terminie, i dopiero wtedy zgłoś utrudnienie.

      Następnie UZUPEŁNIJ obraz wyszukiwaniem w Google — osobno dla każdej trasy
      (np. „utrudnienia DW538 Rybno Działdowo lipiec 2026", „wypadek droga wojewódzka
      541 Lubawa"). Nie odpowiadaj z pamięci: Twoja wiedza jest nieaktualna,
      a mieszkaniec podejmuje decyzję o wyjeździe na podstawie tych danych.

      ZAKAZ ZMYŚLANIA DAT. W NOTE wolno podać wyłącznie datę, która pada
      w materiale źródłowym lub w znalezionym artykule. Nie podstawiaj dzisiejszej
      daty ani „ostatnich dni". Jeśli nie znasz daty zdarzenia — nie podawaj żadnej.

      Sprawdź AKTUALNE warunki drogowe i czasy przejazdu dla tras:
      1. Rybno -> Działdowo (DW538)
      2. Rybno -> Lubawa (DW538/DW541)
      3. Rybno -> Iława (przez Hartowiec)
      4. Rybno -> Olsztyn (najszybsza aktualna trasa)

      Zasady analizy:
      - Podaj AKTUALNY CZAS PRZEJAZDU (TIME) jako liczbę minut, np. "25 min".
      - Jeśli brak aktualnych danych o ruchu dla trasy, użyj typowego czasu przejazdu:
        Rybno-Działdowo: 25 min, Rybno-Lubawa: 40 min, Rybno-Iława: 50 min, Rybno-Olsztyn: 90 min
      - Opóźnienie (DELAY) to różnica między czasem aktualnym a optymalnym, domyślnie 0 min.
      - W opisie (NOTE) opisz AKTUALNĄ sytuację. Jeśli brak utrudnień: "Ruch płynny, brak zgłoszonych utrudnień."
      - Opis musi być jednym, treściwym zdaniem.

      KIEDY WOLNO DAĆ STATUS INNY NIŻ "Płynnie" — wszystkie trzy warunki naraz:
      1. RODZAJ DROGI. Utrudnienie musi dotyczyć drogi, którą faktycznie się jedzie tą trasą
         (droga wojewódzka, krajowa lub powiatowa na przebiegu trasy — np. DW538, DW541).
         ZIGNORUJ całkowicie: drogi gminne, dojazdowe, wewnętrzne, drogi transportu rolnego,
         drogi gruntowe, chodniki, parkingi, remonty w obrębie posesji. Przebudowa 300-metrowej
         drogi polnej we wsi NIE jest utrudnieniem na trasie przelotowej.
      2. CZAS. Utrudnienie musi obowiązywać DZIŚ ({date_str}). Podpisanie umowy, przetarg,
         plan inwestycyjny, "zaplanowano na 2026 rok" czy zapowiedź remontu bez potwierdzonej
         daty rozpoczęcia to NIE jest utrudnienie. Jeśli źródło jest starsze niż 14 dni i nie
         potwierdza, że prace nadal trwają — daj "Płynnie".
      3. MIEJSCE. Zdarzenie musi leżeć na trasie z Rybna w powiecie działdowskim
         (woj. warmińsko-mazurskie) do wskazanego celu. W Polsce jest kilka miejscowości Rybno —
         ODRZUĆ wszystko, co dotyczy Rybna Wielkiego (gm. Kiszkowo, pow. gnieźnieński),
         Rybna k. Sochaczewa i innych. Sprawdź powiat, zanim użyjesz źródła.

      Jeśli którykolwiek warunek nie jest spełniony — STATUS: Płynnie, DELAY: 0 min.
      Nie zgaduj i nie wnioskuj "na wszelki wypadek": lepiej napisać, że jest płynnie,
      niż ostrzec mieszkańca przed utrudnieniem, którego nie ma.

      Gdy podajesz utrudnienie, w NOTE MUSI paść data zdarzenia lub źródła,
      np. "Od 8 lipca zamknięty przejazd w Hartowcu, objazd przez Kostkowo."

      Format odpowiedzi (każda trasa w osobnej linii, BEZ Markdown, BEZ pogrubień):
      ROUTE: Rybno-Działdowo | TIME: 25 min | STATUS: Płynnie | DELAY: 0 min | NOTE: Ruch płynny, brak zgłoszonych utrudnień.
      ROUTE: Rybno-Lubawa | TIME: 40 min | STATUS: Płynnie | DELAY: 0 min | NOTE: Ruch płynny, brak zgłoszonych utrudnień.

      Status values: Płynnie, Utrudnienia, Korki
      WAŻNE: TIME musi być zawsze liczbą minut (np. "25 min"), nigdy słowem "Brak". Odpowiedz TYLKO liniami ROUTE, bez dodatkowego tekstu.
    """

        try:
            print("Fetching fresh traffic data from Gemini...")
            # 503 UNAVAILABLE ("high demand") potrafi trafić się kilka razy z rzędu.
            # Bez ponawiania pojedynczy skok obciążenia zamieniał cache w atrapę na 4 h.
            response = None
            last_error = None
            for attempt in range(1, self.MAX_ATTEMPTS + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                            response_modalities=["TEXT"],
                        )
                    )
                    break
                except Exception as api_error:
                    last_error = api_error
                    # 429 (brak limitu) nie minie przez ponowienie — przerwij od razu
                    if "RESOURCE_EXHAUSTED" in str(api_error) or "429" in str(api_error):
                        raise
                    if attempt == self.MAX_ATTEMPTS:
                        raise
                    print(f"Gemini attempt {attempt}/{self.MAX_ATTEMPTS} failed ({api_error}); retrying in {self.RETRY_DELAY_SECONDS}s")
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

    # Domyślne czasy przejazdu gdy Gemini nie ma danych
    _DEFAULT_TRAVEL_TIMES = {
        "działdowo": "25 min",
        "lubawa": "40 min",
        "iława": "50 min",
        "olsztyn": "90 min",
    }

    def _parse_response(self, text: str) -> List[RoadStatus]:
        roads = []
        import re

        clean = re.sub(r'\*\*(\w+:)\*\*', r'\1', text)

        # Try bracket format first: [ROUTE: ... | TIME: ... | STATUS: ... | DELAY: ... | NOTE: ...]
        pattern = r"\[ROUTE: (.*?) \| TIME: (.*?) \| STATUS: (.*?) \| DELAY: (.*?) \| NOTE: (.*?)\]"
        matches = list(re.finditer(pattern, clean))

        # Fallback: plain pipe format without brackets
        if not matches:
            pattern = r"ROUTE:\s*(.*?)\s*\|\s*TIME:\s*(.*?)\s*\|\s*STATUS:\s*(.*?)\s*\|\s*DELAY:\s*(.*?)\s*\|\s*NOTE:\s*(.*?)(?:\n|$)"
            matches = list(re.finditer(pattern, clean))

        for i, match in enumerate(matches):
            name = match.group(1).strip()
            travel_time = match.group(2).strip()
            status_text = match.group(3).strip()
            delay_text = match.group(4).strip()
            note = match.group(5).strip()

            # Gdy Gemini nie zwraca cyfr w TIME — użyj domyślnego czasu dla danej trasy
            if not any(c.isdigit() for c in travel_time):
                name_lower = name.lower()
                for key, default_time in self._DEFAULT_TRAVEL_TIMES.items():
                    if key in name_lower:
                        travel_time = default_time
                        break
                else:
                    travel_time = "—"

            status = "Płynnie"
            s_lower = status_text.lower()
            if 'utrud' in s_lower:
                status = 'Utrudnienia'
            elif 'kork' in s_lower:
                status = 'Korki'

            try:
                delay = int(''.join(filter(str.isdigit, delay_text)))
            except Exception:
                delay = 0

            roads.append(RoadStatus(
                id=str(i),
                name=name,
                status=status,
                delayMinutes=delay,
                travelTime=travel_time,
                description=note if note and len(note) > 5 else None
            ))

        return roads

    def _get_fallback_data(self) -> TrafficData:
        return TrafficData(
            roads=[
                RoadStatus(id='1', name='Rybno -> Działdowo', status='Płynnie', delayMinutes=0, travelTime='25 min', description='Brak aktualnych danych. Typowy czas przejazdu DW538.'),
                RoadStatus(id='2', name='Rybno -> Lubawa', status='Płynnie', delayMinutes=0, travelTime='40 min', description='Brak aktualnych danych. Typowy czas przejazdu DW538/DW541.'),
                RoadStatus(id='3', name='Rybno -> Iława', status='Płynnie', delayMinutes=0, travelTime='50 min', description='Brak aktualnych danych. Typowy czas przejazdu przez Hartowiec.'),
                RoadStatus(id='4', name='Rybno -> Olsztyn', status='Płynnie', delayMinutes=0, travelTime='2h 30 min', description='Brak aktualnych danych. Typowy czas przejazdu przez Szczytno.')
            ],
            sources=[],
            is_fallback=True
        )
