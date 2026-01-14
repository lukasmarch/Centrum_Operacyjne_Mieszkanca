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

class TrafficService:
    _cache = None
    _last_update = None
    CACHE_DURATION_SECONDS = 7200  # 2 hours

    def __init__(self):
        from src.config import settings
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            # Fallback to GOOGLE_API_KEY from settings or env if needed
            api_key = os.environ.get("GOOGLE_API_KEY") 
        
        if not api_key:
            print("Warning: GEMINI_API_KEY not set")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    async def get_traffic_data(self) -> "TrafficData":
        import time
        
        # Check cache
        if TrafficService._cache and TrafficService._last_update:
            if time.time() - TrafficService._last_update < TrafficService.CACHE_DURATION_SECONDS:
                print("Returning cached traffic data")
                return TrafficService._cache

        if not self.client:
            return self._get_fallback_data()

        prompt = """
      Jesteś dyspozytorem ruchu dla regionu Rybno (powiat działdowski). 
      Twoim centrum jest miejscowość RYBNO. Sprawdź AKTUALNE (real-time) warunki drogowe i czasy przejazdu dla tras:
      1. Rybno -> Działdowo (DW538)
      2. Rybno -> Lubawa (DW538/DW541)
      3. Rybno -> Iława (przez Hartowiec)
      4. Rybno -> Olsztyn (najszybsza aktualna trasa)
      
      Zasady analizy:
      - Podaj AKTUALNY CZAS PRZEJAZDU (TravelTime) w minutach.
      - Opóźnienie (Delay) to różnica między czasem aktualnym a optymalnym.
      - W opisie ('NOTE') bądź ekstremalnie precyzyjny: jeśli jest zima, sprawdź czy przyczyną jest śliska nawierzchnia, błoto pośniegowe czy praca pługów. Jeśli to korek w małym mieście, określ czy to zator przy przejeździe kolejowym czy wzmożony ruch lokalny.
      - Opis musi być jednym, treściwym zdaniem, które wyjaśnia "dlaczego" (np. "Błoto pośniegowe na podjazdach pod wzniesienia spowalnia ruch ciężarowy").

      Format odpowiedzi:
      [ROUTE: Skąd-Dokąd | TIME: X min | STATUS: Status | DELAY: X min | NOTE: Opis przyczyny]
      
      Status values: Płynnie, Utrudnienia, Korki
    """

        try:
            print("Fetching fresh traffic data from Gemini...")
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    response_modalities=["TEXT"],
                )
            )

            text = response.text or ""
            
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
                return TrafficService._cache
            return self._get_fallback_data()

    def _parse_response(self, text: str) -> List[RoadStatus]:
        roads = []
        import re
        
        # [ROUTE: Skąd-Dokąd | TIME: X min | STATUS: Status | DELAY: X min | NOTE: Opis przyczyny]
        pattern = r"\[ROUTE: (.*?) \| TIME: (.*?) \| STATUS: (.*?) \| DELAY: (.*?) \| NOTE: (.*?)\]"
        matches = re.finditer(pattern, text)
        
        for i, match in enumerate(matches):
            name = match.group(1).strip()
            travel_time = match.group(2).strip()
            status_text = match.group(3).strip()
            delay_text = match.group(4).strip()
            note = match.group(5).strip()
            
            status = "UNKNOWN"
            s_lower = status_text.lower()
            if 'płyn' in s_lower: status = 'Płynnie'
            elif 'utrud' in s_lower: status = 'Utrudnienia'
            elif 'kork' in s_lower: status = 'Korki'
            
            # Parse delay "5 min" -> 5
            try:
                delay = int(''.join(filter(str.isdigit, delay_text)))
            except:
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
                RoadStatus(id='1', name='Rybno -> Działdowo', status='Utrudnienia', delayMinutes=5, travelTime='28 min', description='Utrudnienia przy wjeździe do Działdowa przez oblodzoną nawierzchnię na DW538.'),
                RoadStatus(id='2', name='Rybno -> Lubawa', status='Płynnie', delayMinutes=0, travelTime='22 min', description='Trasa czysta, nawierzchnia czarna mokra, brak widocznych utrudnień.'),
                RoadStatus(id='3', name='Rybno -> Iława', status='Płynnie', delayMinutes=0, travelTime='35 min', description='Ruch odbywa się płynnie, zachowana dobra przejezdność przez Hartowiec.'),
                RoadStatus(id='4', name='Rybno -> Olsztyn', status='Korki', delayMinutes=15, travelTime='1h 10 min', description='Znaczne opóźnienia na trasie przez opady śniegu i spowolniony ruch na wysokości Nidzicy.')
            ],
            sources=[]
        )
