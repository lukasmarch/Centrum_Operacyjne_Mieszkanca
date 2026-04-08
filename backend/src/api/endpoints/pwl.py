"""
Polska w Liczbach (PwL) API Endpoints

Udostępnia dane gminne uzupełniające GUS BDL:
- Nieruchomości (mieszkalnictwo gmina)
- Rynek pracy gmina (bezrobocie, pensja, pendlerzy)
- Bezpieczeństwo gmina (przestępczość)
- Transport gmina (ścieżki rowerowe, wypadki)
- Demografia (średni wiek, feminizacja, śluby)
- REGON sektory
- Finanse — historia budżetu i kategorie

Źródło: polskawliczbach.pl (Firecrawl scraping)
Dane: tylko zweryfikowane (is_verified=True)
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from src.database import get_session, User
from src.auth.dependencies import get_optional_user, get_business_user
from src.integrations.pwl_integration import (
    PWL_UNIT_ID,
    promote_to_verified,
    generate_comparison_report,
    parse_pwl_from_json,
)

router = APIRouter(tags=["pwl"])

# Sekcje dostępne dla Free / Premium
FREE_SECTIONS = {"demographics", "regon"}
PREMIUM_SECTIONS = {"real_estate", "labor_market", "education", "safety", "transport", "finance"}


@router.get("/rybno")
async def get_pwl_rybno(
    section: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user),
):
    """
    Zwraca dane PwL dla Gminy Rybno pogrupowane po sekcjach.

    - Free: demografia, REGON
    - Premium+: wszystkie sekcje (nieruchomości, rynek pracy, edukacja, bezpieczeństwo, transport, finanse)
    """
    tier = user.tier if user else "free"
    is_premium = tier in ("premium", "business")

    # Ustal dostępne sekcje
    allowed_sections = FREE_SECTIONS.copy()
    if is_premium:
        allowed_sections |= PREMIUM_SECTIONS

    if section and section not in allowed_sections:
        raise HTTPException(
            status_code=403,
            detail=f"Sekcja '{section}' wymaga konta Premium. Dostępne sekcje: {sorted(FREE_SECTIONS)}"
        )

    # Filtruj po sekcji jeśli podano
    sections_to_query = {section} if section else allowed_sections

    # Pobierz dane z bazy
    placeholders = ", ".join(f":s{i}" for i in range(len(sections_to_query)))
    params = {"uid": PWL_UNIT_ID}
    for i, s in enumerate(sections_to_query):
        params[f"s{i}"] = s

    result = await db.execute(
        text(f"""
            SELECT section, field_key, field_name_pl, year, value, extra_data, fetched_at
            FROM pwl_gmina_stats
            WHERE unit_id = :uid
              AND is_verified = true
              AND section IN ({placeholders})
            ORDER BY section, field_key
        """),
        params
    )
    rows = result.fetchall()

    # Grupuj po sekcji
    sections_data: dict = {}
    for row in rows:
        sec, fk, name, year, val, extra, fetched = row
        sections_data.setdefault(sec, {"fields": [], "fetched_at": str(fetched)})
        entry = {
            "key": fk,
            "name": name,
            "year": year,
        }
        if val is not None:
            entry["value"] = val
        if extra is not None:
            entry["extra_data"] = extra
        sections_data[sec]["fields"].append(entry)

    return {
        "unit_id": PWL_UNIT_ID,
        "unit_name": "Rybno",
        "source": "polskawliczbach.pl",
        "tier_access": tier,
        "sections": sections_data,
        "available_premium_sections": sorted(PREMIUM_SECTIONS) if not is_premium else [],
    }


@router.get("/sections")
async def get_pwl_sections(
    db: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user),
):
    """Zwraca listę dostępnych sekcji z liczbą pól i datą ostatniego importu."""
    result = await db.execute(
        text("""
            SELECT section,
                   COUNT(*) as field_count,
                   MAX(fetched_at) as last_fetched,
                   MAX(year) as data_year
            FROM pwl_gmina_stats
            WHERE unit_id = :uid AND is_verified = true
            GROUP BY section
            ORDER BY section
        """),
        {"uid": PWL_UNIT_ID}
    )
    rows = result.fetchall()

    tier = user.tier if user else "free"
    is_premium = tier in ("premium", "business")

    sections = []
    for sec, count, last_fetched, data_year in rows:
        sections.append({
            "section": sec,
            "field_count": count,
            "data_year": data_year,
            "last_fetched": str(last_fetched) if last_fetched else None,
            "requires_premium": sec in PREMIUM_SECTIONS,
            "accessible": is_premium or sec in FREE_SECTIONS,
        })

    return {"sections": sections}


@router.get("/compare")
async def get_pwl_compare(
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_business_user),
):
    """
    [Business] Raport porównawczy PwL vs GUS BDL dla nakładających się zmiennych.
    Używany do weryfikacji spójności danych przed udostępnieniem.
    """
    # Pobierz ostatnie dane PwL z bazy (demographics + finance + education + labor_market)
    result = await db.execute(
        text("""
            SELECT section, field_key, value, year
            FROM pwl_gmina_stats
            WHERE unit_id = :uid AND is_verified = true
            ORDER BY section, field_key
        """),
        {"uid": PWL_UNIT_ID}
    )
    rows = result.fetchall()

    # Zrekonstruuj strukturę pwl_data do generate_comparison_report
    pwl_data: dict = {}
    for sec, fk, val, year in rows:
        pwl_data.setdefault(sec, {})
        pwl_data[sec][fk] = val

    # Mapowanie nazw sekcji PwL → nazwy w rybno_data.json
    # (demographics, finance, education, labor_market są takie same)
    report = await generate_comparison_report(pwl_data, db)

    mismatches = [r for r in report if r.get("match") is False]
    return {
        "report": report,
        "total_checked": len(report),
        "matches": len([r for r in report if r.get("match") is True]),
        "mismatches": len(mismatches),
        "no_gus_data": len([r for r in report if r.get("gus_value") is None]),
        "mismatch_details": mismatches,
    }


@router.get("/scrape-logs")
async def get_scrape_logs(
    limit: int = 10,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_business_user),
):
    """[Business] Historia scrapowań PwL."""
    result = await db.execute(
        text("""
            SELECT id, unit_id, scraped_at, status,
                   records_imported, records_updated, error_message
            FROM pwl_scrape_log
            WHERE unit_id = :uid
            ORDER BY scraped_at DESC
            LIMIT :lim
        """),
        {"uid": PWL_UNIT_ID, "lim": limit}
    )
    rows = result.fetchall()

    logs = []
    for row in rows:
        lid, uid, scraped_at, status, imported, updated, err = row
        logs.append({
            "id": lid,
            "scraped_at": str(scraped_at),
            "status": status,
            "records_imported": imported,
            "records_updated": updated,
            "error": err,
        })

    return {"logs": logs}


@router.post("/verify/{log_id}")
async def verify_scrape_log(
    log_id: int,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_business_user),
):
    """
    [Business] Zatwierdza dane z danego scrape_log_id (is_verified = True).
    Po zatwierdzeniu dane stają się widoczne przez /api/stats/pwl/rybno.
    """
    # Sprawdź czy log istnieje
    log_result = await db.execute(
        text("SELECT id, status FROM pwl_scrape_log WHERE id = :id"),
        {"id": log_id}
    )
    log_row = log_result.fetchone()
    if not log_row:
        raise HTTPException(status_code=404, detail=f"Log ID {log_id} nie istnieje")

    count = await promote_to_verified(PWL_UNIT_ID, log_id, db)

    # Zaktualizuj status logu
    await db.execute(
        text("UPDATE pwl_scrape_log SET status = 'verified' WHERE id = :id"),
        {"id": log_id}
    )
    await db.commit()

    return {
        "log_id": log_id,
        "verified_records": count,
        "message": f"Zatwierdzono {count} rekordów. Dane są teraz dostępne przez API."
    }
