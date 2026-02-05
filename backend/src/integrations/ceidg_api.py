"""
CEIDG API Integration - Centralna Ewidencja i Informacja o Działalności Gospodarczej

API v3: https://dane.biznes.gov.pl/api/ceidg/v3
Dokumentacja: https://dane.biznes.gov.pl/pl/api

Wymagany token JWT z biznes.gov.pl
"""
import os
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.utils.logger import setup_logger
from src.config import settings

logger = setup_logger("CEIDGService")


class CEIDGService:
    """Serwis do pobierania danych firm z API CEIDG"""

    BASE_URL = "https://dane.biznes.gov.pl/api/ceidg/v3"
    
    # Gmina docelowa
    TARGET_GMINA = "Rybno"
    TARGET_POWIAT = "działdowski"

    def __init__(self, token: Optional[str] = None, timeout: int = 60):
        """
        Args:
            token: JWT token z biznes.gov.pl (domyślnie z env CEIDG_API_TOKEN)
            timeout: Timeout dla requestów HTTP (sekundy)
        """
        self.token = token or settings.CEIDG_API_TOKEN
        if not self.token:
            raise ValueError("CEIDG_API_TOKEN is required. Set it in environment or .env file.")
        
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }
        self.logger = logger

    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Wykonaj request do API CEIDG

        Args:
            endpoint: Ścieżka endpointu (np. "/firmy")
            params: Query parametry

        Returns:
            Odpowiedź JSON z API
        """
        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                self.logger.info(f"CEIDG API request: {url} | params: {params}")

                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 401:
                        raise Exception("Unauthorized - check CEIDG_API_TOKEN")
                    if response.status == 429:
                        raise Exception("Rate limit exceeded")
                    if response.status == 400:
                        error_text = await response.text()
                        raise Exception(f"Bad request: {error_text}")
                    if response.status == 204:
                        return {"firmy": [], "count": 0, "links": {}}
                    
                    response.raise_for_status()
                    data = await response.json()

                    self.logger.info(f"CEIDG API response: {response.status} | count: {data.get('count', 0)}")
                    return data

        except aiohttp.ClientError as e:
            self.logger.error(f"CEIDG API error: {e}")
            raise Exception(f"CEIDG API request failed: {e}")

    async def search_by_gmina(
        self,
        gmina: str,
        limit: int = 25,
        page: int = 1,
        status: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Wyszukaj firmy w danej gminie

        Args:
            gmina: Nazwa gminy (np. "Rybno")
            limit: Wyniki na stronę (max 25)
            page: Numer strony (od 1)
            status: Lista statusów do filtrowania

        Returns:
            Dict z 'firmy', 'count', 'links'
        """
        params = {
            "gmina": gmina,
            "limit": min(limit, 25),
            "page": page
        }

        if status:
            params["status"] = ",".join(status)

        return await self._make_request("/firmy", params)

    async def search_by_nip(self, nip: str) -> Dict[str, Any]:
        """Wyszukaj firmę po NIP"""
        # Usuń myślniki jeśli są
        nip_clean = nip.replace("-", "").replace(" ", "")
        return await self._make_request("/firmy", {"nip": nip_clean})

    async def search_by_regon(self, regon: str) -> Dict[str, Any]:
        """Wyszukaj firmę po REGON"""
        return await self._make_request("/firmy", {"regon": regon})

    async def fetch_all_businesses(
        self,
        gmina: str,
        powiat_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Pobierz wszystkie firmy z danej gminy (z paginacją)

        Args:
            gmina: Nazwa gminy (np. "Rybno")
            powiat_filter: Filtruj tylko ten powiat (np. "działdowski")

        Returns:
            Lista wszystkich firm
        """
        all_businesses = []
        page = 1
        total_count = None

        self.logger.info(f"Fetching all businesses for gmina: {gmina}")

        while True:
            self.logger.info(f"Fetching page {page}...")
            result = await self.search_by_gmina(gmina, limit=25, page=page)

            firms = result.get("firmy", [])
            if not firms:
                break

            # Filtruj po powiecie jeśli podano
            if powiat_filter:
                firms = [
                    f for f in firms
                    if f.get("adresDzialalnosci", {}).get("powiat", "").lower() == powiat_filter.lower()
                ]

            all_businesses.extend(firms)

            if total_count is None:
                total_count = result.get("count", 0)
                self.logger.info(f"Total available: {total_count}")

            # Sprawdź czy są następne strony
            links = result.get("links", {})
            if not links.get("next") or page * 25 >= total_count:
                break

            page += 1

        self.logger.info(f"Fetched {len(all_businesses)} businesses (filtered by powiat: {powiat_filter})")
        return all_businesses

    async def get_business_details(self, ceidg_id: str) -> Optional[Dict[str, Any]]:
        """
        Pobierz szczegółowe dane firmy z endpointu /firma/{id}
        """
        try:
            self.logger.info(f"Fetching details for business ID: {ceidg_id}")
            response = await self._make_request(f"/firma/{ceidg_id}")
            
            # API returns { "firma": [ { details... } ] }
            firms_list = response.get("firma", [])
            if firms_list:
                return firms_list[0]
            
            self.logger.warning(f"Business details not found for ID: {ceidg_id}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching business details for {ceidg_id}: {e}")
            return None

    def extract_business_data(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wyekstrahuj dane firmy do formatu bazy danych.
        Obsługuje zarówno format skrócony (z listy) jak i pełny (z detali).
        """
        adres = raw.get("adresDzialalnosci", {})
        adres_kor = raw.get("adresKorespondencyjny", {})
        wlasciciel = raw.get("wlasciciel", {})
        
        # Parsuj datę rozpoczęcia
        data_rozp = raw.get("dataRozpoczecia")
        if data_rozp:
            try:
                data_rozp = datetime.strptime(data_rozp, "%Y-%m-%d")
            except ValueError:
                data_rozp = None

        # Determine link
        link = raw.get("link")
        if not link and raw.get("id"):
             link = f"https://aplikacja.ceidg.gov.pl/CEIDG/CEIDG.Public.UI/Search.aspx?Leas={raw.get('id')}"

        return {
            "ceidg_id": raw.get("id"),
            "nazwa": raw.get("nazwa", ""),
            "nip": wlasciciel.get("nip", raw.get("nip", "")),
            "regon": wlasciciel.get("regon", raw.get("regon")),
            "status": raw.get("status", "AKTYWNY"),
            "data_rozpoczecia": data_rozp,
            "wlasciciel_imie": wlasciciel.get("imie"),
            "wlasciciel_nazwisko": wlasciciel.get("nazwisko"),
            "ulica": adres.get("ulica"),
            "budynek": adres.get("budynek"),
            "lokal": adres.get("lokal"),
            "miasto": adres.get("miasto", ""),
            "kod_pocztowy": adres.get("kodPocztowy", adres.get("kod", "")),
            "gmina": adres.get("gmina", ""),
            "powiat": adres.get("powiat", ""),
            "wojewodztwo": adres.get("wojewodztwo"),
            
            # Detailed Fields
            "pkd_main": raw.get("pkdGlowny", {}).get("kod"),
            "pkd_list": raw.get("pkd", []),
            "adres_korespondencyjny": adres_kor if adres_kor else None,
            "spolki": raw.get("spolki", []),
            "obywatelstwa": raw.get("obywatelstwa", []),
            "email": raw.get("email"),
            "www": raw.get("www"),
            "telefon": raw.get("telefon"),
            
            "raw_data": raw,
            "ceidg_link": link,
            "fetched_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

    async def fetch_rybno_businesses(self) -> tuple[List[Dict], Dict]:
        """
        Pobierz wszystkie firmy z Gminy Rybno (powiat działdowski)

        Returns:
            Tuple (lista firm, statystyki)
        """
        businesses = await self.fetch_all_businesses(
            gmina=self.TARGET_GMINA,
            powiat_filter=self.TARGET_POWIAT
        )

        # Oblicz statystyki
        by_miejscowosc = {}
        active_count = 0

        for b in businesses:
            miasto = b.get("adresDzialalnosci", {}).get("miasto", "Nieznane")
            by_miejscowosc[miasto] = by_miejscowosc.get(miasto, 0) + 1
            if b.get("status") == "AKTYWNY":
                active_count += 1

        stats = {
            "gmina": self.TARGET_GMINA,
            "powiat": self.TARGET_POWIAT,
            "total_count": len(businesses),
            "active_count": active_count,
            "by_miejscowosc": dict(sorted(by_miejscowosc.items(), key=lambda x: -x[1])),
            "last_sync": datetime.utcnow().isoformat()
        }

        return businesses, stats
