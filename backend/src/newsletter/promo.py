"""
Sekcja „Polecane firmy" w newsletterze (plan Firma lokalna).

Dostarcza dane do szablonów weekly.html / daily.html:
- promoted_businesses: wizytówki premium z deterministyczną rotacją dzienną,
  żeby każda firma pojawiała się cyklicznie, a nie tylko pierwsza z listy
- business_announcements: aktywne ogłoszenia/okazje

Obecność w newsletterze jest zliczana w raporcie miesięcznym firmy
(business_report_job) na podstawie tej samej rotacji.
"""
from datetime import datetime
from typing import Any, Dict, List

from sqlmodel import select

from src.database.schema import CEIDGBusiness, BusinessProfile, BusinessAnnouncement
from src.utils.logger import setup_logger

logger = setup_logger("NewsletterPromo")


def rotate_for_today(items: List[Any], count: int) -> List[Any]:
    """Deterministyczna rotacja: offset wg dnia roku — bez stanu w bazie."""
    if not items or count <= 0:
        return []
    offset = datetime.utcnow().timetuple().tm_yday % len(items)
    rotated = items[offset:] + items[:offset]
    return rotated[:count]


async def get_newsletter_promo(
    session,
    max_promoted: int = 2,
    max_announcements: int = 2,
) -> Dict[str, List[Dict[str, Any]]]:
    """Zwraca kontekst sekcji reklamowej; puste listy gdy brak firm premium."""
    from src.utils.pkd_mapping import get_friendly_category

    now = datetime.utcnow()
    promo: Dict[str, List[Dict[str, Any]]] = {
        "promoted_businesses": [],
        "business_announcements": [],
    }

    try:
        result = await session.execute(
            select(CEIDGBusiness, BusinessProfile)
            .join(BusinessProfile, BusinessProfile.business_id == CEIDGBusiness.id)
            .where(BusinessProfile.claim_status == "verified")
            .where(BusinessProfile.is_premium == True)  # noqa: E712
            .where(CEIDGBusiness.opted_out == False)  # noqa: E712
            .where(CEIDGBusiness.status != "WYKRESLONY")
            .order_by(CEIDGBusiness.id)
        )
        premium_rows = result.all()

        for business, profile in rotate_for_today(premium_rows, max_promoted):
            desc = (profile.description or "").strip()
            promo["promoted_businesses"].append({
                "nazwa": business.nazwa,
                "miasto": business.miasto,
                "branza": get_friendly_category(business.pkd_main) if business.pkd_main else None,
                "description": desc[:160] + ("…" if len(desc) > 160 else ""),
                "telefon": profile.telefon,
                "godziny": profile.godziny,
            })

        result = await session.execute(
            select(BusinessAnnouncement, CEIDGBusiness, BusinessProfile)
            .join(CEIDGBusiness, CEIDGBusiness.id == BusinessAnnouncement.business_id)
            .join(BusinessProfile, BusinessProfile.business_id == CEIDGBusiness.id)
            .where(BusinessAnnouncement.is_active == True)  # noqa: E712
            .where(
                (BusinessAnnouncement.valid_until.is_(None))
                | (BusinessAnnouncement.valid_until > now)
            )
            .where(BusinessProfile.claim_status == "verified")
            .where(BusinessProfile.is_premium == True)  # noqa: E712
            .where(CEIDGBusiness.opted_out == False)  # noqa: E712
            .order_by(BusinessAnnouncement.created_at.desc())
            .limit(max_announcements)
        )
        for ann, business, profile in result.all():
            promo["business_announcements"].append({
                "title": ann.title,
                "body": ann.body,
                "nazwa": business.nazwa,
                "miasto": business.miasto,
                # kontakt podany przez firmę przy przejęciu wizytówki (zgoda)
                "telefon": profile.telefon,
                "valid_until_label": (
                    ann.valid_until.strftime("%d.%m %H:%M") if ann.valid_until else None
                ),
            })
    except Exception as e:
        # Sekcja reklamowa nigdy nie może zablokować wysyłki newslettera
        logger.error(f"Newsletter promo section failed: {e}")

    return promo
