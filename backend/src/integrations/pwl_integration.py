"""
Integracja z Polska w Liczbach (polskawliczbach.pl)
Uzupełnienie danych GUS BDL o wskaźniki na poziomie gminy.

Źródło: https://www.polskawliczbach.pl/gmina_Rybno_warminsko_mazurskie
Metoda: Firecrawl API (scraping markdown) + MarkdownParser
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("PwL.Integration")

# ========================
# Konfiguracja gminy
# ========================

PWL_UNIT_ID = "042815403062"
PWL_UNIT_NAME = "Rybno"
PWL_URL = "https://www.polskawliczbach.pl/gmina_Rybno_warminsko_mazurskie"
PWL_DATA_YEAR = 2024  # Rok danych z aktualnego scrapowania

# ========================
# Whitelist pól do importu
# (tylko gmina-poziom, brak w GUS BDL lub unikalne)
# ========================

PWL_FIELD_WHITELIST: dict[str, list[str]] = {
    "demographics": [
        "average_age",
        "average_age_women",
        "average_age_men",
        "feminization_ratio",
        "marriages_per_1000",
        "marriages_2024",
        "divorces_per_1000",
        "natural_growth_per_1000",
    ],
    "real_estate": [
        "total_apartments",
        "apartments_per_1000",
        "avg_area_m2",
        "avg_area_per_person_m2",
        "avg_rooms_per_apartment",
        "persons_per_apartment",
        "new_apartments_2024",
        "new_apartments_per_1000",
        "new_avg_area_m2",
        "new_avg_rooms",
        "water_supply_pct",
        "flush_toilet_pct",
        "bathroom_pct",
        "central_heating_pct",
        "gas_network_pct",
    ],
    "labor_market": [
        "employed_total",
        "unemployment_rate",
        "salary_gross_pln",
        "salary_vs_poland_pct",
        "sector_agriculture_pct",
        "commute_out",
        "commute_in",
        "commute_balance",
    ],
    "education": [
        "kindergartens",
        "kindergarten_children",
        "primary_students",
        "high_schools",
        "high_school_students",
        "students_per_class",
    ],
    "safety": [
        "crimes_total",
        "crimes_per_1000",
        "crimes_criminal",
        "crimes_economic",
        "crimes_traffic",
        "crimes_against_life",
        "crimes_against_property",
        "detection_rate_total",
        "detection_rate_criminal",
        "detection_rate_property",
    ],
    "transport": [
        "accidents_total",
        "accidents_per_100k",
        "fatalities",
        "injured",
        "bike_paths_km",
        "bike_paths_per_10k_km2",
        "bike_paths_per_10k_people",
    ],
    "regon": [
        "entities_total",
        "natural_persons",
        "new_entities_2024",
        "deregistered_2024",
        "micro_enterprises",
        "small_enterprises",
        "medium_enterprises",
        "construction_count",
        "trade_count",
        "manufacturing_count",
        "transport_count",
    ],
}

# Pola budżetowe ze złożoną strukturą (historia wieloletnia + kategorie)
PWL_COMPLEX_FIELDS = [
    "budget_history",
    "budget_income_details",
    "budget_expenditure_details",
]

# Pola wykluczone z powodu błędów parsera lub złego formatu
PWL_EXCLUDED_FIELDS = {
    "working_age_percentage",
    "pre_working_age_percentage",
    "post_working_age_percentage",
    "higher_education_pct",
    "secondary_education_pct",
    "vocational_education_pct",
    "primary_education_pct",
    "preschool_per_1000_children",
}

# ========================
# Polskie nazwy pól
# ========================

FIELD_NAMES_PL: dict[str, str] = {
    # demographics
    "average_age": "Średni wiek mieszkańców (lata)",
    "average_age_women": "Średni wiek kobiet (lata)",
    "average_age_men": "Średni wiek mężczyzn (lata)",
    "feminization_ratio": "Współczynnik feminizacji (kobiety na 100 mężczyzn)",
    "marriages_per_1000": "Małżeństwa na 1000 ludności",
    "marriages_2024": "Małżeństwa zawarte (rok)",
    "divorces_per_1000": "Rozwody na 1000 ludności",
    "natural_growth_per_1000": "Przyrost naturalny na 1000 ludności",
    # real_estate
    "total_apartments": "Liczba mieszkań ogółem",
    "apartments_per_1000": "Mieszkania na 1000 ludności",
    "avg_area_m2": "Przeciętna powierzchnia mieszkania (m²)",
    "avg_area_per_person_m2": "Przeciętna powierzchnia na osobę (m²)",
    "avg_rooms_per_apartment": "Przeciętna liczba pokoi na mieszkanie",
    "persons_per_apartment": "Przeciętna liczba osób na mieszkanie",
    "new_apartments_2024": "Nowe mieszkania oddane (rok)",
    "new_apartments_per_1000": "Nowe mieszkania na 1000 ludności",
    "new_avg_area_m2": "Przeciętna pow. nowych mieszkań (m²)",
    "new_avg_rooms": "Przeciętna liczba pokoi w nowych mieszkaniach",
    "water_supply_pct": "Mieszkania z siecią wodociągową (%)",
    "flush_toilet_pct": "Mieszkania z ubikacją spłukiwaną (%)",
    "bathroom_pct": "Mieszkania z łazienką (%)",
    "central_heating_pct": "Mieszkania z centralnym ogrzewaniem (%)",
    "gas_network_pct": "Mieszkania z siecią gazową (%)",
    # labor_market
    "employed_total": "Pracujący ogółem (osoby)",
    "unemployment_rate": "Stopa bezrobocia rejestrowanego gmina (%)",
    "salary_gross_pln": "Przeciętne wynagrodzenie brutto gmina (PLN)",
    "salary_vs_poland_pct": "Wynagrodzenie vs średnia Polska (% poniżej/powyżej)",
    "sector_agriculture_pct": "Pracujący w rolnictwie (%)",
    "commute_out": "Pendlerzy wyjeżdżający z gminy (osoby)",
    "commute_in": "Pendlerzy przyjeżdżający do gminy (osoby)",
    "commute_balance": "Bilans pendlowania (osoby)",
    # education
    "kindergartens": "Liczba przedszkoli",
    "kindergarten_children": "Dzieci w przedszkolach (osoby)",
    "primary_students": "Uczniowie szkół podstawowych (osoby)",
    "high_schools": "Liczba szkół średnich",
    "high_school_students": "Uczniowie szkół średnich (osoby)",
    "students_per_class": "Uczniów na oddział klasowy",
    # safety
    "crimes_total": "Przestępstwa ogółem",
    "crimes_per_1000": "Przestępstwa na 1000 mieszkańców",
    "crimes_criminal": "Przestępstwa kryminalne",
    "crimes_economic": "Przestępstwa gospodarcze",
    "crimes_traffic": "Przestępstwa drogowe",
    "crimes_against_life": "Przestępstwa przeciwko życiu",
    "crimes_against_property": "Przestępstwa przeciwko mieniu",
    "detection_rate_total": "Wykrywalność przestępstw ogółem (%)",
    "detection_rate_criminal": "Wykrywalność przestępstw kryminalnych (%)",
    "detection_rate_property": "Wykrywalność przestępstw przeciwko mieniu (%)",
    # transport
    "accidents_total": "Wypadki drogowe ogółem (rok)",
    "accidents_per_100k": "Wypadki drogowe na 100 tys. ludności",
    "fatalities": "Ofiary śmiertelne wypadków drogowych",
    "injured": "Ranni w wypadkach drogowych",
    "bike_paths_km": "Ścieżki rowerowe (km)",
    "bike_paths_per_10k_km2": "Ścieżki rowerowe na 10 tys. km²",
    "bike_paths_per_10k_people": "Ścieżki rowerowe na 10 tys. ludności",
    # regon
    "entities_total": "Podmioty REGON ogółem",
    "natural_persons": "Osoby fizyczne prowadzące działalność",
    "new_entities_2024": "Nowo zarejestrowane podmioty (rok)",
    "deregistered_2024": "Wyrejestrowane podmioty (rok)",
    "micro_enterprises": "Mikroprzedsiębiorstwa (do 9 osób)",
    "small_enterprises": "Małe przedsiębiorstwa (10-49 osób)",
    "medium_enterprises": "Średnie przedsiębiorstwa (50-249 osób)",
    "construction_count": "Podmioty — budownictwo",
    "trade_count": "Podmioty — handel",
    "manufacturing_count": "Podmioty — produkcja",
    "transport_count": "Podmioty — transport",
    # complex / budget
    "budget_history": "Historia budżetu gminy (dochody i wydatki 2017-2024)",
    "budget_income_details": "Dochody budżetu wg kategorii klasyfikacji budżetowej",
    "budget_expenditure_details": "Wydatki budżetu wg kategorii klasyfikacji budżetowej",
}

# ========================
# Pola nakładające się z GUS BDL (do raportu porównawczego)
# ========================

GUS_OVERLAP_MAP = [
    # (section, pwl_field, gus_var_key, gus_var_id)
    ("demographics", "births_2024", "births_live", "59"),
    ("demographics", "deaths_2024", "deaths_total", "65"),
    ("demographics", "migration_balance", "migration_balance_total", "1365234"),
    ("demographics", "internal_registrations", "internal_migration_in", "269607"),
    ("demographics", "internal_deregistrations", "internal_migration_out", "269593"),
    ("labor_market", "employed_per_1000", "employed_per_1000", "454132"),
    ("finance", "budget_income_mln", "revenue_total", "76037"),
    ("finance", "budget_expenditure_mln", "expenditure_total", "1548644"),
    ("education", "primary_schools", "primary_schools", "838"),
]

# GUS population jest osobnym kluczem
GUS_POPULATION_VAR_ID = "72305"


# ========================
# Firecrawl client
# ========================

def scrape_pwl_sync(url: str = PWL_URL) -> str:
    """
    Synchroniczne scrapowanie strony przez Firecrawl API.
    Zwraca markdown zawartości strony.
    Wymaga FIRECRAWL_API_KEY w zmiennych środowiskowych.
    """
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY nie ustawiony w zmiennych środowiskowych")

    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        raise ImportError("Zainstaluj pakiet firecrawl: pip install firecrawl-py")

    app = FirecrawlApp(api_key=api_key)
    logger.info(f"Scrapowanie PwL: {url}")

    try:
        result = app.scrape_url(url, params={"onlyMainContent": True})
    except TypeError:
        result = app.scrape_url(url)

    if isinstance(result, dict):
        markdown = result.get("markdown", "")
    elif hasattr(result, "markdown"):
        markdown = result.markdown or ""
    else:
        markdown = ""

    if not markdown:
        raise ValueError(f"Brak treści markdown z {url}")

    logger.info(f"Pobrano {len(markdown)} znaków markdown z PwL")
    return markdown


async def scrape_pwl_async(url: str = PWL_URL) -> str:
    """Async wrapper dla scrape_pwl_sync (Firecrawl SDK jest synchroniczny)."""
    import asyncio
    return await asyncio.to_thread(scrape_pwl_sync, url)


# ========================
# Parser markdown → structured dict
# ========================

def _parse_float(value_str) -> Optional[float]:
    if value_str is None:
        return None
    clean = str(value_str).replace(",", ".").replace(" ", "").replace("\xa0", "").replace("%", "")
    try:
        return float(clean)
    except (ValueError, TypeError):
        return None


def _parse_int(value_str) -> Optional[int]:
    if value_str is None:
        return None
    clean = str(value_str).replace(" ", "").replace("\xa0", "")
    try:
        return int(clean)
    except (ValueError, TypeError):
        return None


def parse_pwl_markdown(markdown_text: str) -> dict:
    """
    Parsuje markdown z polskawliczbach.pl do strukturyzowanego słownika.
    Zaadaptowane z FIRECRAWL_polska_w_liczbach/scraping/parser.py
    """
    t = markdown_text

    def find_float(pattern):
        m = re.search(pattern, t)
        return _parse_float(m.group(1)) if m else None

    def find_int(pattern):
        m = re.search(pattern, t)
        return _parse_int(m.group(1)) if m else None

    result = {}

    # --- DEMOGRAPHICS ---
    demo = {}
    demo["population_total"] = find_int(r'([\d\s]+)\s*Liczba mieszkańców')
    demo["men_count"] = find_int(r'([\d\s]+)\s*Mężczyźni\b')
    demo["women_count"] = find_int(r'([\d\s]+)\s*Kobiety\b')
    demo["average_age"] = find_float(r'([\d,]+)\s*lat\s*Średni wiek mieszkańców')
    demo["average_age_women"] = find_float(r'([\d,]+)\s*lat\s*Kobiety\s*\(średni wiek\)')
    demo["average_age_men"] = find_float(r'([\d,]+)\s*lat\s*Mężczyźni\s*\(średni wiek\)')
    demo["feminization_ratio"] = find_int(r'(\d+)\s*Współczynnik feminizacji')
    demo["marriages_per_1000"] = find_float(r'([\d,]+)\s*Małżeństwa na 1000')
    demo["marriages_2024"] = find_int(r'(\d+)\s*Małżeństwa zawarte')
    demo["divorces_per_1000"] = find_float(r'([\d,]+)\s*Rozwody na 1000')
    demo["natural_growth"] = find_int(r'(-?\d+)\s*Przyrost naturalny\s*(?:w roku|\()')
    demo["natural_growth_per_1000"] = find_float(r'(-?[\d,]+)\s*Przyrost naturalny na 1000')
    demo["births_2024"] = find_int(r'(\d+)\s*Urodzenia żywe\b')
    demo["deaths_2024"] = find_int(r'(\d+)\s*Zgony\b')
    demo["migration_balance"] = find_int(r'(-?\d+)\s*Saldo migracji\b')
    demo["internal_registrations"] = find_int(r'(\d+)\s*Zameldowania w ruchu wewnętrznym')
    demo["internal_deregistrations"] = find_int(r'(\d+)\s*Wymeldowania w ruchu wewnętrznym')
    result["demographics"] = demo

    # --- REAL ESTATE ---
    re_data = {}
    re_data["total_apartments"] = find_int(r'([\d\s]+)\s*Liczba nieruchomości w \d+ roku')
    re_data["apartments_per_1000"] = find_float(r'([\d,]+)\s*Mieszkania na 1000 mieszkańców')
    re_data["avg_area_m2"] = find_float(r'([\d,]+)\s*m2\s*Przeciętna powierzchnia użytkowa 1 mieszkania')
    re_data["avg_area_per_person_m2"] = find_float(r'([\d,]+)\s*m2\s*Przeciętna powierzchnia użytkowa na 1 osobę')
    re_data["avg_rooms_per_apartment"] = find_float(r'([\d,]+)\s*Przeciętna liczba izb w 1 mieszkaniu')
    re_data["persons_per_apartment"] = find_float(r'([\d,]+)\s*Przeciętna liczba osób w 1 mieszkaniu')
    re_data["new_apartments_2024"] = find_int(r'(\d+)\s*Liczba nowych mieszkań')
    re_data["new_apartments_per_1000"] = find_float(r'([\d,]+)\s*Nowe mieszkania na 1000')
    re_data["new_avg_area_m2"] = find_float(r'([\d,]+)\s*m2\s*Przeciętna powierzchnia nowych')
    re_data["new_avg_rooms"] = find_float(r'([\d,]+)\s*Przeciętna liczba izb w nowych')
    re_data["water_supply_pct"] = find_float(r'([\d,]+)%?\s*Mieszkania wyposażone w sieć wodociągową')
    re_data["flush_toilet_pct"] = find_float(r'([\d,]+)%?\s*Mieszkania wyposażone w ubikację spłukiwaną')
    re_data["bathroom_pct"] = find_float(r'([\d,]+)%?\s*Mieszkania wyposażone w łazienkę')
    re_data["central_heating_pct"] = find_float(r'([\d,]+)%?\s*Mieszkania wyposażone w centralne ogrzewanie')
    re_data["gas_network_pct"] = find_float(r'([\d,]+)%?\s*Mieszkania wyposażone w sieć gazową')
    result["real_estate"] = re_data

    # --- FINANCE ---
    fin = {}
    fin["budget_income_mln"] = find_float(r'([\d,]+)\s*mln PLN\s*Dochody')
    fin["budget_expenditure_mln"] = find_float(r'([\d,]+)\s*mln PLN\s*Wydatki')
    fin["income_per_capita"] = find_int(r'(\d+)\s*PLN\s*Dochód na mieszkańca')
    fin["expenditure_per_capita"] = find_int(r'(\d+)\s*PLN\s*Wydatek na mieszkańca')
    result["finance"] = fin

    # --- LABOR MARKET ---
    labor = {}
    labor["employed_per_1000"] = find_int(r'(\d+)\s*Pracujący na 1000 ludności')
    labor["employed_total"] = find_int(r'([\d\s]+)\s*Pracujący ogółem')
    labor["unemployment_rate"] = find_float(r'([\d,]+)%?\s*Stopa bezrobocia rejestrowanego')
    labor["salary_gross_pln"] = find_float(r'([\d,]+)\s*PLN\s*Przeciętne wynagrodzenie brutto')
    labor["salary_vs_poland_pct"] = find_float(r'([\d,]+)%?\s*(?:poniżej|powyżej)\s*średniej krajowej')
    labor["sector_agriculture_pct"] = find_float(r'([\d,]+)%?\s*Pracujący w rolnictwie')
    labor["commute_out"] = find_int(r'(\d+)\s*Wyjeżdżający do pracy')
    labor["commute_in"] = find_int(r'(\d+)\s*Przyjeżdżający do pracy')
    labor["commute_balance"] = find_int(r'(-?\d+)\s*Bilans dojazdów do pracy')
    result["labor_market"] = labor

    # --- EDUCATION ---
    edu = {}
    edu["kindergartens"] = find_int(r'(\d+)\s*Przedszkola\b')
    edu["kindergarten_children"] = find_int(r'(\d+)\s*Dzieci w przedszkolach')
    edu["primary_schools"] = find_int(r'(\d+)\s*Szkoły podstawowe\b')
    edu["primary_students"] = find_int(r'(\d+)\s*Uczniowie szkół podstawowych')
    edu["high_schools"] = find_int(r'(\d+)\s*Szkoły średnie\b')
    edu["high_school_students"] = find_int(r'(\d+)\s*Uczniowie szkół średnich')
    edu["students_per_class"] = find_float(r'([\d,]+)\s*Uczniów na oddział')
    result["education"] = edu

    # --- SAFETY ---
    safety = {}
    safety["crimes_total"] = find_int(r'(\d+)\s*Przestępstwa ogółem\b')
    safety["crimes_per_1000"] = find_float(r'([\d,]+)\s*Przestępstwa na 1000')
    safety["crimes_criminal"] = find_int(r'(\d+)\s*Przestępstwa kryminalne\b')
    safety["crimes_economic"] = find_int(r'(\d+)\s*Przestępstwa gospodarcze\b')
    safety["crimes_traffic"] = find_int(r'(\d+)\s*Przestępstwa drogowe\b')
    safety["crimes_against_life"] = find_int(r'(\d+)\s*Przestępstwa przeciwko życiu')
    safety["crimes_against_property"] = find_int(r'(\d+)\s*Przestępstwa przeciwko mieniu')
    safety["detection_rate_total"] = find_float(r'([\d,]+)%?\s*Wykrywalność ogółem')
    safety["detection_rate_criminal"] = find_float(r'([\d,]+)%?\s*Wykrywalność kryminalnych')
    safety["detection_rate_property"] = find_float(r'([\d,]+)%?\s*Wykrywalność przeciwko mieniu')
    result["safety"] = safety

    # --- TRANSPORT ---
    transport = {}
    transport["accidents_total"] = find_int(r'(\d+)\s*Wypadki drogowe\b')
    transport["accidents_per_100k"] = find_float(r'([\d,]+)\s*Wypadki na 100')
    transport["fatalities"] = find_int(r'(\d+)\s*Ofiary śmiertelne\b')
    transport["injured"] = find_int(r'(\d+)\s*Ranni\b')
    transport["bike_paths_km"] = find_float(r'([\d,]+)\s*km\s*Ścieżki rowerowe\b')
    transport["bike_paths_per_10k_km2"] = find_float(r'([\d,]+)\s*Ścieżki rowerowe na 10 tys\. km')
    transport["bike_paths_per_10k_people"] = find_float(r'([\d,]+)\s*Ścieżki rowerowe na 10 tys\. mieszk')
    result["transport"] = transport

    # --- REGON ---
    regon = {}
    regon["entities_total"] = find_int(r'(\d+)\s*Liczba podmiotów REGON\b')
    regon["natural_persons"] = find_int(r'(\d+)\s*Osoby fizyczne\b')
    regon["new_entities_2024"] = find_int(r'(\d+)\s*Nowo zarejestrowane\b')
    regon["deregistered_2024"] = find_int(r'(\d+)\s*Wyrejestrowane\b')
    regon["micro_enterprises"] = find_int(r'(\d+)\s*Mikroprzedsiębiorstwa\b')
    regon["small_enterprises"] = find_int(r'(\d+)\s*Małe przedsiębiorstwa\b')
    regon["medium_enterprises"] = find_int(r'(\d+)\s*Średnie przedsiębiorstwa\b')
    regon["construction_count"] = find_int(r'(\d+)\s*Budownictwo\b')
    regon["trade_count"] = find_int(r'(\d+)\s*Handel\b')
    regon["manufacturing_count"] = find_int(r'(\d+)\s*Produkcja\b')
    regon["transport_count"] = find_int(r'(\d+)\s*Transport\b')
    result["regon"] = regon

    return result


def parse_pwl_from_json(json_data: dict) -> dict:
    """
    Odczytuje dane z istniejącego rybno_data.json (structured_data).
    Używane przy imporcie z pliku (bez scrapowania).
    """
    return json_data.get("structured_data", json_data)


# ========================
# Raport porównawczy GUS vs PwL
# ========================

async def generate_comparison_report(pwl_data: dict, db: AsyncSession) -> list[dict]:
    """
    Porównuje dane PwL z istniejącymi danymi GUS w gus_gmina_stats.
    Zwraca listę słowników z polami: field, gus_value, gus_year, pwl_value, diff_pct, match.
    """
    report = []

    # Sprawdź ludność (specjalny case)
    pop_gus = await db.execute(
        text("""
            SELECT value, year FROM gus_gmina_stats
            WHERE unit_id = :uid AND var_id = :vid
            ORDER BY year DESC LIMIT 1
        """),
        {"uid": PWL_UNIT_ID, "vid": GUS_POPULATION_VAR_ID}
    )
    pop_row = pop_gus.fetchone()
    pwl_pop = pwl_data.get("demographics", {}).get("population_total")

    if pop_row and pwl_pop is not None:
        gus_val = pop_row[0]
        gus_year = pop_row[1]
        diff = abs(gus_val - pwl_pop) / gus_val * 100 if gus_val else 0
        report.append({
            "field": "population_total",
            "section": "demographics",
            "field_name": "Ludność ogółem",
            "gus_value": gus_val,
            "gus_year": gus_year,
            "pwl_value": pwl_pop,
            "diff_pct": round(diff, 2),
            "match": diff < 1.0,
        })

    # Pozostałe nakładające się pola
    section_map = {
        "demographics": pwl_data.get("demographics", {}),
        "labor_market": pwl_data.get("labor_market", {}),
        "education": pwl_data.get("education", {}),
        "finance": pwl_data.get("finance", {}),
    }

    finance_multiplier = {
        "budget_income_mln": 1_000_000,
        "budget_expenditure_mln": 1_000_000,
    }

    for section, pwl_field, gus_var_key, gus_var_id in GUS_OVERLAP_MAP:
        pwl_section_data = section_map.get(section, {})
        pwl_val = pwl_section_data.get(pwl_field)
        if pwl_val is None:
            continue

        # Konwersja mln → PLN dla finansów
        if pwl_field in finance_multiplier:
            pwl_val = pwl_val * finance_multiplier[pwl_field]

        gus_row = await db.execute(
            text("""
                SELECT value, year FROM gus_gmina_stats
                WHERE unit_id = :uid AND var_id = :vid
                ORDER BY year DESC LIMIT 1
            """),
            {"uid": PWL_UNIT_ID, "vid": gus_var_id}
        )
        row = gus_row.fetchone()

        if row is None:
            report.append({
                "field": pwl_field,
                "section": section,
                "field_name": FIELD_NAMES_PL.get(pwl_field, pwl_field),
                "gus_value": None,
                "gus_year": None,
                "pwl_value": pwl_val,
                "diff_pct": None,
                "match": None,
                "note": "Brak danych GUS w bazie",
            })
            continue

        gus_val, gus_year = row
        if gus_val is None:
            continue

        diff = abs(gus_val - pwl_val) / abs(gus_val) * 100 if gus_val else 0
        report.append({
            "field": pwl_field,
            "section": section,
            "field_name": FIELD_NAMES_PL.get(pwl_field, pwl_field),
            "gus_value": gus_val,
            "gus_year": gus_year,
            "pwl_value": pwl_val,
            "diff_pct": round(diff, 2),
            "match": diff < 1.0,
        })

    return report


# ========================
# Import do bazy danych
# ========================

def flatten_pwl_data(pwl_data: dict, year: int = PWL_DATA_YEAR) -> list[dict]:
    """
    Spłaszcza strukturę pwl_data do listy rekordów gotowych do wstawienia do DB.
    Każdy rekord to: {unit_id, unit_name, section, field_key, field_name_pl, year, value, extra_data, source_url}
    """
    records = []

    for section, allowed_fields in PWL_FIELD_WHITELIST.items():
        section_data = pwl_data.get(section, {})
        if not section_data:
            continue

        for field_key in allowed_fields:
            if field_key in PWL_EXCLUDED_FIELDS:
                continue

            value = section_data.get(field_key)
            if value is None:
                continue

            # Walidacja: odrzuć wartości wyglądające jak błędy parsera
            if isinstance(value, (int, float)):
                # Reject absurdalne wartości procentowe
                if "pct" in field_key and (value > 100.5 or value < 0):
                    logger.warning(f"Odrzucono podejrzaną wartość: {field_key}={value}")
                    continue

            records.append({
                "unit_id": PWL_UNIT_ID,
                "unit_name": PWL_UNIT_NAME,
                "section": section,
                "field_key": field_key,
                "field_name_pl": FIELD_NAMES_PL.get(field_key, field_key),
                "year": year,
                "value": float(value) if isinstance(value, (int, float)) else None,
                "extra_data": None,
                "source_url": PWL_URL,
            })

    # Dane budżetowe (historia wieloletnia) — jako extra_data
    finance_data = pwl_data.get("finance", {})
    if finance_data:
        budget_history = finance_data.get("budget_history")
        if budget_history:
            records.append({
                "unit_id": PWL_UNIT_ID,
                "unit_name": PWL_UNIT_NAME,
                "section": "finance",
                "field_key": "budget_history",
                "field_name_pl": FIELD_NAMES_PL["budget_history"],
                "year": year,
                "value": None,
                "extra_data": {"history": budget_history},
                "source_url": PWL_URL,
            })

        income_details = finance_data.get("budget_income_details")
        if income_details:
            records.append({
                "unit_id": PWL_UNIT_ID,
                "unit_name": PWL_UNIT_NAME,
                "section": "finance",
                "field_key": "budget_income_details",
                "field_name_pl": FIELD_NAMES_PL["budget_income_details"],
                "year": year,
                "value": None,
                "extra_data": {"categories": income_details},
                "source_url": PWL_URL,
            })

        expenditure_details = finance_data.get("budget_expenditure_details")
        if expenditure_details:
            records.append({
                "unit_id": PWL_UNIT_ID,
                "unit_name": PWL_UNIT_NAME,
                "section": "finance",
                "field_key": "budget_expenditure_details",
                "field_name_pl": FIELD_NAMES_PL["budget_expenditure_details"],
                "year": year,
                "value": None,
                "extra_data": {"categories": expenditure_details},
                "source_url": PWL_URL,
            })

    return records


async def import_to_db(
    records: list[dict],
    db: AsyncSession,
    log_id: Optional[int] = None,
    is_verified: bool = False,
) -> tuple[int, int]:
    """
    Wstawia rekordy do pwl_gmina_stats (upsert).
    Zwraca (imported_count, updated_count).
    """
    imported = 0
    updated = 0
    now = datetime.utcnow()

    for rec in records:
        # Sprawdź czy rekord już istnieje
        existing = await db.execute(
            text("""
                SELECT id FROM pwl_gmina_stats
                WHERE unit_id = :uid AND section = :sec AND field_key = :fk AND year = :yr
            """),
            {"uid": rec["unit_id"], "sec": rec["section"], "fk": rec["field_key"], "yr": rec["year"]}
        )
        row = existing.fetchone()

        if row:
            await db.execute(
                text("""
                    UPDATE pwl_gmina_stats
                    SET value = :val,
                        extra_data = CAST(:extra AS jsonb),
                        field_name_pl = :name,
                        source_url = :url,
                        is_verified = :verified,
                        scrape_log_id = :log_id,
                        fetched_at = :now
                    WHERE id = :id
                """),
                {
                    "val": rec["value"],
                    "extra": json.dumps(rec["extra_data"], ensure_ascii=False) if rec["extra_data"] is not None else None,
                    "name": rec["field_name_pl"],
                    "url": rec["source_url"],
                    "verified": is_verified,
                    "log_id": log_id,
                    "now": now,
                    "id": row[0],
                }
            )
            updated += 1
        else:
            await db.execute(
                text("""
                    INSERT INTO pwl_gmina_stats
                        (unit_id, unit_name, section, field_key, field_name_pl,
                         year, value, extra_data, source_url,
                         is_verified, scrape_log_id, fetched_at)
                    VALUES
                        (:uid, :uname, :sec, :fk, :name,
                         :yr, :val, CAST(:extra AS jsonb), :url,
                         :verified, :log_id, :now)
                """),
                {
                    "uid": rec["unit_id"],
                    "uname": rec["unit_name"],
                    "sec": rec["section"],
                    "fk": rec["field_key"],
                    "name": rec["field_name_pl"],
                    "yr": rec["year"],
                    "val": rec["value"],
                    "extra": json.dumps(rec["extra_data"], ensure_ascii=False) if rec["extra_data"] is not None else None,
                    "url": rec["source_url"],
                    "verified": is_verified,
                    "log_id": log_id,
                    "now": now,
                }
            )
            imported += 1

    await db.commit()
    return imported, updated


async def promote_to_verified(unit_id: str, log_id: int, db: AsyncSession) -> int:
    """Zatwierdza rekordy z danego scrape_log_id (is_verified = True)."""
    result = await db.execute(
        text("""
            UPDATE pwl_gmina_stats
            SET is_verified = true
            WHERE unit_id = :uid AND scrape_log_id = :log_id AND is_verified = false
            RETURNING id
        """),
        {"uid": unit_id, "log_id": log_id}
    )
    rows = result.fetchall()
    await db.commit()
    return len(rows)
