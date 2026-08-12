"""
Business Report Job — TYGODNIOWY raport e-mail dla firm z wizytówkami.

Poniedziałek 8:30. Dwa warianty:
- plan Firma lokalna (is_premium): pełny raport — wyświetlenia wizytówki,
  kontakty i pokazy z minionego tygodnia, opublikowane ogłoszenia, zasięg newslettera
  (namacalny dowód wartości 49 zł/mc — obiecany w ofercie planu)
- wizytówka darmowa (verified): teaser z licznikiem wyświetleń i CTA na plan

Przyrost wyświetleń liczony z snapshotu views_last_report (bez tabeli historii);
po wysyłce snapshot jest przesuwany na bieżącą wartość.
"""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select, func

from src.config import settings
from src.database.schema import (
    CEIDGBusiness, BusinessProfile, BusinessAnnouncement, User,
    NewsletterSubscriber,
)
from src.newsletter.email_service import EmailService
from src.utils.logger import setup_logger

logger = setup_logger("BusinessReportJob")

MONTHS_PL = [
    "styczniu", "lutym", "marcu", "kwietniu", "maju", "czerwcu",
    "lipcu", "sierpniu", "wrześniu", "październiku", "listopadzie", "grudniu",
]


def _report_html(
    nazwa: str,
    is_premium: bool,
    month_label: str,
    views_total: int,
    views_delta: int,
    impressions_delta: int,
    announcements_count: int,
    newsletter_reach: int,
) -> str:
    app_url = settings.APP_URL
    stat_row = (
        "<tr><td style='padding:8px 12px;color:#555;'>{label}</td>"
        "<td style='padding:8px 12px;text-align:right;font-weight:bold;color:#1e3a5f;'>{value}</td></tr>"
    )
    # Nazwy pozycji muszą mówić, CO zmierzono. „Wyświetlenia wizytówki" brzmiały
    # jak odwiedziny, a liczyły pokazy karty w katalogu — czyli także wtedy, gdy
    # ktoś przewinął listę, nie patrząc. Rozdzielone 12.08.2026
    rows = stat_row.format(
        label=f"Pokazy wizytówki ({month_label})", value=impressions_delta
    )
    rows += stat_row.format(
        label=f"Kliknięcia w kontakt ({month_label})", value=views_delta
    )
    rows += stat_row.format(label="Kliknięcia w kontakt (łącznie)", value=views_total)
    if is_premium:
        rows += stat_row.format(label=f"Ogłoszenia opublikowane ({month_label})", value=announcements_count)
        rows += stat_row.format(label="Zasięg newslettera (subskrybenci)", value=newsletter_reach)

    if is_premium:
        intro = (
            "Dziękujemy, że jesteś z nami w planie <strong>Firma lokalna</strong>. "
            "Oto co Twoja wizytówka wypracowała w minionym tygodniu:"
        )
        cta = (
            f"<p>Pamiętaj: w każdym miesiącu możesz opublikować <strong>2 ogłoszenia</strong> "
            f"i <strong>8 okazji „tu i teraz”</strong> — pojawią się na stronie głównej, "
            f"w feedzie aktualności i w newsletterze.</p>"
            f"<a href='{app_url}' class='btn'>Dodaj ogłoszenie</a>"
        )
    else:
        intro = (
            "Twoja darmowa wizytówka w katalogu firm RybnoLive pracowała w minionym miesiącu:"
        )
        cta = (
            f"<p>W planie <strong>Firma lokalna (49 zł/mc)</strong> Twoja firma byłaby wyróżniona "
            f"na stronie głównej portalu i w newsletterze, z możliwością publikacji ogłoszeń "
            f"i okazji. Napisz do nas: biuro@lumargo.pl</p>"
            f"<a href='{app_url}' class='btn'>Zobacz katalog firm</a>"
        )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; line-height: 1.6; color: #333; max-width: 560px; margin: 0 auto; padding: 16px; }}
            .btn {{ display: inline-block; background: #1e3a5f; color: white; padding: 12px 30px;
                    text-decoration: none; border-radius: 5px; margin: 12px 0; }}
            table {{ width: 100%; border-collapse: collapse; background: #f8fafc; border-radius: 8px; }}
            tr + tr td {{ border-top: 1px solid #e5e7eb; }}
        </style>
    </head>
    <body>
        <h2>📊 Raport miesięczny — {nazwa}</h2>
        <p>{intro}</p>
        <table>{rows}</table>
        {cta}
        <p style="font-size: 12px; color: #888;">
            RybnoLive · Centrum Operacyjne Mieszkańca · raport generowany automatycznie
            1. dnia miesiąca dla właścicieli wizytówek.
        </p>
    </body>
    </html>
    """


async def send_business_reports():
    """Wysyła raporty miesięczne do właścicieli zweryfikowanych wizytówek."""
    logger.info("Starting business weekly report job...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    email_service = EmailService()

    # Okno tygodniowe. Raport miesięczny docierał do firmy w chwili, gdy
    # o wizytówce dawno zapomniała, a przyrost z 30 dni nie mówi, KTÓRY post
    # albo która okazja zadziałała. Tydzień jest jednostką, w której właściciel
    # firmy jeszcze pamięta, co robił.
    now = datetime.utcnow()
    period_end = now
    period_start = now - timedelta(days=7)
    month_label = (
        f"{period_start.day} {MONTHS_PL[period_start.month - 1].lower()}"
        f" – {period_end.day} {MONTHS_PL[period_end.month - 1].lower()}"
    )

    stats = {"total": 0, "sent": 0, "failed": 0}

    try:
        async with async_session() as session:
            result = await session.execute(
                select(BusinessProfile, CEIDGBusiness, User)
                .join(CEIDGBusiness, CEIDGBusiness.id == BusinessProfile.business_id)
                .join(User, User.id == BusinessProfile.user_id)
                .where(BusinessProfile.claim_status == "verified")
            )
            rows = result.all()
            stats["total"] = len(rows)
            if not rows:
                logger.info("No verified business profiles — nothing to report")
                return stats

            reach_result = await session.execute(
                select(func.count()).select_from(NewsletterSubscriber)
                .where(NewsletterSubscriber.status == "active")
                .where(NewsletterSubscriber.confirmed_at.isnot(None))
            )
            newsletter_reach = reach_result.scalar() or 0

            for profile, business, user in rows:
                to_email = profile.email or user.email
                if not to_email:
                    continue
                try:
                    ann_result = await session.execute(
                        select(func.count()).select_from(BusinessAnnouncement)
                        .where(BusinessAnnouncement.business_id == business.id)
                        .where(BusinessAnnouncement.created_at >= period_start)
                        .where(BusinessAnnouncement.created_at < period_end)
                    )
                    announcements_count = ann_result.scalar() or 0

                    # Dwie różne liczby, świadomie rozdzielone (migracja
                    # `add_business_impressions`): pokazy to zasięg, kontakty to
                    # zainteresowanie. Do 12.08.2026 raport wysyłał pokazy pod
                    # nazwą „wyświetlenia wizytówki" — czyli liczbę zawyżoną
                    # o każde wejście do katalogu
                    views_delta = max(0, profile.views_count - profile.views_last_report)
                    impressions_delta = max(
                        0, profile.impressions_count - profile.impressions_last_report
                    )
                    html = _report_html(
                        nazwa=business.nazwa,
                        is_premium=profile.is_premium,
                        month_label=month_label,
                        views_total=profile.views_count,
                        views_delta=views_delta,
                        impressions_delta=impressions_delta,
                        announcements_count=announcements_count,
                        newsletter_reach=newsletter_reach,
                    )
                    result = await email_service.send_email(
                        to_email=to_email,
                        subject=f"📊 Twoja wizytówka {month_label} — raport RybnoLive",
                        html_content=html,
                    )
                    if result.get("status") == "sent":
                        stats["sent"] += 1
                        profile.views_last_report = profile.views_count
                        profile.impressions_last_report = profile.impressions_count
                        session.add(profile)
                    else:
                        stats["failed"] += 1
                        logger.error(f"Report send failed for {to_email}: {result.get('error')}")
                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"Report error for business={business.id}: {e}")

            await session.commit()
    finally:
        await engine.dispose()

    logger.info(f"Business report job completed: {stats}")
    return stats


def run_business_reports():
    """Sync wrapper for APScheduler."""
    asyncio.run(send_business_reports())
