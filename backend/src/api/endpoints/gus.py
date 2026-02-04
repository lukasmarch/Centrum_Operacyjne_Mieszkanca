"""
GUS Statistics API Endpoints

Provides tier-based access to GUS data:
- Free tier: Basic 5 variables
- Premium tier: 17 variables (demographics, employment, business, transport)
- Business tier: All 40+ variables + advanced features
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from src.database import get_session, User
from src.auth.dependencies import get_optional_user, get_premium_user, get_business_user
from src.integrations.gus_api import GUSDataService

router = APIRouter(prefix="/api/stats", tags=["gus"])

# ==================== TIER DEFINITIONS ====================

FREE_VARIABLES = [
    "population_total",
    "births_live",
    "entities_regon_per_10k",
    "new_entities_per_10k",
    "deregistered_per_10k",
]

PREMIUM_VARIABLES = FREE_VARIABLES + [
    # Demografia (5)
    "population_density",
    "population_male",
    "population_female",
    "infant_mortality_rate",
    # Rynek pracy (3)
    "unemployment_rate",
    "avg_salary",
    "registered_unemployed",
    # Przedsiębiorczość (4)
    "sme_per_10k",
    "large_entities_per_10k",
    "micro_enterprises_share",
    "natural_persons_business",
    # Transport (3)
    "personal_cars",
    "vehicles_per_1000",
    "paved_roads_km",
    # Infrastruktura (2)
    "investment_expenditure",
    "road_spending",
]

BUSINESS_VARIABLES = list(GUSDataService.VARS.keys())  # Wszystkie zmienne

# Variable metadata
VARIABLE_METADATA = {
    # Free tier
    "population_total": {"name": "Ludność ogółem", "unit": "os.", "tier": "free", "category": "demografia"},
    "births_live": {"name": "Urodzenia żywe", "unit": "os.", "tier": "free", "category": "demografia"},
    "entities_regon_per_10k": {"name": "Podmioty REGON/10k", "unit": "", "tier": "free", "category": "przedsiebiorczosc"},
    "new_entities_per_10k": {"name": "Nowe firmy/10k", "unit": "", "tier": "free", "category": "przedsiebiorczosc"},
    "deregistered_per_10k": {"name": "Wykreślone firmy/10k", "unit": "", "tier": "free", "category": "przedsiebiorczosc"},

    # Premium tier - Demografia
    "population_density": {"name": "Gęstość zaludnienia", "unit": "os./km²", "tier": "premium", "category": "demografia"},
    "population_male": {"name": "Ludność mężczyźni", "unit": "tys.", "tier": "premium", "category": "demografia"},
    "population_female": {"name": "Ludność kobiety", "unit": "tys.", "tier": "premium", "category": "demografia"},
    "infant_mortality_rate": {"name": "Zgony niemowląt/1000", "unit": "", "tier": "premium", "category": "demografia"},

    # Premium tier - Rynek pracy
    "unemployment_rate": {"name": "Stopa bezrobocia", "unit": "%", "tier": "premium", "category": "rynek_pracy"},
    "avg_salary": {"name": "Średnie wynagrodzenie", "unit": "PLN", "tier": "premium", "category": "rynek_pracy"},
    "registered_unemployed": {"name": "Bezrobotni zarejestrowani", "unit": "os.", "tier": "premium", "category": "rynek_pracy"},

    # Premium tier - Przedsiębiorczość
    "sme_per_10k": {"name": "MŚP/10k", "unit": "", "tier": "premium", "category": "przedsiebiorczosc"},
    "large_entities_per_10k": {"name": "Duże firmy/10k", "unit": "", "tier": "premium", "category": "przedsiebiorczosc"},
    "micro_enterprises_share": {"name": "Udział mikrofirm", "unit": "%", "tier": "premium", "category": "przedsiebiorczosc"},
    "natural_persons_business": {"name": "Osoby fizyczne - działalność", "unit": "os.", "tier": "premium", "category": "przedsiebiorczosc"},

    # Premium tier - Transport
    "personal_cars": {"name": "Samochody osobowe", "unit": "szt.", "tier": "premium", "category": "transport"},
    "vehicles_per_1000": {"name": "Pojazdy/1000 ludności", "unit": "", "tier": "premium", "category": "transport"},
    "paved_roads_km": {"name": "Drogi twarde", "unit": "km", "tier": "premium", "category": "transport"},

    # Premium tier - Infrastruktura
    "investment_expenditure": {"name": "Wydatki inwestycyjne", "unit": "PLN", "tier": "premium", "category": "infrastruktura"},
    "road_spending": {"name": "Wydatki na drogi", "unit": "PLN", "tier": "premium", "category": "infrastruktura"},

    # Business tier - Pozostałe
    "mortality_rate": {"name": "Zgony ogółem/1000", "unit": "", "tier": "business", "category": "demografia"},
    "divorces": {"name": "Rozwody", "unit": "os.", "tier": "business", "category": "demografia"},
    "unemployed_total": {"name": "Bezrobocie ogółem", "unit": "os.", "tier": "business", "category": "rynek_pracy"},
    "vehicles_total": {"name": "Pojazdy samochodowe ogółem", "unit": "szt.", "tier": "business", "category": "transport"},
    "buses": {"name": "Autobusy", "unit": "szt.", "tier": "business", "category": "transport"},
    "trucks": {"name": "Samochody ciężarowe", "unit": "szt.", "tier": "business", "category": "transport"},
    "improved_roads_km": {"name": "Drogi ulepszone", "unit": "km", "tier": "business", "category": "transport"},
    "unpaved_roads_km": {"name": "Drogi gruntowe", "unit": "km", "tier": "business", "category": "transport"},
    "library_spending": {"name": "Wydatki na biblioteki", "unit": "PLN", "tier": "business", "category": "infrastruktura"},
    "social_care_spending": {"name": "Wydatki na domy pomocy", "unit": "PLN", "tier": "business", "category": "infrastruktura"},
    "foreign_capital_companies": {"name": "Spółki zagraniczne/10k", "unit": "", "tier": "business", "category": "przedsiebiorczosc"},
    "accommodations_per_10000": {"name": "Noclegi/10k", "unit": "", "tier": "business", "category": "turystyka"},
    "deregistered_share": {"name": "Udział wyrejestrowanych", "unit": "%", "tier": "business", "category": "przedsiebiorczosc"},
    "new_to_deregistered_ratio": {"name": "Stosunek nowe/wyrejestrowane", "unit": "%", "tier": "business", "category": "przedsiebiorczosc"},
    "entities_per_1k": {"name": "Podmioty/1000 ludności", "unit": "", "tier": "business", "category": "przedsiebiorczosc"},
}


# ==================== HELPER FUNCTIONS ====================

def get_allowed_variables(user: Optional[User]) -> List[str]:
    """Get list of variables allowed for user's tier"""
    if not user:
        return FREE_VARIABLES

    if user.tier == "business":
        return BUSINESS_VARIABLES
    elif user.tier == "premium":
        return PREMIUM_VARIABLES
    else:
        return FREE_VARIABLES


def check_variable_access(var_key: str, user: Optional[User]) -> bool:
    """Check if user has access to specific variable"""
    allowed = get_allowed_variables(user)
    return var_key in allowed


# ==================== ENDPOINTS ====================

@router.get("/variables/list")
async def list_variables(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Get list of available variables for current user's tier

    Returns:
        - variables: List of variable metadata (filtered by tier)
        - user_tier: Current user's tier
        - total_available: Number of variables available to user
    """
    allowed_vars = get_allowed_variables(current_user)
    user_tier = current_user.tier if current_user else "free"

    # Filter metadata by allowed variables and add var_id from GUS API
    filtered_metadata = {}
    for var_key in allowed_vars:
        meta = VARIABLE_METADATA.get(var_key, {})
        var_id = GUSDataService.VARS.get(var_key)
        filtered_metadata[var_key] = {
            **meta,
            "var_id": var_id  # Add var_id for frontend
        }

    # Group by category
    by_category = {}
    for var_key, meta in filtered_metadata.items():
        category = meta["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append({
            "key": var_key,
            **meta
        })

    return {
        "user_tier": user_tier,
        "total_available": len(allowed_vars),
        "variables": filtered_metadata,
        "by_category": by_category,
        "tiers": {
            "free": {"count": len(FREE_VARIABLES), "price": "0 zł/mc"},
            "premium": {"count": len(PREMIUM_VARIABLES), "price": "19 zł/mc"},
            "business": {"count": len(BUSINESS_VARIABLES), "price": "99 zł/mc"}
        }
    }


@router.get("/variable/{var_key}")
async def get_variable(
    var_key: str,
    year: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get single variable value for Gmina Rybno

    Args:
        var_key: Variable key (e.g., "unemployment_rate")
        year: Optional year (default: latest)

    Returns:
        Variable data with value, year, metadata

    Raises:
        403: If user doesn't have access to this variable
        404: If variable not found
    """
    # Check access
    if not check_variable_access(var_key, current_user):
        metadata = VARIABLE_METADATA.get(var_key, {})
        required_tier = metadata.get("tier", "premium")
        raise HTTPException(
            status_code=403,
            detail=f"This variable requires {required_tier} subscription"
        )

    # Fetch data
    service = GUSDataService()
    try:
        data = await service.get_single_variable(var_key, year)

        # Add metadata
        metadata = VARIABLE_METADATA.get(var_key, {})
        data["metadata"] = metadata

        return data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {str(e)}")


@router.get("/multi-metric")
async def get_multi_metric(
    var_keys: str,  # Comma-separated list
    year: Optional[int] = None,
    current_user: User = Depends(get_business_user)  # Business only
):
    """
    Get multiple variables at once (Business tier only)

    Args:
        var_keys: Comma-separated variable keys (e.g., "unemployment_rate,avg_salary")
        year: Optional year (default: latest)

    Returns:
        Dict with all requested variables

    Requires: Business tier
    """
    keys = [k.strip() for k in var_keys.split(",")]

    if len(keys) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 variables allowed")

    service = GUSDataService()
    results = {}

    for var_key in keys:
        try:
            data = await service.get_single_variable(var_key, year)
            metadata = VARIABLE_METADATA.get(var_key, {})
            data["metadata"] = metadata
            results[var_key] = data
        except Exception as e:
            results[var_key] = {"error": str(e)}

    return {
        "variables": results,
        "year": year,
        "count": len(results)
    }


@router.get("/categories")
async def get_categories(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Get available categories for user's tier

    Returns:
        List of categories with variable counts
    """
    allowed_vars = get_allowed_variables(current_user)
    user_tier = current_user.tier if current_user else "free"

    # Count by category
    categories = {}
    for var_key in allowed_vars:
        meta = VARIABLE_METADATA.get(var_key, {})
        category = meta.get("category", "inne")

        if category not in categories:
            categories[category] = {
                "name": category.replace("_", " ").title(),
                "count": 0,
                "variables": []
            }

        categories[category]["count"] += 1
        categories[category]["variables"].append({
            "key": var_key,
            "name": meta.get("name", var_key),
            "unit": meta.get("unit", "")
        })

    # Category icons
    icons = {
        "demografia": "👥",
        "rynek_pracy": "💼",
        "przedsiebiorczosc": "🏢",
        "transport": "🚗",
        "infrastruktura": "🏗️",
        "turystyka": "🏨"
    }

    for cat_key, cat_data in categories.items():
        cat_data["icon"] = icons.get(cat_key, "📊")

    return {
        "user_tier": user_tier,
        "categories": categories
    }
