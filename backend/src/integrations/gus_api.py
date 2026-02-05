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

    # ==================== UNIT IDs - GMINY W POWIECIE DZIAŁDOWSKIM ====================
    # Główna jednostka: Gmina Rybno
    UNIT_ID_RYBNO = "042815403062"        # Gmina Rybno (główna)
    
    # Pozostałe gminy do porównań
    UNIT_ID_DZIALDOWO_M = "042815403011"  # Miasto Działdowo
    UNIT_ID_DZIALDOWO_G = "042815403022"  # Gmina Działdowo (wiejska)
    UNIT_ID_ILOWO = "042815403032"        # Gmina Iłowo-Osada
    UNIT_ID_LIDZBARK = "042815403043"     # Gmina Lidzbark (miejsko-wiejska)
    UNIT_ID_PLOSNICA = "042815403052"     # Gmina Płośnica
    
    # Powiat (dla agregacji)
    UNIT_ID_POWIAT = "042815403000"       # Powiat Działdowski
    
    # Słownik wszystkich gmin do porównań
    GMINY = {
        "Rybno": "042815403062",
        "Działdowo (miasto)": "042815403011",
        "Działdowo (gmina)": "042815403022",
        "Iłowo-Osada": "042815403032",
        "Lidzbark": "042815403043",
        "Płośnica": "042815403052",
    }

    # Zmienne dostępne TYLKO na poziomie powiatu (nie gminy)
    # Transport i infrastruktura są agregowane na poziomie powiatu
    POWIAT_LEVEL_VARS = [
        "personal_cars", "vehicles_total", "vehicles_per_1000",
        "buses", "trucks", "paved_roads_km", "improved_roads_km", "unpaved_roads_km",
        "road_spending", "library_spending", "social_care_spending",
        "accommodations_per_10000"
    ]

    # Variable IDs - Zweryfikowane 2026-01-14 przez kompleksowy test API
    # Wszystkie zmienne poniżej mają dane dla Powiatu Działdowskiego (2024)
    VARS = {
        # ==================== DEMOGRAFIA ====================
        "population_total": "72305",          # Ludność ogółem (61,003 w 2024)
        "population_male": "1645344",         # Ludność mężczyźni (tys.)
        "population_female": "1645343",       # Ludność kobiety (tys.)
        "population_density": "60559",        # Gęstość zaludnienia (os./km²)
        "births_live": "59",                  # Urodzenia żywe
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

        # ==================== PRZEDSIĘBIORCZOŚĆ ====================
        # Zweryfikowane 2026-02-03 przez API GUS
        "entities_regon_per_10k": "60530",        # Podmioty wpisane do REGON na 10 tys. ludności
        "new_entities_per_10k": "60529",          # Jednostki nowo zarejestrowane REGON na 10 tys. ludności
        "deregistered_per_10k": "60528",          # Jednostki wykreślone z REGON na 10 tys. ludności
        "micro_enterprises_share": "1548709",     # Udział mikroprzedsiębiorstw (do 9 osób) %
        "deregistered_share": "471845",           # Udział podmiotów wyrejestrowanych %
        "new_to_deregistered_ratio": "1645253",   # Stosunek nowo zarejestrowanych do wyrejestrowanych %
        "entities_per_1k": "458173",              # Podmioty wpisane do rejestru na 1000 ludności
        "sme_per_10k": "1620132",                 # Podmioty MŚP (0-249 pracujących) na 10 tys. mieszkańców
        "large_entities_per_10k": "634131",       # Podmioty o liczbie pracujących >49 na 10 tys. mieszkańców
        "natural_persons_business": "152710",     # Osoby fizyczne - działalność gospodarcza
        "foreign_capital_companies": "1725014",   # Spółki z kapitałem zagranicznym/10k

        # ==================== FINANSE ====================
        "investment_expenditure": "76450",        # Wydatki inwestycyjne gmin (PLN)
    }

    def __init__(self, timeout: int = 30):
        """
        Args:
            timeout: Timeout dla requestów HTTP (sekundy)
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.logger = logger

    def _get_unit_id_for_variable(self, var_key: str) -> str:
        """
        Określ właściwy unit_id dla zmiennej (gmina vs powiat).

        Zmienne transportowe i infrastrukturalne są dostępne tylko na poziomie powiatu.
        Pozostałe zmienne są dostępne na poziomie gminy.

        Args:
            var_key: Klucz zmiennej (np. "personal_cars", "population_total")

        Returns:
            Unit ID (gmina Rybno lub powiat Działdowski)
        """
        if var_key in self.POWIAT_LEVEL_VARS:
            return self.UNIT_ID_POWIAT
        return self.UNIT_ID_RYBNO

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
            endpoint = f"/data/by-unit/{self.UNIT_ID_RYBNO}"

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
            endpoint = f"/data/by-unit/{self.UNIT_ID_RYBNO}"

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
            unit_id = self.UNIT_ID_RYBNO

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

        UWAGA: Dane transportowe są dostępne tylko na poziomie POWIATU,
        nie dla pojedynczych gmin.

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
            # ZMIANA: Używamy POWIAT zamiast RYBNO dla danych transportowych
            endpoint = f"/data/by-unit/{self.UNIT_ID_POWIAT}"

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

        UWAGA: Dane infrastrukturalne są dostępne tylko na poziomie POWIATU,
        nie dla pojedynczych gmin.

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
            # ZMIANA: Używamy POWIAT zamiast RYBNO dla danych infrastrukturalnych
            endpoint = f"/data/by-unit/{self.UNIT_ID_POWIAT}"

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

    async def get_business_stats(
        self,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Pobierz statystyki przedsiębiorczości dla Powiatu Działdowskiego

        Args:
            year: Rok danych (domyślnie: ostatni dostępny)

        Returns:
            Dict ze statystykami:
            {
                "entities_regon_per_10k": float,      # Podmioty REGON na 10 tys. ludności
                "new_entities_per_10k": float,        # Nowo zarejestrowane na 10 tys. ludności
                "deregistered_per_10k": float,        # Wykreślone na 10 tys. ludności
                "micro_enterprises_share": float,     # Udział mikroprzedsiębiorstw (%)
                "deregistered_share": float,          # Udział wyrejestrowanych (%)
                "new_to_deregistered_ratio": float,   # Stosunek nowych do wyrejestrowanych (%)
                "entities_per_1k": float,             # Podmioty na 1000 ludności
                "sme_per_10k": float,                 # MŚP na 10 tys. mieszkańców
                "large_entities_per_10k": float,      # Duże firmy (>49 osób) na 10 tys. mieszkańców
                "year": int,
                "updated_at": str
            }
        """
        vars_to_fetch = {
            "entities_regon_per_10k": self.VARS.get("entities_regon_per_10k"),
            "new_entities_per_10k": self.VARS.get("new_entities_per_10k"),
            "deregistered_per_10k": self.VARS.get("deregistered_per_10k"),
            "micro_enterprises_share": self.VARS.get("micro_enterprises_share"),
            "deregistered_share": self.VARS.get("deregistered_share"),
            "new_to_deregistered_ratio": self.VARS.get("new_to_deregistered_ratio"),
            "entities_per_1k": self.VARS.get("entities_per_1k"),
            "sme_per_10k": self.VARS.get("sme_per_10k"),
            "large_entities_per_10k": self.VARS.get("large_entities_per_10k"),
        }

        stats = {
            "entities_regon_per_10k": None,
            "new_entities_per_10k": None,
            "deregistered_per_10k": None,
            "micro_enterprises_share": None,
            "deregistered_share": None,
            "new_to_deregistered_ratio": None,
            "entities_per_1k": None,
            "sme_per_10k": None,
            "large_entities_per_10k": None,
            "year": None,
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            endpoint = f"/data/by-unit/{self.UNIT_ID_RYBNO}"

            for stat_name, var_id in vars_to_fetch.items():
                if not var_id:
                    continue

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

                            stats[stat_name] = float(value) if value else None

                            if stats["year"] is None:
                                stats["year"] = year_val

                except Exception as e:
                    self.logger.warning(f"Failed to get {stat_name}: {e}")
                    continue

            self.logger.info(
                f"Business stats: {stats['entities_regon_per_10k']} entities/10k, "
                f"{stats['new_entities_per_10k']} new/10k, "
                f"{stats['micro_enterprises_share']}% micro in {stats['year']}"
            )
            return stats

        except Exception as e:
            self.logger.error(f"Failed to get business stats: {e}")
            raise

    # ==================== NOWE METODY DLA GMINY RYBNO ====================

    async def get_gmina_stats(
        self,
        unit_id: str,
        var_id: str,
        years_back: int = 10
    ) -> Dict[str, Any]:
        """
        Pobierz dane dla konkretnej gminy i wskaźnika

        Args:
            unit_id: ID jednostki GUS (np. "042815403062" dla Rybna)
            var_id: ID zmiennej GUS (np. "60530" dla podmiotów REGON)
            years_back: Ile lat wstecz pobierać (domyślnie 10)

        Returns:
            Dict z danymi historycznymi dla danej gminy
        """
        try:
            endpoint = f"/data/by-unit/{unit_id}"
            params = {"var-id": var_id}

            response = await self._make_request(endpoint, params)
            results = response.get("results", [])

            if not results:
                return {"unit_id": unit_id, "var_id": var_id, "values": []}

            values = results[0].get("values", [])
            
            # Filtruj do ostatnich N lat
            current_year = datetime.now().year
            min_year = current_year - years_back
            
            filtered_values = [
                {"year": int(v["year"]), "value": float(v["val"]) if v["val"] else None}
                for v in values
                if int(v["year"]) >= min_year
            ]

            return {
                "unit_id": unit_id,
                "unit_name": response.get("unitName", ""),
                "var_id": var_id,
                "values": filtered_values,
                "fetched_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to get gmina stats for {unit_id}, var {var_id}: {e}")
            raise

    async def get_comparative_stats(
        self,
        var_id: str,
        year: Optional[int] = None,
        var_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pobierz dane porównawcze dla wszystkich gmin w powiecie
        LUB dla powiatu (jeśli zmienna dostępna tylko na poziomie powiatu)

        Args:
            var_id: ID zmiennej GUS
            year: Rok danych (domyślnie: ostatni dostępny)
            var_key: Klucz zmiennej (opcjonalnie, dla określenia poziomu)

        Returns:
            Dict z danymi dla wszystkich gmin lub powiatu
        """
        # Znajdź var_key jeśli nie podano
        if not var_key:
            for key, vid in self.VARS.items():
                if vid == var_id:
                    var_key = key
                    break

        # Sprawdź czy to zmienna powiatowa
        is_powiat_level = var_key in self.POWIAT_LEVEL_VARS if var_key else False

        comparison = {
            "var_id": var_id,
            "year": year,
            "gminy": {},
            "fetched_at": datetime.utcnow().isoformat()
        }

        if is_powiat_level:
            # Dla zmiennych powiatowych - pobierz tylko dane powiatu
            try:
                endpoint = f"/data/by-unit/{self.UNIT_ID_POWIAT}"
                params = {"var-id": var_id}
                if year:
                    params["year"] = str(year)

                response = await self._make_request(endpoint, params)
                results = response.get("results", [])

                if results:
                    values = results[0].get("values", [])
                    if values:
                        latest = values[-1]
                        # Dla powiatu używamy nazwy "Rybno" żeby frontend działał
                        comparison["gminy"]["Rybno"] = {
                            "value": float(latest["val"]) if latest["val"] else None,
                            "year": int(latest["year"])
                        }
                        comparison["year"] = int(latest["year"])
            except Exception as e:
                self.logger.warning(f"Failed to get powiat data: {e}")
                comparison["gminy"]["Rybno"] = {"value": None, "year": None}
        else:
            # Dla zmiennych gminnych - pobierz dane wszystkich gmin
            for gmina_name, unit_id in self.GMINY.items():
                try:
                    endpoint = f"/data/by-unit/{unit_id}"
                    params = {"var-id": var_id}
                    if year:
                        params["year"] = str(year)

                    response = await self._make_request(endpoint, params)
                    results = response.get("results", [])

                    if results:
                        values = results[0].get("values", [])
                        if values:
                            # Weź ostatnią wartość
                            latest = values[-1]
                            comparison["gminy"][gmina_name] = {
                                "value": float(latest["val"]) if latest["val"] else None,
                                "year": int(latest["year"])
                            }
                            # Ustaw rok z pierwszej odpowiedzi
                            if comparison["year"] is None:
                                comparison["year"] = int(latest["year"])

                except Exception as e:
                    self.logger.warning(f"Failed to get data for {gmina_name}: {e}")
                    comparison["gminy"][gmina_name] = {"value": None, "year": None}

        return comparison

    async def get_historical_trend(
        self,
        var_id: str,
        years_back: int = 22,
        var_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pobierz pełny trend historyczny (gmina Rybno lub powiat Działdowski)

        Automatycznie wybiera właściwy poziom w zależności od typu zmiennej.

        Args:
            var_id: ID zmiennej GUS
            years_back: Ile lat wstecz (domyślnie 22 - od 2002)
            var_key: Klucz zmiennej (opcjonalnie, dla określenia poziomu)

        Returns:
            Dict z danymi historycznymi
        """
        # Znajdź var_key jeśli nie podano
        if not var_key:
            for key, vid in self.VARS.items():
                if vid == var_id:
                    var_key = key
                    break

        # Określ właściwy unit_id
        unit_id = self._get_unit_id_for_variable(var_key) if var_key else self.UNIT_ID_RYBNO

        return await self.get_gmina_stats(unit_id, var_id, years_back)

    async def get_single_variable(
        self,
        var_key: str,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Pobierz pojedynczą zmienną (uniwersalna metoda)

        Automatycznie wybiera właściwy poziom (gmina Rybno vs powiat Działdowski)
        w zależności od typu zmiennej.

        Args:
            var_key: Klucz zmiennej (np. "population_density", "unemployment_rate")
            year: Rok danych (domyślnie: ostatni dostępny)

        Returns:
            Dict z danymi:
            {
                "var_key": str,              # Klucz zmiennej
                "var_id": str,               # ID zmiennej GUS
                "value": float | int | None, # Wartość
                "year": int,                 # Rok danych
                "unit_id": str,              # ID jednostki
                "updated_at": str            # Kiedy pobrano (ISO)
            }
        """
        var_id = self.VARS.get(var_key)
        if not var_id:
            raise ValueError(f"Unknown variable key: {var_key}")

        # Określ właściwy unit_id (gmina vs powiat)
        unit_id = self._get_unit_id_for_variable(var_key)

        try:
            endpoint = f"/data/by-unit/{unit_id}"
            params = {"var-id": var_id}
            if year:
                params["year"] = str(year)

            response = await self._make_request(endpoint, params)
            results = response.get("results", [])

            if not results:
                return {
                    "var_key": var_key,
                    "var_id": var_id,
                    "value": None,
                    "year": year,
                    "unit_id": unit_id,
                    "updated_at": datetime.utcnow().isoformat()
                }

            values = results[0].get("values", [])
            if not values:
                return {
                    "var_key": var_key,
                    "var_id": var_id,
                    "value": None,
                    "year": year,
                    "unit_id": unit_id,
                    "updated_at": datetime.utcnow().isoformat()
                }

            latest = values[-1]
            value_raw = latest.get("val")
            year_val = latest.get("year")

            # Konwersja wartości (int dla liczb całkowitych, float dla reszty)
            value = None
            if value_raw is not None:
                try:
                    # Jeśli wartość ma przecinek/kropkę - to float
                    if "." in str(value_raw) or "," in str(value_raw):
                        value = float(value_raw)
                    else:
                        value = int(value_raw)
                except (ValueError, TypeError):
                    value = float(value_raw)

            self.logger.info(f"Variable {var_key} ({var_id}): {value} in {year_val} [unit: {unit_id}]")

            return {
                "var_key": var_key,
                "var_id": var_id,
                "value": value,
                "year": year_val,
                "unit_id": unit_id,
                "updated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to get variable {var_key} ({var_id}): {e}")
            raise
