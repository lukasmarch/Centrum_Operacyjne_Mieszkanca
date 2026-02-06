import re
from models import (
    GminaStats, BasicInfo, Demographics, RealEstate, Finance,
    LaborMarket, Education, Safety, Transport, REGON, BudgetDepartment
)

def parse_float(value_str):
    """Parse Polish-formatted float (comma as decimal separator)."""
    if not value_str:
        return None
    clean_str = value_str.replace(',', '.').replace(' ', '').replace('%', '').replace('\xa0', '')
    try:
        return float(clean_str)
    except ValueError:
        return None

def parse_int(value_str):
    """Parse integer, removing spaces and non-breaking spaces."""
    if not value_str:
        return None
    clean_str = value_str.replace(' ', '').replace('\xa0', '')
    try:
        return int(clean_str)
    except ValueError:
        return None

class MarkdownParser:
    def __init__(self, markdown_text):
        self.text = markdown_text

    def parse(self) -> GminaStats:
        stats = GminaStats()
        
        self._parse_basic_info(stats)
        self._parse_demographics(stats)
        self._parse_real_estate(stats)
        self._parse_finance(stats)
        self._parse_labor_market(stats)
        self._parse_education(stats)
        self._parse_safety(stats)
        self._parse_transport(stats)
        self._parse_regon(stats)
        
        return stats

    def _parse_basic_info(self, stats: GminaStats):
        """Parse basic municipality info."""
        info = stats.basic_info
        
        # TERYT code: "TERYT (TERC) 2803062"
        teryt = re.search(r'TERYT \(TERC\)\s*(\d+)', self.text)
        if teryt:
            info.teryt_code = teryt.group(1)
        
        # Area: "148,4 km² Powierzchnia"
        area = re.search(r'(\d+[,\.]\d+)\s*km[²2]\s*Powierzchnia', self.text)
        if area:
            info.area_km2 = parse_float(area.group(1))
        
        # Density: "46 osób/km² Gęstość zaludnienia"
        density = re.search(r'(\d+)\s*osób/km[²2]\s*Gęstość', self.text)
        if density:
            info.population_density = parse_int(density.group(1))
        
        # Mayor: "Tomasz Węgrzynowski Wójt gminy"
        mayor = re.search(r'([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)\s*Wójt', self.text)
        if mayor:
            info.mayor = mayor.group(1)
        
        # Phone code: "(+48) 23 Numer kierunkowy"
        phone = re.search(r'\(\+48\)\s*(\d+)\s*Numer kierunkowy', self.text)
        if phone:
            info.phone_code = phone.group(1)

    def _parse_demographics(self, stats: GminaStats):
        """Parse demographic data."""
        demo = stats.demographics
        
        # Population: "6 693 Liczba mieszkańców"
        pop = re.search(r'([\d\s]+)\s*Liczba mieszkańców', self.text)
        if pop:
            demo.population_total = parse_int(pop.group(1))
        
        # Gender counts
        women = re.search(r'([\d\s]+)\s*Kobiety\b', self.text)
        if women:
            demo.women_count = parse_int(women.group(1))
        
        men = re.search(r'([\d\s]+)\s*Mężczyźni\b', self.text)
        if men:
            demo.men_count = parse_int(men.group(1))
        
        # Gender percentages: "49,3% stanowią kobiety"
        women_pct = re.search(r'([\d,]+)%\s*stanowią kobiety', self.text)
        if women_pct:
            demo.women_percentage = parse_float(women_pct.group(1))
            demo.men_percentage = 100.0 - demo.women_percentage if demo.women_percentage else None
        
        # Average age: "40,6 lat Średni wiek mieszkańców"
        avg_age = re.search(r'([\d,]+)\s*lat\s*Średni wiek mieszkańców', self.text)
        if avg_age:
            demo.average_age = parse_float(avg_age.group(1))
        
        # Age by gender
        age_women = re.search(r'([\d,]+)\s*lat\s*Kobiety\s*\(średni wiek\)', self.text)
        if age_women:
            demo.average_age_women = parse_float(age_women.group(1))
        
        age_men = re.search(r'([\d,]+)\s*lat\s*Mężczyźni\s*\(średni wiek\)', self.text)
        if age_men:
            demo.average_age_men = parse_float(age_men.group(1))
        
        # Feminization ratio: "97 Współczynnik feminizacji"
        fem_ratio = re.search(r'(\d+)\s*Współczynnik feminizacji', self.text)
        if fem_ratio:
            demo.feminization_ratio = parse_int(fem_ratio.group(1))
        
        # Marriages: "2,7 Małżeństwa na 1000 ludności"
        marriages = re.search(r'([\d,]+)\s*Małżeństwa na 1000', self.text)
        if marriages:
            demo.marriages_per_1000 = parse_float(marriages.group(1))
        
        # Number of marriages: "18 Małżeństwa zawarte"
        marriages_count = re.search(r'(\d+)\s*Małżeństwa zawarte', self.text)
        if marriages_count:
            demo.marriages_2024 = parse_int(marriages_count.group(1))
        
        # Divorces: "1,8 Rozwody na 1000"
        divorces = re.search(r'([\d,]+)\s*Rozwody na 1000', self.text)
        if divorces:
            demo.divorces_per_1000 = parse_float(divorces.group(1))
        
        # Natural growth: "-23 Przyrost naturalny"
        growth = re.search(r'(-?\d+)\s*Przyrost naturalny\s*(?:w roku|\()', self.text)
        if growth:
            demo.natural_growth = parse_int(growth.group(1))
        
        # Natural growth per 1000: "-3,44 Przyrost naturalny na 1000"
        growth_rate = re.search(r'(-?[\d,]+)\s*Przyrost naturalny na 1000', self.text)
        if growth_rate:
            demo.natural_growth_per_1000 = parse_float(growth_rate.group(1))
        
        # Births: "47 Urodzenia żywe"
        births = re.search(r'(\d+)\s*Urodzenia żywe\b', self.text)
        if births:
            demo.births_2024 = parse_int(births.group(1))
        
        # Deaths: "70 Zgony"
        deaths = re.search(r'(\d+)\s*Zgony\b', self.text)
        if deaths:
            demo.deaths_2024 = parse_int(deaths.group(1))
        
        # Migration
        mig_balance = re.search(r'(-?\d+)\s*Saldo migracji\b', self.text)
        if mig_balance:
            demo.migration_balance = parse_int(mig_balance.group(1))
        
        internal_in = re.search(r'(\d+)\s*Zameldowania w ruchu wewnętrznym', self.text)
        if internal_in:
            demo.internal_registrations = parse_int(internal_in.group(1))
        
        internal_out = re.search(r'(\d+)\s*Wymeldowania w ruchu wewnętrznym', self.text)
        if internal_out:
            demo.internal_deregistrations = parse_int(internal_out.group(1))
        
        # Age groups: "59,8% W wieku produkcyjnym"
        working_age = re.search(r'[\d\s]+([\d,]+)%\s*W wieku produkcyjnym\b', self.text)
        if working_age:
            demo.working_age_percentage = parse_float(working_age.group(1))
        
        pre_working = re.search(r'[\d\s]+([\d,]+)%\s*W wieku przedprodukcyjnym', self.text)
        if pre_working:
            demo.pre_working_age_percentage = parse_float(pre_working.group(1))
        
        post_working = re.search(r'[\d\s]+([\d,]+)%\s*W wieku poprodukcyjnym', self.text)
        if post_working:
            demo.post_working_age_percentage = parse_float(post_working.group(1))

        # Parse historical data
        self._parse_historical_demographics(stats)

    def _parse_real_estate(self, stats: GminaStats):
        """Parse real estate and housing data."""
        re_data = stats.real_estate
        
        # Total apartments: "2 159 Liczba nieruchomości"
        total = re.search(r'([\d\s]+)\s*Liczba nieruchomości w \d+ roku', self.text)
        if total:
            re_data.total_apartments = parse_int(total.group(1))
        
        # Per 1000: "323,10 Mieszkania na 1000"
        per_1000 = re.search(r'([\d,]+)\s*Mieszkania na 1000 mieszkańców', self.text)
        if per_1000:
            re_data.apartments_per_1000 = parse_float(per_1000.group(1))
        
        # Average area: "85,50 m2 Przeciętna powierzchnia użytkowa 1 mieszkania"
        avg_area = re.search(r'([\d,]+)\s*m2\s*Przeciętna powierzchnia użytkowa 1 mieszkania', self.text)
        if avg_area:
            re_data.avg_area_m2 = parse_float(avg_area.group(1))
        
        # Area per person: "27,60 m2 Przeciętna powierzchnia użytkowa mieszkania na 1 osobę"
        area_per_person = re.search(r'([\d,]+)\s*m2\s*Przeciętna powierzchnia użytkowa mieszkania na 1 osobę', self.text)
        if area_per_person:
            re_data.avg_area_per_person_m2 = parse_float(area_per_person.group(1))
        
        # Rooms: "4,60 Przeciętna liczba izb"
        rooms = re.search(r'([\d,]+)\s*Przeciętna liczba izb w 1 mieszkaniu', self.text)
        if rooms:
            re_data.avg_rooms_per_apartment = parse_float(rooms.group(1))
        
        # Persons per apartment: "3,09 Przeciętna liczba osób na 1 mieszkanie"
        persons = re.search(r'([\d,]+)\s*Przeciętna liczba osób na 1 mieszkanie', self.text)
        if persons:
            re_data.persons_per_apartment = parse_float(persons.group(1))
        
        # New apartments: "8 Liczba nieruchomości oddanych do użytkowania"
        new_apts = re.search(r'(\d+)\s*Liczba nieruchomości oddanych do użytkowania', self.text)
        if new_apts:
            re_data.new_apartments_2024 = parse_int(new_apts.group(1))
        
        # New per 1000: "1,20 Liczba mieszkań na 1000 mieszkańców"
        new_per_1000 = re.search(r'([\d,]+)\s*Liczba mieszkań na 1000 mieszkańców\s*\(oddanych', self.text)
        if new_per_1000:
            re_data.new_apartments_per_1000 = parse_float(new_per_1000.group(1))
        
        # New average area: "112,8 m2 Przeciętna powierzchnia użytkowa nieruchomości"
        new_area = re.search(r'([\d,]+)\s*m2\s*Przeciętna powierzchnia użytkowa nieruchomości\s*\(oddanej', self.text)
        if new_area:
            re_data.new_avg_area_m2 = parse_float(new_area.group(1))
        
        # New average rooms: "5,00 Przeciętna liczba izb w lokalu"
        new_rooms = re.search(r'([\d,]+)\s*Przeciętna liczba izb w lokalu\s*\(oddanego', self.text)
        if new_rooms:
            re_data.new_avg_rooms = parse_float(new_rooms.group(1))
        
        # Infrastructure percentages
        water = re.search(r'([\d,]+)%\s*Mieszkania wyposażone.*?wodociąg', self.text)
        if water:
            re_data.water_supply_pct = parse_float(water.group(1))
        
        toilet = re.search(r'([\d,]+)%\s*Mieszkania wyposażone.*?ustęp spłukiwany', self.text)
        if toilet:
            re_data.flush_toilet_pct = parse_float(toilet.group(1))
        
        bathroom = re.search(r'([\d,]+)%\s*Mieszkania wyposażone.*?łazienka', self.text)
        if bathroom:
            re_data.bathroom_pct = parse_float(bathroom.group(1))
        
        heating = re.search(r'([\d,]+)%\s*Mieszkania wyposażone.*?centralne ogrzewanie', self.text)
        if heating:
            re_data.central_heating_pct = parse_float(heating.group(1))
        
        gas = re.search(r'([\d,]+)%\s*Mieszkania wyposażone.*?gaz sieciowy', self.text)
        if gas:
            re_data.gas_network_pct = parse_float(gas.group(1))

    def _parse_finance(self, stats: GminaStats):
        """Parse public finance data."""
        fin = stats.finance
        
        # Expenditure: "62,0 mln złotych"
        exp = re.search(r'wydatków.*?wyniosła.*?([\d,]+)\s*mln', self.text)
        if exp:
            fin.budget_expenditure_mln = parse_float(exp.group(1))
        
        # Income: "59,3 mln złotych"
        inc = re.search(r'dochodów.*?wyniosła.*?([\d,]+)\s*mln', self.text)
        if inc:
            fin.budget_income_mln = parse_float(inc.group(1))
        
        # Per capita expenditure: "9,3 tys złotych"
        exp_per = re.search(r'wydatków.*?([\d,]+)\s*tys.*?na jednego mieszkańca', self.text)
        if exp_per:
            fin.expenditure_per_capita = parse_float(exp_per.group(1)) * 1000 if parse_float(exp_per.group(1)) else None
        
        # Per capita income: "8,9 tys złotych"
        inc_per = re.search(r'dochodów.*?([\d,]+)\s*tys.*?na jednego mieszkańca', self.text)
        if inc_per:
            fin.income_per_capita = parse_float(inc_per.group(1)) * 1000 if parse_float(inc_per.group(1)) else None
        
        # YoY change
        exp_change = re.search(r'wzrost wydatków o\s*([\d,]+)%', self.text)
        if exp_change:
            fin.expenditure_change_pct = parse_float(exp_change.group(1))
        
        inc_change = re.search(r'wzrost dochodów o\s*([\d,]+)%', self.text)
        if inc_change:
            fin.income_change_pct = parse_float(inc_change.group(1))
        
        # Department breakdown from table or text
        edu_pct = re.search(r'Oświata i wychowanie.*?([\d,]+)%\)', self.text)
        if edu_pct:
            fin.education_expenditure_pct = parse_float(edu_pct.group(1))
        
        transport_pct = re.search(r'Transport i łączność.*?([\d,]+)%\)', self.text)
        if transport_pct:
            fin.transport_expenditure_pct = parse_float(transport_pct.group(1))
        
        admin_pct = re.search(r'Administracja publiczna.*?([\d,]+)%\)', self.text)
        if admin_pct:
            fin.admin_expenditure_pct = parse_float(admin_pct.group(1))
        
        # Investment
        inv = re.search(r'inwestycyjne stanowiły\s*([\d,]+)\s*mln', self.text)
        if inv:
            fin.investment_expenditure_mln = parse_float(inv.group(1))
        
        inv_pct = re.search(r'inwestycyjne.*?([\d,]+)%\s*wydatków ogółem', self.text)
        if inv_pct:
            fin.investment_pct = parse_float(inv_pct.group(1))

        # Parse historical data
        self._parse_historical_finance(stats)

    def _parse_labor_market(self, stats: GminaStats):
        """Parse labor market data."""
        labor = stats.labor_market
        
        # Employed per 1000: "144 Pracujący na 1000 ludności"
        emp = re.search(r'(\d+)\s*Pracujący na 1000 ludności', self.text)
        if emp:
            labor.employed_per_1000 = parse_int(emp.group(1))
        
        # Total employed: "982 Pracujący ogółem"
        emp_total = re.search(r'(\d+)\s*Pracujący ogółem\b', self.text)
        if emp_total:
            labor.employed_total = parse_int(emp_total.group(1))
        
        # Unemployment: "12,4% Szacunkowa stopa bezrobocia" or in text
        unemp = re.search(r'bezrobocie.*?wynosiła?\w*.*?([\d,]+)%', self.text, re.IGNORECASE)
        if not unemp:
            unemp = re.search(r'([\d,]+)%\s*Szacunkowa stopa bezrobocia', self.text)
        if unemp:
            labor.unemployment_rate = parse_float(unemp.group(1))
        
        # Gender-specific unemployment
        unemp_women = re.search(r'([\d,]+)%\s*Kobiety.*?bezrob', self.text)
        if unemp_women:
            labor.unemployment_rate_women = parse_float(unemp_women.group(1))
        
        unemp_men = re.search(r'([\d,]+)%\s*Mężczyźni.*?bezrob', self.text)
        if unemp_men:
            labor.unemployment_rate_men = parse_float(unemp_men.group(1))
        
        # Salary: "6 837,70 PLN" or "6 838 PLN"
        salary = re.search(r'wynagrodzenie brutto.*?([\d\s,]+)\s*PLN', self.text)
        if salary:
            labor.salary_gross_pln = parse_float(salary.group(1))
        
        # Salary vs Poland: "79.20%"
        salary_pct = re.search(r'([\d,]+)%.*?przeciętnego.*?wynagrodzenia.*?Polsce', self.text)
        if salary_pct:
            labor.salary_vs_poland_pct = parse_float(salary_pct.group(1))
        
        # Sectors from text
        agri = re.search(r'([\d,]+)%.*?pracuje w sektorze rolniczym', self.text)
        if agri:
            labor.sector_agriculture_pct = parse_float(agri.group(1))
        
        industry = re.search(r'([\d,]+)%\s*w przemyśle i budownictwie', self.text)
        if industry:
            labor.sector_industry_pct = parse_float(industry.group(1))
        
        services = re.search(r'([\d,]+)%\s*w sektorze usługowym', self.text)
        if services:
            labor.sector_services_pct = parse_float(services.group(1))
        
        finance = re.search(r'([\d,]+)%\s*pracuje w sektorze finansowym', self.text)
        if finance:
            labor.sector_finance_pct = parse_float(finance.group(1))
        
        # Commuting
        commute_out = re.search(r'(\d+)\s*Liczba osób wyjeżdżających do pracy', self.text)
        if commute_out:
            labor.commute_out = parse_int(commute_out.group(1))
        
        commute_in = re.search(r'(\d+)\s*Liczba osób przyjeżdżających do pracy', self.text)
        if commute_in:
            labor.commute_in = parse_int(commute_in.group(1))
        
        commute_bal = re.search(r'(-?\d+)\s*Saldo przyjazdów i wyjazdów', self.text)
        if commute_bal:
            labor.commute_balance = parse_int(commute_bal.group(1))

    def _parse_education(self, stats: GminaStats):
        """Parse education data."""
        edu = stats.education
        
        # Kindergartens: "1 **Przedszkola**"
        kg = re.search(r'(\d+)\s*\*?\*?Przedszkola\*?\*?', self.text)
        if kg:
            edu.kindergartens = parse_int(kg.group(1))
        
        # Kindergarten children: "75 Dzieci"
        kg_children = re.search(r'(\d+)\s*Dzieci\s*(?:w przedszkol|\n)', self.text)
        if kg_children:
            edu.kindergarten_children = parse_int(kg_children.group(1))
        
        # Primary schools: "5 **Szkoły podstawowe**"
        ps = re.search(r'(\d+)\s*\*?\*?Szkoły podstawowe', self.text)
        if ps:
            edu.primary_schools = parse_int(ps.group(1))
        
        # Primary students: "618 Uczniowie"
        ps_students = re.search(r'(\d+)\s*Uczniowie\s*(?:w szkoł|\n)', self.text)
        if ps_students:
            edu.primary_students = parse_int(ps_students.group(1))
        
        # High schools: "1 **Licea ogólnokształcące**"
        hs = re.search(r'(\d+)\s*\*?\*?Licea ogólnokształcące', self.text)
        if hs:
            edu.high_schools = parse_int(hs.group(1))
        
        # High school students: "95 Uczniowie"
        hs_match = re.search(r'Licea ogólnokształcące.*?(\d+)\s*Uczniowie', self.text, re.DOTALL)
        if hs_match:
            edu.high_school_students = parse_int(hs_match.group(1))
        
        # Vocational: "1 Branżowa szkoła"
        voc = re.search(r'(\d+)\s*Branżowa szkoła', self.text)
        if voc:
            edu.vocational_schools = parse_int(voc.group(1))
        
        # Students per class: "13,4 Uczniowie przypadający na 1 oddział"
        per_class = re.search(r'([\d,]+)\s*\*?\*?Uczniowie przypadający na 1 oddział', self.text)
        if per_class:
            edu.students_per_class = parse_float(per_class.group(1))
        
        # Education levels from census data
        higher = re.search(r'([\d,]+)%\s*Wykształcenie wyższe', self.text)
        if higher:
            edu.higher_education_pct = parse_float(higher.group(1))
        
        secondary = re.search(r'([\d,]+)%\s*Wykształcenie średnie i policealne', self.text)
        if secondary:
            edu.secondary_education_pct = parse_float(secondary.group(1))
        
        vocational_edu = re.search(r'([\d,]+)%\s*Wykształcenie zasadnicze zawodowe', self.text)
        if vocational_edu:
            edu.vocational_education_pct = parse_float(vocational_edu.group(1))
        
        primary_edu = re.search(r'([\d,]+)%\s*Wykształcenie podstawowe ukończone', self.text)
        if primary_edu:
            edu.primary_education_pct = parse_float(primary_edu.group(1))

    def _parse_safety(self, stats: GminaStats):
        """Parse crime and safety data."""
        safety = stats.safety
        
        # Total crimes: "112 Przestępstwa ogółem"
        total = re.search(r'(\d+)\s*Przestępstwa ogółem\s*\(oszacowanie\)', self.text)
        if total:
            safety.crimes_total = parse_int(total.group(1))
        
        # Crimes per 1000: "16,81 Przestępstwa ogółem na 1000"
        per_1000 = re.search(r'([\d,]+)\s*Przestępstwa ogółem na 1000', self.text)
        if per_1000:
            safety.crimes_per_1000 = parse_float(per_1000.group(1))
        
        # Crime types
        criminal = re.search(r'(\d+)\s*Przestępstwa o charakterze kryminalnym', self.text)
        if criminal:
            safety.crimes_criminal = parse_int(criminal.group(1))
        
        economic = re.search(r'(\d+)\s*Przestępstwa o charakterze gospodarczym', self.text)
        if economic:
            safety.crimes_economic = parse_int(economic.group(1))
        
        traffic = re.search(r'(\d+)\s*Przestępstwa drogowe', self.text)
        if traffic:
            safety.crimes_traffic = parse_int(traffic.group(1))
        
        life = re.search(r'(\d+)\s*Przestępstwa przeciwko życiu', self.text)
        if life:
            safety.crimes_against_life = parse_int(life.group(1))
        
        property_crime = re.search(r'(\d+)\s*Przestępstwa przeciwko mieniu', self.text)
        if property_crime:
            safety.crimes_against_property = parse_int(property_crime.group(1))
        
        # Detection rates
        detect_total = re.search(r'(\d+)%\s*Wskaźnik wykrywalności.*?ogółem', self.text)
        if detect_total:
            safety.detection_rate_total = parse_float(detect_total.group(1))
        
        detect_criminal = re.search(r'(\d+)%\s*Wskaźnik wykrywalności.*?kryminalnym', self.text)
        if detect_criminal:
            safety.detection_rate_criminal = parse_float(detect_criminal.group(1))
        
        detect_property = re.search(r'(\d+)%\s*Wskaźnik wykrywalności.*?mieniu', self.text)
        if detect_property:
            safety.detection_rate_property = parse_float(detect_property.group(1))

    def _parse_transport(self, stats: GminaStats):
        """Parse transport and road safety data."""
        trans = stats.transport
        
        # Accidents: "3 Wypadki drogowe"
        accidents = re.search(r'(\d+)\s*Wypadki drogowe\s*\(rok', self.text)
        if accidents:
            trans.accidents_total = parse_int(accidents.group(1))
        
        # Per 100k: "44,82 Wypadki drogowe na 100 tys."
        acc_per_100k = re.search(r'([\d,]+)\s*Wypadki drogowe na 100 tys', self.text)
        if acc_per_100k:
            trans.accidents_per_100k = parse_float(acc_per_100k.group(1))
        
        # Fatalities: "0 Ofiary śmiertelne"
        fatalities = re.search(r'(\d+)\s*Ofiary śmiertelne\s*\(rok', self.text)
        if fatalities:
            trans.fatalities = parse_int(fatalities.group(1))
        
        # Injured: "3 Ranni"
        injured = re.search(r'(\d+)\s*Ranni\s*\(rok', self.text)
        if injured:
            trans.injured = parse_int(injured.group(1))
        
        # Bike paths: "5 km Ścieżki rowerowe"
        bike = re.search(r'(\d+)\s*km\s*Ścieżki rowerowe', self.text)
        if bike:
            trans.bike_paths_km = parse_float(bike.group(1))
        
        # Per 10k km2: "336,9 km Ścieżki rowerowe na 10 tys. km2"
        bike_per_km2 = re.search(r'([\d,]+)\s*km\s*Ścieżki rowerowe na 10 tys. km2', self.text)
        if bike_per_km2:
            trans.bike_paths_per_10k_km2 = parse_float(bike_per_km2.group(1))
        
        # Per 10k people: "7,5 km Ścieżki rowerowe na 10 tys. ludności"
        bike_per_people = re.search(r'([\d,]+)\s*km\s*Ścieżki rowerowe na 10 tys. ludności', self.text)
        if bike_per_people:
            trans.bike_paths_per_10k_people = parse_float(bike_per_people.group(1))

        # Parse historical data
        self._parse_historical_transport(stats)

    def _parse_regon(self, stats: GminaStats):
        """Parse business registry (REGON) data."""
        regon = stats.regon
        
        # Total entities: "567 Podmioty gospodarki narodowej"
        total = re.search(r'(\d+)\s*Podmioty gospodarki narodowej', self.text)
        if total:
            regon.entities_total = parse_int(total.group(1))
        
        # Natural persons: "466 Osoby fizyczne prowadzące działalność"
        natural = re.search(r'(\d+)\s*Osoby fizyczne prowadzące działalność', self.text)
        if natural:
            regon.natural_persons = parse_int(natural.group(1))
        
        # New entities: "29 Podmioty nowo zarejestrowane"
        new = re.search(r'(\d+)\s*Podmioty nowo zarejestrowane', self.text)
        if new:
            regon.new_entities_2024 = parse_int(new.group(1))
        
        # Deregistered: "31 Podmioty wyrejestrowane"
        dereg = re.search(r'(\d+)\s*Podmioty wyrejestrowane', self.text)
        if dereg:
            regon.deregistered_2024 = parse_int(dereg.group(1))
        
        # By size
        micro = re.search(r'(\d+)\s*Mikro-przedsiębiorstwa', self.text)
        if micro:
            regon.micro_enterprises = parse_int(micro.group(1))
        
        small = re.search(r'(\d+)\s*Małe przedsiębiorstwa', self.text)
        if small:
            regon.small_enterprises = parse_int(small.group(1))
        
        medium = re.search(r'(\d+)\s*Średnie przedsiębiorstwa', self.text)
        if medium:
            regon.medium_enterprises = parse_int(medium.group(1))
        
        
        # By activity type
        construction = re.search(r'(\d+)\s*Budownictwo\b', self.text)
        if construction:
            regon.construction_count = parse_int(construction.group(1))
        
        trade = re.search(r'(\d+)\s*Handel hurtowy i detaliczny', self.text)
        if trade:
            regon.trade_count = parse_int(trade.group(1))
        
        manufacturing = re.search(r'(\d+)\s*Przetwórstwo przemysłowe', self.text)
        if manufacturing:
            regon.manufacturing_count = parse_int(manufacturing.group(1))
        
        transport_bus = re.search(r'(\d+)\s*Transport i gospodarka magazynowa', self.text)
        if transport_bus:
            regon.transport_count = parse_int(transport_bus.group(1))

    def _extract_table_data(self, start_marker, end_marker=None, row_pattern=None):
        """Helper to extract data from markdown tables."""
        lines = self.text.split('\n')
        extracting = False
        data = []
        
        for line in lines:
            if start_marker in line:
                extracting = True
                continue
            
            if extracting:
                if end_marker and end_marker in line:
                    break
                if not line.strip():
                    continue
                
                if row_pattern:
                    match = re.search(row_pattern, line)
                    if match:
                        data.append(match)
        return data

    def _parse_historical_demographics(self, stats: GminaStats):
        """Parse population history from table."""
        # Find section "Ludność w gminie Rybno na przestrzeni lat"
        # Table format: | Rok | Liczba ludności | ...
        
        lines = self.text.split('\n')
        start_idx = -1
        
        for i, line in enumerate(lines):
            if "Ludność w gminie Rybno na przestrzeni lat" in line:
                start_idx = i
                break
        
        if start_idx != -1:
            for i in range(start_idx + 2, len(lines)): # Skip header and separator
                line = lines[i]
                if not line.strip() or "źródło" in line.lower():
                    break
                    
                # | 2023 | 6 000 | ...
                match = re.search(r'\|\s*(\d{4})\s*\|\s*([\d\s]+)\s*\|', line)
                if match:
                    year = int(match.group(1))
                    val = parse_int(match.group(2))
                    if year and val:
                        stats.demographics.population_history.append({"year": year, "val": val})

    def _parse_historical_finance(self, stats: GminaStats):
        """Parse budget history from tables."""
        lines = self.text.split('\n')
        
        def extract_budget_data(section_header):
            years = []
            values = []
            departments = []
            
            start_idx = -1
            for i, line in enumerate(lines):
                if section_header in line:
                    start_idx = i
                    break
            
            if start_idx != -1:
                # Look for data in lines following the header
                # First find the table header with Years
                table_start_idx = -1
                for i in range(start_idx, min(start_idx + 50, len(lines))):
                    if "| **Dział klasyfikacji budżetowej** |" in lines[i]:
                        table_start_idx = i
                        matches = re.findall(r'\*\*(\d{4})\*\*', lines[i])
                        years = [int(m) for m in matches]
                        break
                
                # If we found the table header, parse rows
                if table_start_idx != -1:
                    # Look for Ogółem line separately (it might be before or after header)
                    ogolem_values = []
                    for i in range(max(start_idx, table_start_idx - 5), min(table_start_idx + 5, len(lines))):
                         line = lines[i]
                         if "Ogółem (zł)" in line:
                            cells = [c.strip() for c in line.split('|')[1:-1]]
                            data_cells = cells[1:]
                            for cell in data_cells:
                                val_match = re.search(r'([\d,\.\s]+)\s*(mln|tys|mld)', cell)
                                if val_match:
                                    num_str = val_match.group(1).replace(',', '.').replace(' ', '')
                                    unit = val_match.group(2)
                                    val = float(num_str)
                                    if unit == 'mln': val *= 1_000_000
                                    elif unit == 'tys': val *= 1_000
                                    elif unit == 'mld': val *= 1_000_000_000
                                    ogolem_values.append(val)
                                else:
                                    ogolem_values.append(0.0)
                            break
                    
                    if ogolem_values:
                        values = ogolem_values 

                    for i in range(table_start_idx + 2, min(table_start_idx + 50, len(lines))):
                        line = lines[i]
                        if not line.strip().startswith('|'):
                            break
                        
                        # Check for "Ogółem" line (Totals)
                        if "Ogółem (zł)" in line:
                            cells = [c.strip() for c in line.split('|')[1:-1]]
                            # cells[0] is header
                            # cells[1..] are values
                            # Filter empty cells if any
                            data_cells = cells[1:]
                            # Use helper logic to parse value
                            values = []
                            for cell in data_cells:
                                # Clean cell: remove <br>..., remove _..._, remove **...**
                                val_match = re.search(r'([\d,\.\s]+)\s*(mln|tys|mld)', cell)
                                if val_match:
                                    num_str = val_match.group(1).replace(',', '.').replace(' ', '')
                                    unit = val_match.group(2)
                                    val = float(num_str)
                                    if unit == 'mln': val *= 1_000_000
                                    elif unit == 'tys': val *= 1_000
                                    elif unit == 'mld': val *= 1_000_000_000
                                    values.append(val)
                                else:
                                    values.append(0.0)
                            continue
                        
                        # Check for Department row: | Name<br>[Dział Code] | ...
                        # Regex to capture content in first cell: | content |
                        # Example: | Różne rozliczenia<br>[Dział 758] | ...
                        parts = line.split('|')
                        if len(parts) > 2:
                            col1 = parts[1]
                            # match Name<br>[Dział Code]
                            dept_match = re.search(r'(.*?)<br>\\\[Dział (\d+)\\\]', col1)
                            if dept_match:
                                name = dept_match.group(1).strip()
                                code = dept_match.group(2).strip()
                                
                                history = []
                                # Parse value columns (indices 2 to len-1)
                                header_count = len(years)
                                data_cols = parts[2:2+header_count]
                                
                                for j, col_val in enumerate(data_cols):
                                    if j < len(years):
                                        # Extract primary value (millions, thousands, or just numbers)
                                        # Formats: "_12,2 mln_ <br>...", "**24,0 mln** <br>...", "793,5 tys", "0,0"
                                        val_str = re.search(r'[\*_]*([\d,\.\s]+)(mln|tys)?[\*_]*', col_val)
                                        if val_str:
                                            num_part = val_str.group(1).replace(' ', '').replace(',', '.')
                                            unit = val_str.group(2)
                                            try:
                                                val = float(num_part)
                                                if unit == 'mln':
                                                    val *= 1_000_000
                                                elif unit == 'tys':
                                                    val *= 1_000
                                                history.append({"year": str(years[j]), "value": val})
                                            except ValueError:
                                                pass
                                
                                departments.append(BudgetDepartment(
                                    name=name,
                                    code=code,
                                    history=history
                                ))

            return years, values, departments

        # 1. Expenditure (Wydatki)
        exp_years, exp_values, exp_depts = extract_budget_data("Wydatki budżetu gminy Rybno według działów")
        
        # 2. Income (Dochody)
        inc_years, inc_values, inc_depts = extract_budget_data("Dochody budżetu gminy Rybno według działów")
        
        # Combine Totals
        combined_years = sorted(list(set(exp_years + inc_years)))
        history_map = {}
        for y in combined_years:
            history_map[y] = {"year": y, "income": None, "expenditure": None}
            
        if len(exp_years) == len(exp_values):
            for i, y in enumerate(exp_years):
                if y in history_map:
                    history_map[y]["expenditure"] = exp_values[i]
                    
        if len(inc_years) == len(inc_values):
            for i, y in enumerate(inc_years):
                if y in history_map:
                    history_map[y]["income"] = inc_values[i]
        
        # Assign to stats
        stats.finance.budget_history = list(history_map.values())
        stats.finance.budget_expenditure_details = exp_depts
        stats.finance.budget_income_details = inc_depts
                    
        # Convert to list
        if history_map:
            stats.finance.budget_history = sorted(history_map.values(), key=lambda x: x['year'])

    def _parse_historical_transport(self, stats: GminaStats):
        """Parse accident history."""
        # "Wypadki drogowe... w latach 2010 - 2024"
        lines = self.text.split('\n')
        start_idx = -1
        
        for i, line in enumerate(lines):
            if "Wypadki drogowe" in line and "w latach" in line:
                start_idx = i
                break
        
        if start_idx != -1:
             for i in range(start_idx + 2, len(lines)):
                line = lines[i]
                if not line.strip() or "źródło" in line.lower():
                    break
                
                # | 2023 | 3 | ...
                match = re.search(r'\|\s*(\d{4})\s*\|\s*(\d+)\s*\|', line)
                if match:
                     year = int(match.group(1))
                     val = int(match.group(2))
                     stats.transport.accidents_history.append({"year": year, "count": val})

