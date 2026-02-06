"""
GUS BDL Variables Registry - Single Source of Truth

Centralny rejestr wszystkich zmiennych GUS używanych w systemie.
Zastępuje duplikację między gus_api.py VARS i gus.py VARIABLE_METADATA.

Każda zmienna ma:
- key: unikalny identyfikator w naszym systemie
- var_id: ID zmiennej w GUS BDL API
- name_pl: nazwa po polsku
- unit: jednostka (os., %, PLN, km, szt.)
- category: kategoria tematyczna
- tier: free | premium | business
- level: gmina | powiat (na jakim poziomie dostępne dane)
- format_type: integer | float | currency | percentage
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class GUSVariable:
    key: str
    var_id: str
    name_pl: str
    unit: str
    category: str
    tier: str  # "free" | "premium" | "business"
    level: str  # "gmina" | "powiat"
    format_type: str  # "integer" | "float" | "currency" | "percentage"


# ============================================================
#  CATEGORIES
# ============================================================

CATEGORIES = {
    "demografia": {"name": "Demografia", "icon": "Users", "order": 1},
    "rynek_pracy": {"name": "Rynek Pracy", "icon": "Briefcase", "order": 2},
    "przedsiebiorczosc": {"name": "Przedsiębiorczość", "icon": "Building2", "order": 3},
    "finanse_gminy": {"name": "Finanse Gminy", "icon": "Wallet", "order": 4},
    "mieszkalnictwo": {"name": "Mieszkalnictwo", "icon": "Home", "order": 5},
    "edukacja": {"name": "Edukacja", "icon": "GraduationCap", "order": 6},
    "transport": {"name": "Transport", "icon": "Car", "order": 7},
    "bezpieczenstwo": {"name": "Bezpieczeństwo", "icon": "Shield", "order": 8},
    "zdrowie": {"name": "Zdrowie", "icon": "Heart", "order": 9},
    "turystyka": {"name": "Turystyka", "icon": "MapPin", "order": 10},
}


# ============================================================
#  UNIT IDs
# ============================================================

UNIT_IDS = {
    "Rybno": "042815403062",
    "Działdowo (miasto)": "042815403011",
    "Działdowo (gmina)": "042815403022",
    "Iłowo-Osada": "042815403032",
    "Lidzbark": "042815403043",
    "Płośnica": "042815403052",
}

UNIT_ID_POWIAT = "042815403000"
UNIT_ID_POLSKA = "000000000000"
UNIT_ID_WOJEWODZTWO = "042800000000"


# ============================================================
#  VARIABLES REGISTRY
# ============================================================

# All variables defined as a list, then indexed by key and var_id
_VARIABLES_LIST: List[GUSVariable] = [

    # ==================== DEMOGRAFIA (gmina) ====================
    # Verified: 72305=6682(2024), 1645344, 1645343, 60559=45.0(2024), 59=47(2024)
    GUSVariable("population_total", "72305", "Ludność ogółem", "os.", "demografia", "free", "gmina", "integer"),
    GUSVariable("population_male", "1645344", "Ludność mężczyźni", "tys.", "demografia", "premium", "gmina", "float"),
    GUSVariable("population_female", "1645343", "Ludność kobiety", "tys.", "demografia", "premium", "gmina", "float"),
    GUSVariable("population_density", "60559", "Gęstość zaludnienia", "os./km²", "demografia", "premium", "gmina", "float"),
    GUSVariable("births_live", "59", "Urodzenia żywe", "os.", "demografia", "free", "gmina", "integer"),
    GUSVariable("deaths_total", "65", "Zgony ogółem", "os.", "demografia", "premium", "gmina", "integer"),
    GUSVariable("deaths_male", "66", "Zgony mężczyźni", "os.", "demografia", "business", "gmina", "integer"),
    GUSVariable("deaths_female", "67", "Zgony kobiety", "os.", "demografia", "business", "gmina", "integer"),
    GUSVariable("infant_deaths", "62", "Zgony niemowląt", "os.", "demografia", "business", "gmina", "integer"),
    GUSVariable("infant_mortality_rate", "60569", "Zgony niemowląt na 1000 urodzeń", "", "demografia", "premium", "powiat", "float"),
    GUSVariable("mortality_rate", "454134", "Zgony ogółem na 1000 urodzeń żywych", "", "demografia", "business", "powiat", "float"),
    GUSVariable("divorces", "1616553", "Rozwody", "os.", "demografia", "business", "powiat", "integer"),
    # Migracje - verified: 269607=42(2024), 269593=87(2024), 1365234=-42(2024)
    GUSVariable("internal_migration_in", "269607", "Migracje wewnętrzne - napływ (rok)", "os.", "demografia", "premium", "gmina", "integer"),
    GUSVariable("internal_migration_out", "269593", "Migracje wewnętrzne - odpływ (rok)", "os.", "demografia", "premium", "gmina", "integer"),
    GUSVariable("migration_balance_total", "1365234", "Saldo migracji ogółem", "os.", "demografia", "premium", "gmina", "integer"),
    GUSVariable("migration_balance_internal", "80125", "Saldo migracji wewnętrznych", "os.", "demografia", "premium", "gmina", "integer"),
    GUSVariable("migration_balance_foreign", "80108", "Saldo migracji zagranicznych", "os.", "demografia", "business", "gmina", "integer"),
    GUSVariable("migration_balance_per_1k", "1365239", "Saldo migracji ogółem na 1000 ludności", "", "demografia", "free", "gmina", "float"),
    GUSVariable("migration_internal_per_1k", "498816", "Saldo migracji wewnętrznych na 1000 ludności", "", "demografia", "premium", "gmina", "float"),
    GUSVariable("migration_foreign_per_1k", "745534", "Saldo migracji zagranicznych na 1000 ludności", "", "demografia", "business", "gmina", "float"),

    # ==================== RYNEK PRACY (powiat) ====================
    # Verified via by-variable: 60270=5.7(2025), 64428=8630(2024), 106027=93578(2025)
    GUSVariable("unemployment_rate", "60270", "Stopa bezrobocia rejestrowanego", "%", "rynek_pracy", "premium", "powiat", "percentage"),
    GUSVariable("avg_salary", "64428", "Przeciętne wynagrodzenie brutto", "PLN", "rynek_pracy", "premium", "powiat", "currency"),
    GUSVariable("registered_unemployed", "106027", "Bezrobotni zarejestrowani", "os.", "rynek_pracy", "premium", "powiat", "integer"),
    GUSVariable("unemployed_total", "459121", "Bezrobocie ogółem", "os.", "rynek_pracy", "business", "powiat", "integer"),
    # Verified: 454132=144(2021) at gmina, 1620621=335.2(2021) at powiat
    GUSVariable("employed_per_1000", "454132", "Pracujący na 1000 ludności", "", "rynek_pracy", "premium", "gmina", "float"),
    GUSVariable("employed_per_1000_working_age", "1620621", "Pracujący na 1000 ludności w wieku produkcyjnym", "", "rynek_pracy", "business", "powiat", "float"),

    # ==================== PRZEDSIĘBIORCZOŚĆ (gmina) ====================
    GUSVariable("entities_regon_per_10k", "60530", "Podmioty REGON na 10 tys. ludności", "", "przedsiebiorczosc", "free", "gmina", "float"),
    GUSVariable("new_entities_per_10k", "60529", "Nowo zarejestrowane na 10 tys. ludności", "", "przedsiebiorczosc", "free", "gmina", "float"),
    GUSVariable("deregistered_per_10k", "60528", "Wykreślone z REGON na 10 tys. ludności", "", "przedsiebiorczosc", "free", "gmina", "float"),
    GUSVariable("micro_enterprises_share", "1548709", "Udział mikroprzedsiębiorstw (do 9 osób)", "%", "przedsiebiorczosc", "premium", "gmina", "percentage"),
    GUSVariable("deregistered_share", "471845", "Udział podmiotów wyrejestrowanych", "%", "przedsiebiorczosc", "business", "gmina", "percentage"),
    GUSVariable("new_to_deregistered_ratio", "1645253", "Stosunek nowych do wyrejestrowanych", "%", "przedsiebiorczosc", "business", "gmina", "percentage"),
    GUSVariable("entities_per_1k", "458173", "Podmioty na 1000 ludności", "", "przedsiebiorczosc", "business", "gmina", "float"),
    GUSVariable("sme_per_10k", "1620132", "MŚP (0-249 pracujących) na 10 tys.", "", "przedsiebiorczosc", "premium", "gmina", "float"),
    GUSVariable("large_entities_per_10k", "634131", "Podmioty >49 osób na 10 tys.", "", "przedsiebiorczosc", "premium", "gmina", "float"),
    GUSVariable("natural_persons_business", "152710", "Osoby fizyczne - działalność gospodarcza", "os.", "przedsiebiorczosc", "premium", "gmina", "integer"),
    GUSVariable("foreign_capital_companies", "1725014", "Spółki z kapitałem zagranicznym/10k", "", "przedsiebiorczosc", "business", "gmina", "float"),

    # ==================== TRANSPORT (powiat) ====================
    GUSVariable("personal_cars", "32561", "Samochody osobowe", "szt.", "transport", "premium", "powiat", "integer"),
    GUSVariable("vehicles_total", "10505", "Pojazdy samochodowe i ciągniki", "szt.", "transport", "business", "powiat", "integer"),
    GUSVariable("vehicles_per_1000", "454131", "Pojazdy na 1000 ludności", "", "transport", "premium", "powiat", "float"),
    GUSVariable("buses", "32555", "Autobusy ogółem", "szt.", "transport", "business", "powiat", "integer"),
    GUSVariable("trucks", "32556", "Samochody ciężarowe", "szt.", "transport", "business", "powiat", "integer"),
    GUSVariable("paved_roads_km", "7723", "Drogi o nawierzchni twardej", "km", "transport", "premium", "powiat", "float"),
    GUSVariable("improved_roads_km", "7724", "Drogi o nawierzchni twardej ulepszonej", "km", "transport", "business", "powiat", "float"),
    GUSVariable("unpaved_roads_km", "7725", "Drogi gruntowe", "km", "transport", "business", "powiat", "float"),

    # ==================== FINANSE GMINY ====================
    # Dochody - verified: 76037=59,342,667(2024), 76973=8866(2024), 76070=12,826,230(2024)
    GUSVariable("revenue_total", "76037", "Dochody ogółem", "PLN", "finanse_gminy", "premium", "gmina", "currency"),
    GUSVariable("revenue_per_capita", "76973", "Dochody ogółem per capita", "PLN", "finanse_gminy", "free", "gmina", "currency"),
    GUSVariable("own_revenue", "76070", "Dochody własne razem", "PLN", "finanse_gminy", "premium", "gmina", "currency"),
    GUSVariable("own_revenue_per_capita", "76976", "Dochody własne per capita", "PLN", "finanse_gminy", "premium", "gmina", "currency"),
    GUSVariable("pit_per_capita", "149128", "PIT per capita", "PLN", "finanse_gminy", "business", "gmina", "currency"),
    GUSVariable("property_tax", "76077", "Podatek od nieruchomości", "PLN", "finanse_gminy", "business", "gmina", "currency"),
    GUSVariable("subsidy_total", "77005", "Subwencja ogólna razem", "PLN", "finanse_gminy", "business", "gmina", "currency"),
    GUSVariable("subsidy_education", "77002", "Subwencja oświatowa", "PLN", "finanse_gminy", "business", "gmina", "currency"),
    # Wydatki - verified: 1548644=62,012,154(2024), 76964=9265(2024), 76967=3434(2024)
    GUSVariable("expenditure_total", "1548644", "Wydatki ogółem", "PLN", "finanse_gminy", "premium", "gmina", "currency"),
    GUSVariable("expenditure_per_capita", "76964", "Wydatki ogółem per capita", "PLN", "finanse_gminy", "free", "gmina", "currency"),
    GUSVariable("education_spending_per_capita", "76967", "Wydatki na oświatę per capita", "PLN", "finanse_gminy", "premium", "gmina", "currency"),
    GUSVariable("culture_spending_per_capita", "76970", "Wydatki na kulturę per capita", "PLN", "finanse_gminy", "business", "gmina", "currency"),
    GUSVariable("investment_expenditure", "76450", "Wydatki inwestycyjne gmin", "PLN", "finanse_gminy", "premium", "gmina", "currency"),
    GUSVariable("investment_per_capita", "1725023", "Wydatki inwestycyjne per capita", "PLN", "finanse_gminy", "premium", "gmina", "currency"),
    GUSVariable("road_spending", "395094", "Wydatki na drogi powiatowe", "PLN", "finanse_gminy", "business", "powiat", "currency"),
    GUSVariable("library_spending", "8536", "Wydatki na biblioteki", "PLN", "finanse_gminy", "business", "powiat", "currency"),
    GUSVariable("social_care_spending", "395146", "Wydatki na domy pomocy", "PLN", "finanse_gminy", "business", "powiat", "currency"),

    # ==================== MIESZKALNICTWO ====================
    # Verified: 9152=6148(2024) at gmina
    GUSVariable("water_supply_population", "9152", "Ludność korzystająca z sieci wodociągowej", "os.", "mieszkalnictwo", "premium", "gmina", "integer"),
    GUSVariable("water_network_km", "1612162", "Długość sieci wodociągowej", "km", "mieszkalnictwo", "premium", "powiat", "float"),
    GUSVariable("housing_municipal_area", "389", "Zasoby gminne - pow. użytkowa", "m²", "mieszkalnictwo", "premium", "powiat", "integer"),
    GUSVariable("housing_private_area", "63993", "Zasoby osób fizycznych - pow. użytkowa", "m²", "mieszkalnictwo", "premium", "powiat", "integer"),
    GUSVariable("dwellings_per_1000", "148156", "Mieszkania oddane na 1000 ludności", "", "mieszkalnictwo", "premium", "powiat", "float"),
    GUSVariable("dwellings_per_10000", "148158", "Mieszkania oddane na 10 tys. ludności", "", "mieszkalnictwo", "business", "powiat", "float"),

    # ==================== EDUKACJA ====================
    # Verified: 838=5(2024) at gmina, 862=5143(powiat), 804=12(powiat)
    GUSVariable("primary_schools", "838", "Szkoły podstawowe", "szt.", "edukacja", "premium", "gmina", "integer"),
    GUSVariable("students_primary", "862", "Uczniowie szkół podstawowych", "os.", "edukacja", "premium", "powiat", "integer"),
    GUSVariable("preschools", "804", "Przedszkola", "szt.", "edukacja", "premium", "powiat", "integer"),
    GUSVariable("preschool_children", "1617142", "Dzieci objęte wychowaniem przedszkolnym", "os.", "edukacja", "premium", "powiat", "integer"),
    GUSVariable("nursery_children", "410640", "Dzieci w żłobkach", "os.", "edukacja", "business", "powiat", "integer"),

    # ==================== BEZPIECZEŃSTWO (powiat) ====================
    # Verified: 398594=16.81(2024), 498627=8.42(2024), 471916=47.4(2024)
    GUSVariable("crimes_total_per_1k", "398594", "Przestępstwa ogółem na 1000 mieszkańców", "", "bezpieczenstwo", "free", "powiat", "float"),
    GUSVariable("crimes_criminal_per_1k", "498627", "Przestępstwa kryminalne na 1000 mieszkańców", "", "bezpieczenstwo", "premium", "powiat", "float"),
    GUSVariable("crimes_economic_per_1k", "498626", "Przestępstwa gospodarcze na 1000 mieszkańców", "", "bezpieczenstwo", "premium", "powiat", "float"),
    GUSVariable("crimes_road_per_1k", "498625", "Przestępstwa drogowe na 1000 mieszkańców", "", "bezpieczenstwo", "premium", "powiat", "float"),
    GUSVariable("crimes_property_per_1k", "498623", "Przestępstwa przeciwko mieniu na 1000", "", "bezpieczenstwo", "business", "powiat", "float"),
    GUSVariable("crimes_family_per_1k", "498621", "Przestępstwa przeciwko rodzinie na 1000", "", "bezpieczenstwo", "business", "powiat", "float"),
    GUSVariable("road_accidents_per_100k", "471916", "Wypadki drogowe na 100 tys. ludności", "", "bezpieczenstwo", "premium", "powiat", "float"),
    GUSVariable("road_accidents_yearly", "1605997", "Wypadki drogowe (rok)", "szt.", "bezpieczenstwo", "premium", "powiat", "integer"),

    # ==================== ZDROWIE (powiat) ====================
    # Verified: 194884=16(2024), 1616687=403309(2024)
    GUSVariable("pharmacies", "194884", "Apteki", "szt.", "zdrowie", "premium", "powiat", "integer"),
    GUSVariable("medical_consultations", "1616687", "Porady lekarskie ogółem", "szt.", "zdrowie", "premium", "powiat", "integer"),

    # ==================== TURYSTYKA (powiat) ====================
    # Verified: 1539594, 1539658=2.0(2024), 1539596=4770(2024), 60297=162.28(2024)
    GUSVariable("accommodations_per_10000", "1539594", "Noclegi na 10000 ludności", "", "turystyka", "business", "powiat", "float"),
    GUSVariable("tourist_objects_per_10k", "1539658", "Obiekty noclegowe na 10 tys. ludności", "", "turystyka", "premium", "powiat", "float"),
    GUSVariable("tourist_objects_non_hotel", "1539718", "Obiekty noclegowe (bez hotelowych)", "szt.", "turystyka", "premium", "powiat", "integer"),
    GUSVariable("overnight_stays_per_10k", "1539596", "Noclegi udzielone turystom na 10 tys.", "", "turystyka", "premium", "powiat", "float"),
    GUSVariable("tourists_per_1000", "60297", "Turyści korzystający z noclegów na 1000", "", "turystyka", "premium", "powiat", "float"),
]


# ============================================================
#  LOOKUP INDEXES
# ============================================================

def _build_indexes():
    by_key: Dict[str, GUSVariable] = {}
    by_var_id: Dict[str, GUSVariable] = {}
    by_category: Dict[str, List[GUSVariable]] = {}
    by_tier: Dict[str, List[GUSVariable]] = {}

    for var in _VARIABLES_LIST:
        by_key[var.key] = var
        by_var_id[var.var_id] = var

        if var.category not in by_category:
            by_category[var.category] = []
        by_category[var.category].append(var)

        if var.tier not in by_tier:
            by_tier[var.tier] = []
        by_tier[var.tier].append(var)

    return by_key, by_var_id, by_category, by_tier


VARS_BY_KEY, VARS_BY_VAR_ID, VARS_BY_CATEGORY, VARS_BY_TIER = _build_indexes()


# ============================================================
#  PUBLIC API
# ============================================================

def get_variable(key: str) -> Optional[GUSVariable]:
    """Get variable by key."""
    return VARS_BY_KEY.get(key)


def get_variable_by_var_id(var_id: str) -> Optional[GUSVariable]:
    """Get variable by BDL var_id."""
    return VARS_BY_VAR_ID.get(var_id)


def get_variables_for_category(category: str) -> List[GUSVariable]:
    """Get all variables for a category."""
    return VARS_BY_CATEGORY.get(category, [])


def get_variables_for_tier(tier: str) -> List[GUSVariable]:
    """Get variables available at a given tier (cumulative)."""
    if tier == "free":
        return VARS_BY_TIER.get("free", [])
    elif tier == "premium":
        return VARS_BY_TIER.get("free", []) + VARS_BY_TIER.get("premium", [])
    elif tier == "business":
        return list(_VARIABLES_LIST)
    return []


def get_all_variables() -> List[GUSVariable]:
    """Get all registered variables."""
    return list(_VARIABLES_LIST)


def get_all_var_ids() -> Dict[str, str]:
    """Get key->var_id mapping (compat with gus_api.py VARS dict)."""
    return {var.key: var.var_id for var in _VARIABLES_LIST}


def get_powiat_level_keys() -> List[str]:
    """Get list of variable keys available only at powiat level."""
    return [var.key for var in _VARIABLES_LIST if var.level == "powiat"]


def get_unit_id_for_variable(key: str) -> str:
    """Get appropriate unit_id for a variable (gmina Rybno or powiat)."""
    var = VARS_BY_KEY.get(key)
    if var and var.level == "powiat":
        return UNIT_ID_POWIAT
    return UNIT_IDS["Rybno"]
