"""
GUS API Integration - Bank Danych Lokalnych (BDL)

Integracja z API GUS (api.stat.gov.pl) do pobierania statystyk demograficznych
i rynku pracy dla Powiatu Działdowskiego.

Dokumentacja API: https://api.stat.gov.pl/Home/BdlApi
"""
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from src.utils.logger import setup_logger

logger = setup_logger("GUSDataService")


class GUSDataService:
    """Serwis do pobierania danych z API GUS (BDL)"""

    BASE_URL = "https://bdl.stat.gov.pl/api/v1"

    # Unit ID dla Powiatu Działdowskiego (kod TERYT: 2803)
    UNIT_ID_DZIALDOWO = "042815403000"  # Zweryfikowane z API GUS (2026-01-14)

    # Variable IDs - Zweryfikowane 2026-01-14 przez kompleksowy test API
    # Wszystkie zmienne poniżej mają dane dla Powiatu Działdowskiego (2024)
    VARS = {
        # ==================== DEMOGRAFIA ====================
        "population_total": "72305",          # Ludność ogółem (61,003 w 2024)
        "infant_mortality_rate": "60569",     # Zgony niemowląt na 1000 urodzeń żywych (4.9)
        "mortality_rate": "454134",           # Zgony ogółem na 1000 urodzeń żywych (156.3)
        "divorces": "1616553",                # Rozwody (109)

        # ==================== RYNEK PRACY ====================
        "unemployment_rate": "60270",         # Stopa bezrobocia rejestrowanego % (12.4)
        "avg_salary": "64428",                # Przeciętne wynagrodzenie brutto PLN (6,837.70)
        "registered_unemployed": "106027",    # Bezrobotni zarejestrowani (290)
        "unemployed_total": "459121",         # Bezrobocie ogółem (501)

        # ==================== TRANSPORT ====================
        "personal_cars": "32561",             # Samochody osobowe (36,874)
        "vehicles_total": "10505",            # Pojazdy samochodowe i ciągniki (47,516)
        "vehicles_per_1000": "454131",        # Pojazdy na 1000 ludności (779)
        "buses": "32555",                     # Autobusy ogółem (85)
        "trucks": "32556",                    # Samochody ciężarowe (3,848)
        "paved_roads_km": "7723",             # Drogi o nawierzchni twardej (km) (307)
        "improved_roads_km": "7724",          # Drogi o nawierzchni twardej ulepszonej (km) (307)
        "unpaved_roads_km": "7725",           # Drogi gruntowe (km) (9.1)

        # ==================== INFRASTRUKTURA / FINANSE ====================
        "road_spending": "395094",            # Wydatki na drogi powiatowe PLN (14,624,793)
        "library_spending": "8536",           # Wydatki na biblioteki PLN (72,986)
        "social_care_spending": "395146",     # Wydatki na domy pomocy PLN (7,880,418)

        # ==================== TURYSTYKA ====================
        "accommodations_per_10000": "1539594", # Noclegi na 10000 ludności (5,028)
    }

    def __init__(self, timeout: int = 30):
        """
        Args:
            timeout: Timeout dla requestów HTTP (sekundy)
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.logger = logger

    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Wykonaj request do API GUS

        Args:
            endpoint: Ścieżka endpointu (np. "/data/by-unit/1403000000")
            params: Query parametry

        Returns:
            Odpowiedź JSON z API

        Raises:
            Exception: Jeśli request się nie powiedzie
        """
        url = f"{self.BASE_URL}{endpoint}"

        # Domyślne parametry
        default_params = {
            "format": "json",
            "page-size": 100,  # Max wyniki na stronę
        }

        if params:
            default_params.update(params)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                self.logger.info(f"GUS API request: {url} | params: {default_params}")

                async with session.get(url, params=default_params) as response:
                    response.raise_for_status()
                    data = await response.json()

                    self.logger.info(f"GUS API response: {response.status} | records: {len(data.get('results', []))}")
                    return data

        except aiohttp.ClientError as e:
            self.logger.error(f"GUS API error: {e}")
            raise Exception(f"GUS API request failed: {e}")

    async def get_population_stats(
        self,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Pobierz statystyki demograficzne dla Powiatu Działdowskiego

        Args:
            year: Rok danych (domyślnie: ostatni dostępny)

        Returns:
            Dict ze statystykami:
            {
                "total": int,                    # Ludność ogółem
                "infant_mortality_rate": float,  # Zgony niemowląt na 1000 urodzeń
                "mortality_rate": float,         # Zgony na 1000 urodzeń
                "divorces": int,                 # Liczba rozwodów
                "year": int,                     # Rok danych
                "updated_at": str                # Kiedy pobrano (ISO)
            }
        """
        vars_to_fetch = {
            "total": self.VARS["population_total"],
            "infant_mortality_rate": self.VARS["infant_mortality_rate"],
            "mortality_rate": self.VARS["mortality_rate"],
            "divorces": self.VARS["divorces"],
        }

        stats = {
            "total": None,
            "infant_mortality_rate": None,
            "mortality_rate": None,
            "divorces": None,
            "year": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            endpoint = f"/data/by-unit/{self.UNIT_ID_DZIALDOWO}"

            for stat_name, var_id in vars_to_fetch.items():
                params = {"var-id": var_id}
                if year:
                    params["year"] = str(year)

                response = await self._make_request(endpoint, params)
                results = response.get("results", [])

                if results:
                    values = results[0].get("values", [])
                    if values:
                        latest = values[-1]
                        value = latest.get("val")
                        year_val = latest.get("year")

                        if stat_name == "total":
                            stats["total"] = int(value) if value else None
                            stats["year"] = year_val
                        elif stat_name == "infant_mortality_rate":
                            stats["infant_mortality_rate"] = float(value) if value else None
                        elif stat_name == "mortality_rate":
                            stats["mortality_rate"] = float(value) if value else None
                        elif stat_name == "divorces":
                            stats["divorces"] = int(value) if value else None

            self.logger.info(f"Demographics stats: {stats['total']} population in {stats['year']}")
            return stats

        except Exception as e:
            self.logger.error(f"Failed to get population stats: {e}")
            raise

    async def get_employment_stats(
        self,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Pobierz statystyki rynku pracy dla Powiatu Działdowskiego

        Args:
            year: Rok danych (domyślnie: ostatni dostępny)

        Returns:
            Dict ze statystykami:
            {
                "unemployment_rate": float,    # Stopa bezrobocia (%)
                "registered_unemployed": int,  # Bezrobotni zarejestrowani
                "unemployed_total": int,       # Bezrobocie ogółem
                "avg_salary": float,           # Średnie wynagrodzenie (PLN brutto)
                "year": int,                   # Rok danych
                "updated_at": str              # Kiedy pobrano (ISO)
            }
        """
        vars_to_fetch = {
            "unemployment_rate": self.VARS["unemployment_rate"],
            "registered_unemployed": self.VARS["registered_unemployed"],
            "unemployed_total": self.VARS["unemployed_total"],
            "avg_salary": self.VARS["avg_salary"],
        }

        stats = {
            "unemployment_rate": None,
            "registered_unemployed": None,
            "unemployed_total": None,
            "avg_salary": None,
            "year": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            endpoint = f"/data/by-unit/{self.UNIT_ID_DZIALDOWO}"

            for stat_name, var_id in vars_to_fetch.items():
                params = {"var-id": var_id}
                if year:
                    params["year"] = str(year)

                response = await self._make_request(endpoint, params)
                results = response.get("results", [])

                if results:
                    values = results[0].get("values", [])
                    if values:
                        latest = values[-1]
                        value = latest.get("val")
                        year_val = latest.get("year")

                        if stat_name == "unemployment_rate":
                            stats["unemployment_rate"] = float(value) if value else None
                            stats["year"] = year_val
                        elif stat_name == "registered_unemployed":
                            stats["registered_unemployed"] = int(value) if value else None
                        elif stat_name == "unemployed_total":
                            stats["unemployed_total"] = int(value) if value else None
                        elif stat_name == "avg_salary":
                            stats["avg_salary"] = float(value) if value else None

            self.logger.info(
                f"Employment stats: {stats['unemployment_rate']}% unemployment in {stats['year']}"
            )
            return stats

        except Exception as e:
            self.logger.error(f"Failed to get employment stats: {e}")
            raise

    async def search_variables(
        self,
        subject_id: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[Dict]:
        """
        Wyszukaj zmienne w API GUS (dla debugowania/eksploracji)

        Args:
            subject_id: ID kategorii (np. "K1" - Demografia)
            keyword: Słowo kluczowe (np. "ludność")

        Returns:
            Lista zmiennych z API
        """
        endpoint = "/variables"
        params = {}

        if subject_id:
            params["subject-id"] = subject_id

        try:
            response = await self._make_request(endpoint, params)
            variables = response.get("results", [])

            # Filtruj po keyword jeśli podano
            if keyword:
                keyword_lower = keyword.lower()
                variables = [
                    v for v in variables
                    if keyword_lower in v.get("n1", "").lower()
                ]

            self.logger.info(f"Found {len(variables)} variables")
            return variables

        except Exception as e:
            self.logger.error(f"Failed to search variables: {e}")
            raise

    async def get_unit_info(self, unit_id: Optional[str] = None) -> Dict:
        """
        Pobierz informacje o jednostce terytorialnej

        Args:
            unit_id: ID jednostki (domyślnie: Powiat Działdowski)

        Returns:
            Dict z informacjami o jednostce
        """
        if not unit_id:
            unit_id = self.UNIT_ID_DZIALDOWO

        endpoint = f"/units/{unit_id}"

        try:
            response = await self._make_request(endpoint)
            unit = response

            self.logger.info(f"Unit info: {unit.get('name')}")
            return unit

        except Exception as e:
            self.logger.error(f"Failed to get unit info: {e}")
            raise

    async def get_transport_stats(
        self,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Pobierz statystyki transportowe dla Powiatu Działdowskiego

        Returns:
            Dict ze statystykami:
            {
                "personal_cars": int,            # Samochody osobowe
                "vehicles_total": int,           # Pojazdy samochodowe ogółem
                "vehicles_per_1000": int,        # Pojazdy na 1000 ludności
                "buses": int,                    # Autobusy
                "trucks": int,                   # Samochody ciężarowe
                "paved_roads_km": float,         # Drogi o nawierzchni twardej (km)
                "improved_roads_km": float,      # Drogi o nawierzchni twardej ulepszonej (km)
                "unpaved_roads_km": float,       # Drogi gruntowe (km)
                "year": int,
                "updated_at": str
            }
        """
        vars_to_fetch = {
            "personal_cars": self.VARS["personal_cars"],
            "vehicles_total": self.VARS["vehicles_total"],
            "vehicles_per_1000": self.VARS["vehicles_per_1000"],
            "buses": self.VARS["buses"],
            "trucks": self.VARS["trucks"],
            "paved_roads_km": self.VARS["paved_roads_km"],
            "improved_roads_km": self.VARS["improved_roads_km"],
            "unpaved_roads_km": self.VARS["unpaved_roads_km"],
        }

        stats = {
            "personal_cars": None,
            "vehicles_total": None,
            "vehicles_per_1000": None,
            "buses": None,
            "trucks": None,
            "paved_roads_km": None,
            "improved_roads_km": None,
            "unpaved_roads_km": None,
            "year": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            endpoint = f"/data/by-unit/{self.UNIT_ID_DZIALDOWO}"

            for stat_name, var_id in vars_to_fetch.items():
                params = {"var-id": var_id}
                if year:
                    params["year"] = str(year)

                try:
                    response = await self._make_request(endpoint, params)
                    results = response.get("results", [])

                    if results:
                        values = results[0].get("values", [])
                        if values:
                            latest = values[-1]
                            value = latest.get("val")
                            year_val = latest.get("year")

                            if stat_name.endswith("_km"):
                                stats[stat_name] = float(value) if value else None
                            else:
                                stats[stat_name] = int(value) if value else None

                            if stats["year"] is None:
                                stats["year"] = year_val

                except Exception as e:
                    self.logger.warning(f"Failed to get {stat_name}: {e}")
                    continue

            self.logger.info(
                f"Transport stats: {stats['personal_cars']} cars, {stats['vehicles_total']} vehicles, "
                f"{stats['paved_roads_km']} km roads in {stats['year']}"
            )
            return stats

        except Exception as e:
            self.logger.error(f"Failed to get transport stats: {e}")
            raise

    async def get_infrastructure_stats(
        self,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Pobierz statystyki infrastruktury i finansów dla Powiatu Działdowskiego

        Returns:
            Dict ze statystykami:
            {
                "road_spending": float,           # Wydatki na drogi powiatowe (PLN)
                "library_spending": float,        # Wydatki na biblioteki (PLN)
                "social_care_spending": float,    # Wydatki na domy pomocy (PLN)
                "accommodations_per_10000": int,  # Noclegi na 10000 ludności
                "year": int,
                "updated_at": str
            }
        """
        vars_to_fetch = {
            "road_spending": self.VARS["road_spending"],
            "library_spending": self.VARS["library_spending"],
            "social_care_spending": self.VARS["social_care_spending"],
            "accommodations_per_10000": self.VARS["accommodations_per_10000"],
        }

        stats = {
            "road_spending": None,
            "library_spending": None,
            "social_care_spending": None,
            "accommodations_per_10000": None,
            "year": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            endpoint = f"/data/by-unit/{self.UNIT_ID_DZIALDOWO}"

            for stat_name, var_id in vars_to_fetch.items():
                params = {"var-id": var_id}
                if year:
                    params["year"] = str(year)

                try:
                    response = await self._make_request(endpoint, params)
                    results = response.get("results", [])

                    if results:
                        values = results[0].get("values", [])
                        if values:
                            latest = values[-1]
                            value = latest.get("val")
                            year_val = latest.get("year")

                            if stat_name.endswith("_spending"):
                                stats[stat_name] = float(value) if value else None
                            else:
                                stats[stat_name] = int(value) if value else None

                            if stats["year"] is None:
                                stats["year"] = year_val

                except Exception as e:
                    self.logger.warning(f"Failed to get {stat_name}: {e}")
                    continue

            self.logger.info(
                f"Infrastructure stats: Road spending {stats['road_spending']} PLN, "
                f"accommodations {stats['accommodations_per_10000']}/10k in {stats['year']}"
            )
            return stats

        except Exception as e:
            self.logger.error(f"Failed to get infrastructure stats: {e}")
            raise

    # Alias dla kompatybilności wstecznej
    async def get_health_stats(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Alias dla get_infrastructure_stats (kompatybilność wsteczna)"""
        return await self.get_infrastructure_stats(year)
