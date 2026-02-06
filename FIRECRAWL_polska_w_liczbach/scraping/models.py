from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class BudgetDepartment(BaseModel):
    name: str
    code: str
    history: List[Dict[str, Any]] = [] # [{"year": 2017, "value": 1000.0, "percent": 0.5}, ...]

class Demographics(BaseModel):
    population_total: Optional[int] = None
    population_history: List[Dict[str, int]] = []
    men_count: Optional[int] = None
    women_count: Optional[int] = None
    men_percentage: Optional[float] = None
    women_percentage: Optional[float] = None
    average_age: Optional[float] = None
    average_age_women: Optional[float] = None
    average_age_men: Optional[float] = None
    feminization_ratio: Optional[int] = None  # 97 kobiet na 100 mężczyzn
    
    # Marital status
    marriages_per_1000: Optional[float] = None
    divorces_per_1000: Optional[float] = None
    marriages_2024: Optional[int] = None
    
    # Natural growth
    natural_growth: Optional[int] = None
    natural_growth_per_1000: Optional[float] = None
    births_2024: Optional[int] = None
    deaths_2024: Optional[int] = None
    
    # Migration
    migration_balance: Optional[int] = None
    internal_registrations: Optional[int] = None
    internal_deregistrations: Optional[int] = None
    
    # Age groups
    working_age_percentage: Optional[float] = None
    pre_working_age_percentage: Optional[float] = None
    post_working_age_percentage: Optional[float] = None

class RealEstate(BaseModel):
    # Total resources
    total_apartments: Optional[int] = None
    apartments_per_1000: Optional[float] = None
    avg_area_m2: Optional[float] = None
    avg_area_per_person_m2: Optional[float] = None
    avg_rooms_per_apartment: Optional[float] = None
    persons_per_apartment: Optional[float] = None
    
    # New construction
    new_apartments_2024: Optional[int] = None
    new_apartments_per_1000: Optional[float] = None
    new_avg_area_m2: Optional[float] = None
    new_avg_rooms: Optional[float] = None
    
    # Infrastructure percentages
    water_supply_pct: Optional[float] = None
    flush_toilet_pct: Optional[float] = None
    bathroom_pct: Optional[float] = None
    central_heating_pct: Optional[float] = None
    gas_network_pct: Optional[float] = None

class Finance(BaseModel):
    # Budget totals
    budget_income_mln: Optional[float] = None
    budget_expenditure_mln: Optional[float] = None
    budget_history: List[Dict[str, Any]] = []
    
    # Detailed breakdown
    budget_income_details: List[BudgetDepartment] = []
    budget_expenditure_details: List[BudgetDepartment] = []

    income_per_capita: Optional[float] = None
    expenditure_per_capita: Optional[float] = None
    
    # Year-over-year changes
    income_change_pct: Optional[float] = None
    expenditure_change_pct: Optional[float] = None
    
    # Expenditure breakdown (%)
    education_expenditure_pct: Optional[float] = None  # Dział 801
    transport_expenditure_pct: Optional[float] = None  # Dział 600
    admin_expenditure_pct: Optional[float] = None      # Dział 750
    social_expenditure_pct: Optional[float] = None     # Dział 852
    agriculture_expenditure_pct: Optional[float] = None  # Dział 010
    
    # Investment
    investment_expenditure_mln: Optional[float] = None
    investment_pct: Optional[float] = None
    
    # Income sources (%)
    rozliczenia_pct: Optional[float] = None  # Dział 758
    taxes_pct: Optional[float] = None        # Dział 756

class LaborMarket(BaseModel):
    # Employment
    employed_per_1000: Optional[int] = None
    employed_total: Optional[int] = None
    employed_women: Optional[int] = None
    employed_men: Optional[int] = None
    
    # Unemployment
    unemployment_rate: Optional[float] = None
    unemployment_rate_women: Optional[float] = None
    unemployment_rate_men: Optional[float] = None
    
    # Salary
    salary_gross_pln: Optional[float] = None
    salary_vs_poland_pct: Optional[float] = None
    
    # Sectors (%)
    sector_agriculture_pct: Optional[float] = None
    sector_industry_pct: Optional[float] = None
    sector_services_pct: Optional[float] = None
    sector_finance_pct: Optional[float] = None
    
    # Commuting
    commute_out: Optional[int] = None
    commute_in: Optional[int] = None
    commute_balance: Optional[int] = None

class Education(BaseModel):
    # Schools count
    kindergartens: Optional[int] = None
    kindergarten_children: Optional[int] = None
    primary_schools: Optional[int] = None
    primary_students: Optional[int] = None
    high_schools: Optional[int] = None
    high_school_students: Optional[int] = None
    vocational_schools: Optional[int] = None
    vocational_students: Optional[int] = None
    
    # Ratios
    students_per_class: Optional[float] = None
    preschool_per_1000_children: Optional[int] = None
    
    # Education level (%)
    higher_education_pct: Optional[float] = None
    secondary_education_pct: Optional[float] = None
    vocational_education_pct: Optional[float] = None
    primary_education_pct: Optional[float] = None

class Safety(BaseModel):
    # Crimes
    crimes_total: Optional[int] = None
    crimes_per_1000: Optional[float] = None
    crimes_criminal: Optional[int] = None
    crimes_economic: Optional[int] = None
    crimes_traffic: Optional[int] = None
    crimes_against_life: Optional[int] = None
    crimes_against_property: Optional[int] = None
    
    # Detection rates
    detection_rate_total: Optional[float] = None
    detection_rate_criminal: Optional[float] = None
    detection_rate_property: Optional[float] = None

class Transport(BaseModel):
    # Accidents
    accidents_total: Optional[int] = None
    accidents_history: List[Dict[str, int]] = []
    accidents_per_100k: Optional[float] = None
    fatalities: Optional[int] = None
    injured: Optional[int] = None
    
    # Infrastructure
    bike_paths_km: Optional[float] = None
    bike_paths_per_10k_km2: Optional[float] = None
    bike_paths_per_10k_people: Optional[float] = None

class REGON(BaseModel):
    entities_total: Optional[int] = None
    natural_persons: Optional[int] = None
    new_entities_2024: Optional[int] = None
    deregistered_2024: Optional[int] = None
    
    # By size
    micro_enterprises: Optional[int] = None  # 0-9
    small_enterprises: Optional[int] = None  # 10-49
    medium_enterprises: Optional[int] = None  # 50-249
    
    # By sector
    construction_count: Optional[int] = None
    trade_count: Optional[int] = None
    manufacturing_count: Optional[int] = None
    transport_count: Optional[int] = None

class BasicInfo(BaseModel):
    name: str = "Gmina Rybno"
    teryt_code: Optional[str] = None
    area_km2: Optional[float] = None
    population_density: Optional[float] = None
    voivodeship: str = "warmińsko-mazurskie"
    powiat: str = "działdowski"
    gmina_type: str = "wiejska"
    mayor: Optional[str] = None
    phone_code: Optional[str] = None

class GminaStats(BaseModel):
    basic_info: BasicInfo = BasicInfo()
    demographics: Demographics = Demographics()
    real_estate: RealEstate = RealEstate()
    finance: Finance = Finance()
    labor_market: LaborMarket = LaborMarket()
    education: Education = Education()
    safety: Safety = Safety()
    transport: Transport = Transport()
    regon: REGON = REGON()
    
    # Metadata
    source_url: str = "https://www.polskawliczbach.pl/gmina_Rybno_warminsko_mazurskie"
    data_year: int = 2024
