"""
Eksploracja GUS BDL API - wyszukiwanie var_id dla nowych kategorii.

Przeszukuje subjects i variables w BDL API żeby znaleźć prawidłowe ID
dla zmiennych z planu (~85 zmiennych w 10 kategoriach).

Uruchomienie:
    cd backend
    python scripts/production/explore_bdl_variables.py
"""
import requests
import time
import json

BASE_URL = "https://bdl.stat.gov.pl/api/v1"
UNIT_RYBNO = "042815403062"
UNIT_POWIAT = "042815403000"

# Rate limiting
REQUEST_DELAY = 0.3  # seconds between requests


def api_get(endpoint, params=None):
    """Make a GET request to BDL API with rate limiting."""
    url = f"{BASE_URL}{endpoint}"
    default_params = {"format": "json", "page-size": 100}
    if params:
        default_params.update(params)
    time.sleep(REQUEST_DELAY)
    resp = requests.get(url, params=default_params)
    resp.raise_for_status()
    return resp.json()


def search_variables(query):
    """Search for variables by name."""
    return api_get("/variables/search", {"name": query, "page-size": 50})


def get_subjects(parent_id=None):
    """Get subject categories."""
    params = {}
    if parent_id:
        params["parent-id"] = parent_id
    return api_get("/subjects", params)


def get_variables_for_subject(subject_id):
    """Get variables for a subject."""
    return api_get("/variables", {"subject-id": subject_id, "page-size": 100})


def test_variable(var_id, unit_id=UNIT_RYBNO):
    """Test if a variable has data for given unit."""
    try:
        data = api_get(f"/data/by-unit/{unit_id}", {"var-id": var_id})
        results = data.get("results", [])
        if results:
            values = results[0].get("values", [])
            if values:
                latest = values[-1]
                return {
                    "has_data": True,
                    "latest_year": latest.get("year"),
                    "latest_value": latest.get("val"),
                    "years_count": len(values),
                    "first_year": values[0].get("year"),
                }
        return {"has_data": False}
    except Exception as e:
        return {"has_data": False, "error": str(e)}


def explore_category(name, search_terms, test_unit=UNIT_RYBNO):
    """Explore a category by searching multiple terms."""
    print(f"\n{'='*60}")
    print(f"  KATEGORIA: {name}")
    print(f"  Unit: {test_unit}")
    print(f"{'='*60}")

    found_vars = {}

    for term in search_terms:
        print(f"\n  Szukam: '{term}'...")
        try:
            result = search_variables(term)
            variables = result.get("results", [])
            print(f"  Znaleziono: {len(variables)} zmiennych")

            for var in variables[:15]:  # max 15 per term
                var_id = str(var["id"])
                var_name = var.get("n1", "")
                var_unit = var.get("n2", "")
                subject = var.get("subjectId", "")

                if var_id not in found_vars:
                    # Test availability
                    test_result = test_variable(var_id, test_unit)

                    found_vars[var_id] = {
                        "id": var_id,
                        "name": var_name,
                        "unit": var_unit,
                        "subject_id": subject,
                        "search_term": term,
                        **test_result,
                    }

                    status = "OK" if test_result["has_data"] else "NO DATA"
                    year = test_result.get("latest_year", "?")
                    val = test_result.get("latest_value", "?")
                    print(f"    [{status}] {var_id}: {var_name} ({var_unit}) = {val} ({year})")

        except Exception as e:
            print(f"  ERROR: {e}")

    # Summary
    available = {k: v for k, v in found_vars.items() if v.get("has_data")}
    print(f"\n  PODSUMOWANIE {name}: {len(available)}/{len(found_vars)} z danymi")
    return found_vars


def main():
    print("GUS BDL API - Eksploracja zmiennych")
    print("=" * 60)

    all_results = {}

    # ==================== DEMOGRAFIA ====================
    demo_vars = explore_category(
        "DEMOGRAFIA",
        [
            "ludność ogółem",
            "gęstość zaludnienia",
            "wiek średni",
            "wiek mediana",
            "ludność wiek",
            "urodzenia żywe",
            "przyrost naturalny",
            "małżeństwa",
            "zgony",
            "migracje wewnętrzne",
            "napływ migracyjny",
            "odpływ migracyjny",
            "saldo migracji",
        ],
        UNIT_RYBNO,
    )
    all_results["demografia"] = demo_vars

    # ==================== RYNEK PRACY ====================
    labor_vars = explore_category(
        "RYNEK PRACY",
        [
            "stopa bezrobocia",
            "wynagrodzenie przeciętne",
            "bezrobotni zarejestrowani",
            "pracujący ogółem",
            "pracujący na 1000",
            "pracujący kobiety",
            "pracujący sektor",
            "zatrudnieni rolnictwo",
            "zatrudnieni przemysł",
            "zatrudnieni usługi",
            "dojazdy do pracy",
        ],
        UNIT_RYBNO,
    )
    all_results["rynek_pracy"] = labor_vars

    # ==================== MIESZKALNICTWO ====================
    housing_vars = explore_category(
        "MIESZKALNICTWO",
        [
            "mieszkania ogółem",
            "mieszkania oddane",
            "powierzchnia mieszkania",
            "wodociąg",
            "kanalizacja",
            "centralne ogrzewanie",
            "gaz sieciowy",
            "izby w mieszkaniach",
            "budynki mieszkalne",
        ],
        UNIT_RYBNO,
    )
    all_results["mieszkalnictwo"] = housing_vars

    # ==================== FINANSE GMINY ====================
    finance_vars = explore_category(
        "FINANSE GMINY",
        [
            "dochody gmin ogółem",
            "dochody gmin per capita",
            "wydatki gmin ogółem",
            "wydatki gmin per capita",
            "wydatki majątkowe",
            "wydatki bieżące",
            "wydatki inwestycyjne",
            "dochody własne",
            "PIT gminy",
            "CIT gminy",
            "subwencje",
            "dotacje celowe",
        ],
        UNIT_RYBNO,
    )
    all_results["finanse_gminy"] = finance_vars

    # ==================== EDUKACJA ====================
    edu_vars = explore_category(
        "EDUKACJA",
        [
            "szkoły podstawowe",
            "uczniowie szkoły",
            "nauczyciele",
            "przedszkola",
            "dzieci przedszkola",
            "wychowanie przedszkolne",
            "absolwenci",
        ],
        UNIT_RYBNO,
    )
    all_results["edukacja"] = edu_vars

    # ==================== BEZPIECZEŃSTWO ====================
    safety_vars = explore_category(
        "BEZPIECZEŃSTWO",
        [
            "przestępstwa stwierdzone",
            "przestępstwa wykrywalność",
            "przestępstwa kryminalne",
            "przestępstwa gospodarcze",
            "przestępstwa drogowe",
            "wypadki drogowe",
        ],
        UNIT_POWIAT,  # bezpieczeństwo często na poziomie powiatu
    )
    all_results["bezpieczenstwo"] = safety_vars

    # ==================== ZDROWIE ====================
    health_vars = explore_category(
        "ZDROWIE",
        [
            "placówki ambulatoryjnej opieki",
            "lekarze na 10",
            "apteki",
            "porady lekarskie",
            "łóżka szpitalne",
        ],
        UNIT_POWIAT,
    )
    all_results["zdrowie"] = health_vars

    # ==================== TURYSTYKA ====================
    tourism_vars = explore_category(
        "TURYSTYKA",
        [
            "turystyczne obiekty noclegowe",
            "noclegi udzielone",
            "korzystający z noclegów",
        ],
        UNIT_POWIAT,
    )
    all_results["turystyka"] = tourism_vars

    # ==================== PODSUMOWANIE ====================
    print("\n\n" + "=" * 60)
    print("  PODSUMOWANIE KOŃCOWE")
    print("=" * 60)

    total_found = 0
    total_with_data = 0

    for category, vars_dict in all_results.items():
        with_data = sum(1 for v in vars_dict.values() if v.get("has_data"))
        total_found += len(vars_dict)
        total_with_data += with_data
        print(f"  {category:20s}: {with_data:3d}/{len(vars_dict):3d} z danymi")

    print(f"\n  RAZEM: {total_with_data}/{total_found} zmiennych z danymi")

    # Save full results to JSON
    output_file = "scripts/production/bdl_exploration_results.json"
    # Prepare serializable output
    output = {}
    for category, vars_dict in all_results.items():
        output[category] = {
            vid: {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                  for k, v in var_info.items()}
            for vid, var_info in vars_dict.items()
        }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  Wyniki zapisane do: {output_file}")

    # Print recommended variables (with data)
    print("\n\n" + "=" * 60)
    print("  REKOMENDOWANE ZMIENNE (z danymi)")
    print("=" * 60)

    for category, vars_dict in all_results.items():
        available = {k: v for k, v in vars_dict.items() if v.get("has_data")}
        if available:
            print(f"\n  # {category.upper()}")
            for var_id, info in available.items():
                name = info.get("name", "?")
                unit = info.get("unit", "")
                year = info.get("latest_year", "?")
                val = info.get("latest_value", "?")
                print(f'    "{var_id}",  # {name} ({unit}) = {val} ({year})')


if __name__ == "__main__":
    main()
