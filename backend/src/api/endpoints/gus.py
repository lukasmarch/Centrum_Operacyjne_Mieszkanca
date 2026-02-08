"""
GUS Statistics API Endpoints - Database-First Architecture (Gmina-Only)

Provides tier-based access to GUS data from local database:
- Free tier: 8 core KPI variables (gmina Rybno only)
- Premium tier: 31 premium variables (gmina data only)
- Business tier: 55 total variables with gmina data

Focus: ONLY variables with actual data for gmina Rybno (042815403062)
Comparisons: Gmina vs Powiat Działdowski (not national)
Categories with data: 7 (Demografia, Rynek Pracy, Przedsiębiorczość, Finanse,
                       Mieszkalnictwo, Edukacja, Zdrowie)
Hidden categories: Transport, Bezpieczeństwo, Turystyka (no gmina data)

All endpoints query local PostgreSQL database (gus_gmina_stats).
Zero live API calls to GUS BDL.
Data refreshed quarterly by scheduler.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import Optional, List, Dict
from datetime import datetime

from src.database import get_session, User
from src.database.schema import GUSGminaStats, GUSNationalAverages, GUSDataRefreshLog
from src.auth.dependencies import get_optional_user, get_premium_user, get_business_user
from src.integrations.gus_variables import (
    get_variable,
    get_variables_for_tier,
    get_variables_for_category,
    get_all_variables,
    get_gmina_available_variables,
    get_gmina_variables_for_category,
    get_gmina_variables_for_tier,
    CATEGORIES,
    UNIT_IDS,
    UNIT_ID_POWIAT,
    UNIT_ID_POLSKA,
    UNIT_ID_WOJEWODZTWO,
    GMINA_AVAILABLE_VAR_IDS,
)

router = APIRouter(prefix="/api/stats", tags=["gus"])

# ==================== HELPER FUNCTIONS ====================
# All variable metadata now comes from gus_variables.py (single source of truth)

def get_allowed_variables(user: Optional[User]) -> List[str]:
    """Get list of variable keys allowed for user's tier (gmina data only)"""
    tier = user.tier if user else "free"
    variables = get_gmina_variables_for_tier(tier)  # CHANGED: Only gmina data
    return [var.key for var in variables]


def check_variable_access(var_key: str, user: Optional[User]) -> bool:
    """Check if user has access to specific variable (gmina data only)"""
    tier = user.tier if user else "free"
    allowed_vars = get_gmina_variables_for_tier(tier)  # CHANGED: Only gmina data
    allowed_keys = [var.key for var in allowed_vars]
    return var_key in allowed_keys


def get_variable_metadata(var_key: str) -> Optional[Dict]:
    """Get variable metadata from registry"""
    var = get_variable(var_key)
    if not var:
        return None

    return {
        "key": var.key,
        "var_id": var.var_id,
        "name": var.name_pl,
        "unit": var.unit,
        "category": var.category,
        "tier": var.tier,
        "level": var.level,
        "format_type": var.format_type,
    }


# ==================== ENDPOINTS ====================

@router.get("/overview")
async def get_overview(
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get Free tier KPI overview (8 variables) - Gmina data only

    Returns ONLY variables with actual data for gmina Rybno.
    Historical trends from 1995-2024.

    Returns:
        - variables: Dict with current values, trends, metadata
        - user_tier: Current user's tier
        - last_refresh: Latest data refresh timestamp

    Free tier endpoint - no auth required
    """
    user_tier = current_user.tier if current_user else "free"
    free_vars = get_gmina_variables_for_tier("free")  # CHANGED: Only gmina data
    var_ids = [v.var_id for v in free_vars]

    # Get latest year from DB
    stmt = select(GUSGminaStats.year).where(
        GUSGminaStats.var_id.in_(var_ids)
    ).order_by(desc(GUSGminaStats.year)).limit(1)
    latest_year = await session.scalar(stmt)

    if not latest_year:
        raise HTTPException(status_code=404, detail="No GUS data available in database")

    # CRITICAL FIX: ALL variables in GMINA_AVAILABLE_VAR_IDS have data for Rybno
    # ALWAYS fetch from unit_id="Rybno" regardless of "level" metadata
    var_ids = [v.var_id for v in free_vars]

    # Fetch current year data - ALL from Rybno
    current_data = {}
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == UNIT_IDS["Rybno"],
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year == latest_year
        )
    )
    result = await session.execute(stmt)
    for row in result.scalars():
        current_data[row.var_id] = row

    # Fetch previous year for trend - ALL from Rybno
    prev_data = {}
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == UNIT_IDS["Rybno"],
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year == latest_year - 1
        )
    )
    result = await session.execute(stmt)
    for row in result.scalars():
        prev_data[row.var_id] = row

    # Fetch historical data (last 10 years) - ALL from Rybno
    historical_by_var = {}
    start_year = latest_year - 9  # 10 years total including latest

    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == UNIT_IDS["Rybno"],
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year >= start_year,
            GUSGminaStats.year <= latest_year
        )
    ).order_by(GUSGminaStats.var_id, GUSGminaStats.year)
    result = await session.execute(stmt)
    for row in result.scalars():
            if row.var_id not in historical_by_var:
                historical_by_var[row.var_id] = []
            historical_by_var[row.var_id].append({
                "year": row.year,
                "value": row.value
            })

    # Build response
    variables = {}
    for var in free_vars:
        current_row = current_data.get(var.var_id)
        if not current_row:
            continue

        # Calculate trend
        prev_row = prev_data.get(var.var_id)
        trend_pct = None
        if prev_row and prev_row.value and prev_row.value != 0:
            trend_pct = round(((current_row.value - prev_row.value) / prev_row.value) * 100, 2)

        variables[var.key] = {
            "value": current_row.value,
            "year": current_row.year,
            "unit_name": current_row.unit_name,
            "trend_pct": trend_pct,
            "historical": historical_by_var.get(var.var_id, []),  # ADDED: 10 years of history
            "metadata": {
                "key": var.key,
                "name": var.name_pl,
                "unit": var.unit,
                "category": var.category,
                "tier": var.tier,
                "level": var.level,
                "format_type": var.format_type,
            }
        }

    # Get last refresh timestamp
    stmt = select(GUSDataRefreshLog.last_refresh).order_by(
        desc(GUSDataRefreshLog.last_refresh)
    ).limit(1)
    last_refresh = await session.scalar(stmt)

    return {
        "variables": variables,
        "user_tier": user_tier,
        "latest_year": latest_year,
        "last_refresh": last_refresh.isoformat() if last_refresh else None,
        "count": len(variables)
    }


@router.get("/section/{section_key}")
async def get_section(
    section_key: str,
    years_back: int = 10,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_premium_user)  # Premium tier required
):
    """
    Get complete section data with trends and comparisons (Gmina data only)

    Returns ONLY variables with actual data for gmina Rybno.
    Comparisons: Gmina Rybno vs Powiat Działdowski (not national).
    Hidden sections: transport, bezpieczenstwo, turystyka (no gmina data).

    Args:
        section_key: Category key (demografia, rynek_pracy, etc.)
        years_back: Number of years for historical trend (default: 10)

    Returns:
        - section: Section metadata
        - variables: Dict with current values, historical trends, powiat comparison
        - latest_year: Most recent data year

    Requires: Premium tier
    """
    # Validate section exists
    if section_key not in CATEGORIES:
        raise HTTPException(status_code=404, detail=f"Section '{section_key}' not found")

    # Get variables for this category - use actual DB data (all vars with Rybno data)
    all_section_vars = get_gmina_variables_for_category(section_key)
    # Filter to variables that have actual data in DB for Rybno
    section_vars = [v for v in all_section_vars if v.var_id in GMINA_AVAILABLE_VAR_IDS]
    if not section_vars:
        # Check if category exists but has no gmina data
        all_category_vars = get_variables_for_category(section_key)
        if all_category_vars:
            raise HTTPException(
                status_code=404,
                detail=f"Section '{section_key}' has no data available for gmina Rybno"
            )
        raise HTTPException(status_code=404, detail=f"No variables found for section '{section_key}'")

    # Check user has access to at least some variables in this section
    user_tier = current_user.tier
    allowed_vars = get_gmina_variables_for_tier(user_tier)  # CHANGED: Only gmina data
    allowed_keys = {v.key for v in allowed_vars}
    accessible_vars = [v for v in section_vars if v.key in allowed_keys]

    if not accessible_vars:
        raise HTTPException(
            status_code=403,
            detail=f"Section '{section_key}' requires premium or business tier"
        )

    # Get latest year from DB (check all available data)
    var_ids = [v.var_id for v in accessible_vars]
    stmt = select(GUSGminaStats.year).where(
        GUSGminaStats.var_id.in_(var_ids)
    ).order_by(desc(GUSGminaStats.year)).limit(1)
    latest_year = await session.scalar(stmt)

    if not latest_year:
        raise HTTPException(status_code=404, detail="No GUS data available in database")

    # CRITICAL FIX: ALL variables in GMINA_AVAILABLE_VAR_IDS have data for Rybno,
    # regardless of their "level" metadata field (some level="powiat" vars have gmina data)
    # ALWAYS fetch from unit_id="Rybno" for all accessible variables
    var_ids = [v.var_id for v in accessible_vars]

    # Fetch current year data - ALL from Rybno
    current_data = {}
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == UNIT_IDS["Rybno"],
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year == latest_year
        )
    )
    result = await session.execute(stmt)
    for row in result.scalars():
        current_data[row.var_id] = row

    # Fetch historical data - ALL from Rybno (10 years back)
    start_year = latest_year - years_back + 1
    historical_by_var = {}

    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == UNIT_IDS["Rybno"],
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year >= start_year,
            GUSGminaStats.year <= latest_year
        )
    ).order_by(GUSGminaStats.var_id, GUSGminaStats.year)
    result = await session.execute(stmt)
    for row in result.scalars():
        if row.var_id not in historical_by_var:
            historical_by_var[row.var_id] = []
        historical_by_var[row.var_id].append({
            "year": row.year,
            "value": row.value
        })

    # Fetch comparison data (all gminy + powiat, latest year only)
    all_unit_ids = list(UNIT_IDS.values()) + [UNIT_ID_POWIAT]
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id.in_(all_unit_ids),
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year == latest_year
        )
    ).order_by(GUSGminaStats.var_id, desc(GUSGminaStats.value))
    comparison_result = await session.execute(stmt)
    comparison_rows = comparison_result.scalars().all()

    # Group comparison data by var_id
    comparison_by_var = {}
    for row in comparison_rows:
        if row.var_id not in comparison_by_var:
            comparison_by_var[row.var_id] = []
        comparison_by_var[row.var_id].append({
            "unit_id": row.unit_id,
            "unit_name": row.unit_name,
            "value": row.value,
            "year": latest_year
        })

    # Fetch previous year data for trend_pct calculation - ALL from Rybno
    prev_data = {}
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == UNIT_IDS["Rybno"],
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year == latest_year - 1
        )
    )
    result = await session.execute(stmt)
    for row in result.scalars():
        prev_data[row.var_id] = row

    # Fetch powiat data for comparison (gmina vs powiat)
    powiat_comparison_data = {}
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == UNIT_ID_POWIAT,
            GUSGminaStats.var_id.in_(var_ids),
            GUSGminaStats.year == latest_year
        )
    )
    powiat_result = await session.execute(stmt)
    powiat_rows = powiat_result.scalars().all()

    # Group powiat data by var_id
    for row in powiat_rows:
        powiat_comparison_data[row.var_id] = row.value

    # Get last refresh timestamp
    stmt = select(GUSDataRefreshLog.last_refresh).order_by(
        desc(GUSDataRefreshLog.last_refresh)
    ).limit(1)
    last_refresh = await session.scalar(stmt)

    # Build response - format matches frontend GUSSectionVariable type
    variables = {}
    for var in accessible_vars:
        current_row = current_data.get(var.var_id)
        if not current_row:
            continue

        # Calculate trend_pct (YoY change)
        prev_row = prev_data.get(var.var_id)
        trend_pct = None
        if prev_row and prev_row.value and prev_row.value != 0:
            trend_pct = round(((current_row.value - prev_row.value) / prev_row.value) * 100, 2)

        # Build powiat_comparison (gmina vs powiat)
        powiat_comparison = None
        powiat_val = powiat_comparison_data.get(var.var_id)
        if powiat_val and current_row.value:
            powiat_comparison = {
                "powiat_value": powiat_val,
                "gmina_value": current_row.value,
                "percentage_of_powiat": round((current_row.value / powiat_val) * 100, 2),
                "difference": round(current_row.value - powiat_val, 2),
                "year": latest_year
            }

        # Format matches GUSSectionVariable { current: GUSVariableValue, trend, comparison, powiat_comparison }
        variables[var.key] = {
            "current": {
                "value": current_row.value,
                "year": current_row.year,
                "trend_pct": trend_pct,
                "metadata": {
                    "key": var.key,
                    "name": var.name_pl,
                    "unit": var.unit,
                    "category": var.category,
                    "tier": var.tier,
                    "level": var.level,
                    "format_type": var.format_type,
                }
            },
            "trend": historical_by_var.get(var.var_id, []),
            "comparison": comparison_by_var.get(var.var_id, []),
            "powiat_comparison": powiat_comparison,  # CHANGED: gmina vs powiat, not national
        }

    return {
        "section_key": section_key,
        "section_name": CATEGORIES[section_key]["name"],
        "section_icon": CATEGORIES[section_key]["icon"],
        "variables": variables,
        "user_tier": user_tier,
        "latest_year": latest_year,
        "last_refresh": last_refresh.isoformat() if last_refresh else None,
        "count": len(variables)
    }


@router.get("/variable/{var_key}/detail")
async def get_variable_detail(
    var_key: str,
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get detailed data for a single variable with full history and comparisons

    Args:
        var_key: Variable key (e.g., "unemployment_rate")

    Returns:
        - variable: Variable metadata
        - current: Current year value
        - historical_trend: All years available in database
        - comparison_gminy: Comparison across all gminy + powiat (latest year)
        - national_comparison: % of national and voivodeship averages

    Access control: Based on variable tier
    """
    # Get variable from registry
    var = get_variable(var_key)
    if not var:
        raise HTTPException(status_code=404, detail=f"Variable '{var_key}' not found")

    # Check access
    if not check_variable_access(var_key, current_user):
        raise HTTPException(
            status_code=403,
            detail=f"This variable requires {var.tier} subscription"
        )

    # Determine unit_id based on variable level
    if var.level == "powiat":
        unit_id = UNIT_ID_POWIAT
        unit_name = "Powiat Działdowski"
    else:
        unit_id = UNIT_IDS["Rybno"]
        unit_name = "Rybno"

    # Get latest year from DB for this specific variable
    stmt = select(GUSGminaStats.year).where(
        and_(
            GUSGminaStats.unit_id == unit_id,
            GUSGminaStats.var_id == var.var_id
        )
    ).order_by(desc(GUSGminaStats.year)).limit(1)
    latest_year = await session.scalar(stmt)

    if not latest_year:
        raise HTTPException(status_code=404, detail="No GUS data available in database")

    # Fetch current year data
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == unit_id,
            GUSGminaStats.var_id == var.var_id,
            GUSGminaStats.year == latest_year
        )
    )
    current_row = await session.scalar(stmt)

    if not current_row:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {var_key} in year {latest_year}"
        )

    # Fetch full historical trend (all years in DB)
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id == unit_id,
            GUSGminaStats.var_id == var.var_id
        )
    ).order_by(GUSGminaStats.year)
    historical_result = await session.execute(stmt)
    historical_trend = [
        {"year": row.year, "value": row.value}
        for row in historical_result.scalars()
    ]

    # Fetch comparison data (all gminy + powiat, latest year)
    all_unit_ids = list(UNIT_IDS.values()) + [UNIT_ID_POWIAT]
    stmt = select(GUSGminaStats).where(
        and_(
            GUSGminaStats.unit_id.in_(all_unit_ids),
            GUSGminaStats.var_id == var.var_id,
            GUSGminaStats.year == latest_year
        )
    ).order_by(desc(GUSGminaStats.value))
    comparison_result = await session.execute(stmt)
    comparison_gminy = [
        {
            "unit_id": row.unit_id,
            "unit_name": row.unit_name,
            "value": row.value,
            "rank": idx + 1
        }
        for idx, row in enumerate(comparison_result.scalars())
    ]

    # Fetch national averages
    stmt = select(GUSNationalAverages).where(
        and_(
            GUSNationalAverages.var_id == var.var_id,
            GUSNationalAverages.year == latest_year
        )
    )
    national_result = await session.execute(stmt)
    national_rows = {row.level: row.value for row in national_result.scalars()}

    # Calculate % of national average
    national_pct = None
    voivodeship_pct = None
    if national_rows.get("national") and current_row.value:
        national_pct = round((current_row.value / national_rows["national"]) * 100, 2)
    if national_rows.get("voivodeship") and current_row.value:
        voivodeship_pct = round((current_row.value / national_rows["voivodeship"]) * 100, 2)

    return {
        "variable": {
            "key": var.key,
            "var_id": var.var_id,
            "name": var.name_pl,
            "unit": var.unit,
            "category": var.category,
            "tier": var.tier,
            "level": var.level,
            "format_type": var.format_type,
        },
        "current": {
            "value": current_row.value,
            "year": current_row.year,
            "unit_id": current_row.unit_id,
            "unit_name": current_row.unit_name,
        },
        "historical_trend": historical_trend,
        "comparison_gminy": comparison_gminy,
        "national_comparison": {
            "national_avg": national_rows.get("national"),
            "national_pct": national_pct,
            "voivodeship_avg": national_rows.get("voivodeship"),
            "voivodeship_pct": voivodeship_pct,
        },
        "latest_year": latest_year,
        "total_years": len(historical_trend),
    }


@router.get("/freshness")
async def get_freshness(
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get data freshness status - when was data last refreshed

    Returns:
        - last_global_refresh: Most recent refresh timestamp
        - by_category: Refresh status grouped by category
        - total_variables: Number of variables tracked

    No auth required (filters by user tier)
    """
    # Get user's allowed variables
    user_tier = current_user.tier if current_user else "free"
    allowed_vars = get_variables_for_tier(user_tier)
    allowed_var_keys = {v.key for v in allowed_vars}

    # Fetch all refresh logs
    stmt = select(GUSDataRefreshLog).order_by(desc(GUSDataRefreshLog.last_refresh))
    result = await session.execute(stmt)
    all_logs = result.scalars().all()

    # Filter logs to only allowed variables
    filtered_logs = [log for log in all_logs if log.var_key in allowed_var_keys]

    if not filtered_logs:
        return {
            "last_global_refresh": None,
            "by_category": {},
            "total_variables": 0,
            "user_tier": user_tier
        }

    # Get most recent refresh
    last_global_refresh = max(log.last_refresh for log in filtered_logs)

    # Group by category
    by_category = {}
    for log in filtered_logs:
        var = get_variable(log.var_key)
        if not var:
            continue

        category = var.category
        if category not in by_category:
            by_category[category] = {
                "category_name": CATEGORIES[category]["name"],
                "variables": [],
                "last_refresh": log.last_refresh,
                "total_records_updated": 0,
                "success_count": 0,
                "failed_count": 0,
            }

        by_category[category]["variables"].append({
            "var_key": log.var_key,
            "var_name": var.name_pl,
            "last_refresh": log.last_refresh.isoformat() if log.last_refresh else None,
            "status": log.status,
            "records_updated": log.records_updated,
            "error_message": log.error_message,
        })

        by_category[category]["total_records_updated"] += log.records_updated
        if log.status == "success":
            by_category[category]["success_count"] += 1
        elif log.status == "failed":
            by_category[category]["failed_count"] += 1

        # Update category's last_refresh to most recent
        if log.last_refresh > by_category[category]["last_refresh"]:
            by_category[category]["last_refresh"] = log.last_refresh

    # Convert last_refresh to ISO format for each category
    for category_data in by_category.values():
        category_data["last_refresh"] = (
            category_data["last_refresh"].isoformat()
            if category_data["last_refresh"]
            else None
        )

    return {
        "last_global_refresh": last_global_refresh.isoformat() if last_global_refresh else None,
        "by_category": by_category,
        "total_variables": len(filtered_logs),
        "user_tier": user_tier
    }


@router.get("/variables/list")
async def list_variables(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Get list of available variables for current user's tier

    Returns:
        - variables: List of variable metadata (filtered by tier)
        - user_tier: Current user's tier
        - total_available: Number of variables available to user
    """
    user_tier = current_user.tier if current_user else "free"
    allowed_vars = get_variables_for_tier(user_tier)

    # Build metadata dict
    filtered_metadata = {}
    for var in allowed_vars:
        filtered_metadata[var.key] = {
            "key": var.key,
            "var_id": var.var_id,
            "name": var.name_pl,
            "unit": var.unit,
            "category": var.category,
            "tier": var.tier,
            "level": var.level,
            "format_type": var.format_type,
        }

    # Group by category
    by_category = {}
    for var in allowed_vars:
        category = var.category
        if category not in by_category:
            by_category[category] = []
        by_category[category].append({
            "key": var.key,
            "var_id": var.var_id,
            "name": var.name_pl,
            "unit": var.unit,
            "tier": var.tier,
            "level": var.level,
        })

    # Calculate tier counts
    free_count = len(get_variables_for_tier("free"))
    premium_count = len(get_variables_for_tier("premium"))
    business_count = len(get_variables_for_tier("business"))

    return {
        "user_tier": user_tier,
        "total_available": len(allowed_vars),
        "variables": filtered_metadata,
        "by_category": by_category,
        "tiers": {
            "free": {"count": free_count, "price": "0 zł/mc"},
            "premium": {"count": premium_count, "price": "19 zł/mc"},
            "business": {"count": business_count, "price": "99 zł/mc"}
        }
    }


@router.get("/categories")
async def get_categories(
    session: AsyncSession = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get available categories for user's tier - based on actual DB data

    Returns categories with actual data for gmina Rybno (from gus_gmina_stats table).
    Uses category column from database, not gus_variables.py level field.

    Returns:
        List of categories with variable counts from database
    """
    from sqlalchemy import select, func, distinct

    user_tier = current_user.tier if current_user else "free"

    # Query DB for categories with Rybno data
    stmt = select(
        GUSGminaStats.category,
        func.count(func.distinct(GUSGminaStats.var_id)).label('var_count')
    ).where(
        and_(
            GUSGminaStats.unit_id == UNIT_IDS["Rybno"],
            GUSGminaStats.category.isnot(None)
        )
    ).group_by(GUSGminaStats.category)

    result = await session.execute(stmt)
    db_categories = {row.category: row.var_count for row in result}

    # Build response - match with CATEGORIES metadata
    categories = {}
    for cat_key, cat_info in CATEGORIES.items():
        if cat_key in db_categories:
            var_count = db_categories[cat_key]

            # Get tier-filtered variables for this category
            tier_vars = get_gmina_variables_for_tier(user_tier)
            category_vars = [v for v in tier_vars if v.category == cat_key and v.var_id in GMINA_AVAILABLE_VAR_IDS]

            if len(category_vars) > 0:
                categories[cat_key] = {
                    "key": cat_key,
                    "name": cat_info["name"],
                    "icon": cat_info["icon"],
                    "order": cat_info["order"],
                    "count": len(category_vars),
                    "total_variables": var_count,
                    "variables": [
                        {
                            "key": v.key,
                            "name": v.name_pl,
                            "unit": v.unit,
                            "tier": v.tier,
                        }
                        for v in category_vars
                    ]
                }

    return {
        "user_tier": user_tier,
        "categories": categories,
        "note": f"Showing {len(categories)} categories with actual gmina Rybno data from database."
    }


# Legacy endpoints removed (2026-02-06):
# - /variable/{var_key} → replaced by /variable/{var_key}/detail (DB-only)
# - /multi-metric → removed (can be re-added later if needed as DB-only)
# - /trend/{var_id} → replaced by /variable/{var_key}/detail
# - /comparison/{var_id} → replaced by /section/{section_key}
