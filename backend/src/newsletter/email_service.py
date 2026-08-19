"""
Email service using Resend for newsletter delivery
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import settings

logger = logging.getLogger("Newsletter.Email")

# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"

DAYS_PL = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
MONTHS_PL = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
             "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

# Paleta systemu (ciemne tło maila) — te same kolory co w makiecie briefingu
CAQI_COLORS = {
    "VERY_LOW": "#34d399",
    "LOW": "#34d399",
    "MEDIUM": "#fbbf24",
    "HIGH": "#f87171",
    "VERY_HIGH": "#f87171",
}

AGENT_COLORS = {
    "Redaktor": "#0ea5e9",
    "Urzędnik": "#f59e0b",
    "Strażnik": "#ef4444",
    "Przewodnik": "#10b981",
    "Organizator": "#06b6d4",
}
DEFAULT_AGENT = "Redaktor"

REPORT_CATEGORIES = {
    "emergency": ("Alarm / wypadek", "#ef4444"),
    "fire": ("Pożar", "#f97316"),
    "infrastructure": ("Infrastruktura", "#3b82f6"),
    "waste": ("Odpady", "#a78bfa"),
    "greenery": ("Zieleń", "#10b981"),
    "safety": ("Bezpieczeństwo", "#f59e0b"),
    "water": ("Woda / kanalizacja", "#06b6d4"),
    "other": ("Inne", "#8f8f8f"),
}


def plural_pl(n: int, one: str, few: str, many: str) -> str:
    """Polska odmiana rzeczownika po liczebniku (1 wydarzenie / 2 wydarzenia / 5 wydarzeń)."""
    if n == 1:
        return one
    if 12 <= n % 100 <= 14:
        return many
    return few if 2 <= n % 10 <= 4 else many


def app_link(path: str = "/", campaign: str = "briefing") -> str:
    """Link do serwisu z parametrami UTM. Ścieżki muszą istnieć w SECTION_TO_PATH (App.tsx)."""
    base = settings.APP_URL.rstrip("/")
    sep = "&" if "?" in path else "?"
    return f"{base}{path}{sep}utm_source=newsletter&utm_medium=email&utm_campaign={campaign}"


class EmailService:
    """Email sending service using Resend"""

    def __init__(self):
        self.resend = None
        if settings.RESEND_API_KEY:
            try:
                import resend
                resend.api_key = settings.RESEND_API_KEY
                self.resend = resend
                logger.info("Resend email service initialized")
            except ImportError:
                logger.warning("Resend package not installed. Run: pip install resend")
        else:
            logger.warning("RESEND_API_KEY not set. Email sending disabled.")

        # Initialize Jinja2 template environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Render an HTML email template with Jinja2.

        Args:
            template_name: Name of the template file (e.g., 'weekly.html')
            context: Dictionary of variables to pass to the template

        Returns:
            Rendered HTML string
        """
        template = self.jinja_env.get_template(template_name)

        # Add common context variables
        context.setdefault('app_url', settings.APP_URL)
        context.setdefault('current_year', datetime.now().year)

        return template.render(**context)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        reply_to: Optional[str] = None,
        unsubscribe_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email via Resend.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            reply_to: Optional reply-to address
            unsubscribe_url: Adres wypisu — trafia do nagłówka List-Unsubscribe,
                dzięki czemu Gmail/Outlook pokazują własny przycisk „Wypisz się"
                (bez tego skrzynki traktują newsletter jak zwykłą pocztę i częściej
                lądujemy w spamie)

        Returns:
            Dict with send result (id, status)
        """
        if not self.resend:
            logger.warning(f"Email not sent (no API key): {subject} -> {to_email}")
            return {"status": "skipped", "reason": "no_api_key"}

        try:
            params = {
                "from": f"{settings.NEWSLETTER_FROM_NAME} <{settings.NEWSLETTER_FROM_EMAIL}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            if unsubscribe_url:
                params["headers"] = {
                    "List-Unsubscribe": f"<{unsubscribe_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                }

            if reply_to:
                params["reply_to"] = reply_to

            result = self.resend.Emails.send(params)

            logger.info(f"Email sent: {subject} -> {to_email} (ID: {result.get('id', 'unknown')})")

            return {
                "status": "sent",
                "id": result.get("id"),
                "to": to_email
            }

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "to": to_email
            }

    def _common_context(
        self,
        to_email: str,
        unsubscribe_token: str,
        campaign: str,
    ) -> Dict[str, Any]:
        """Kontekst wspólny dla obu newsletterów: linki, stopka, przełącznik reklam."""
        now = datetime.now()
        return {
            "recipient_email": to_email,
            # Wypis obsługuje backend (frontend nie ma takiej strony) — patrz
            # newsletter/routes.py: GET/POST /api/newsletter/unsubscribe
            "unsubscribe_url": (
                f"{settings.API_URL.rstrip('/')}/api/newsletter/unsubscribe?token={unsubscribe_token}"
            ),
            "url_dashboard": app_link("/", campaign),
            "url_premium": app_link("/cennik", campaign),
            "url_terms": app_link("/regulamin", campaign),
            "url_reports": app_link("/zgloszenia", campaign),
            "sent_at_label": f"{now.day} {MONTHS_PL[now.month - 1]} {now.year}",
            # Reklama firm wraca dopiero, gdy sprzedamy plan „Firma lokalna"
            "ads_enabled": settings.NEWSLETTER_ADS_ENABLED,
        }

    async def send_weekly_newsletter(
        self,
        to_email: str,
        content: Dict[str, Any],
        unsubscribe_token: str
    ) -> Dict[str, Any]:
        """
        Send weekly newsletter to a subscriber.

        Args:
            to_email: Subscriber's email
            content: Newsletter content from generator
            unsubscribe_token: Token for unsubscribe link

        Returns:
            Send result
        """
        now = datetime.now()
        weekly_weather = content.get("weekly_weather")
        if weekly_weather and weekly_weather.get("caqi_level"):
            weekly_weather["color"] = CAQI_COLORS.get(weekly_weather["caqi_level"], "#a1a1a1")

        weekly_reports = content.get("weekly_reports")
        if weekly_reports and weekly_reports.get("by_category"):
            weekly_reports["categories"] = [
                {
                    "label": REPORT_CATEGORIES.get(cat, (cat, "#8f8f8f"))[0],
                    "color": REPORT_CATEGORIES.get(cat, (cat, "#8f8f8f"))[1],
                    "count": count,
                }
                for cat, count in weekly_reports["by_category"].items()
            ]

        # Build context for template
        context = {
            **self._common_context(to_email, unsubscribe_token, "weekly"),
            "subject": content.get("subject", "Tydzień w gminie Rybno"),
            "preheader": content.get("preview_text", ""),
            "date_header": f"{DAYS_PL[now.weekday()]} · {now.day} {MONTHS_PL[now.month - 1]} {now.year}",
            "status_line": content.get("sections", {}).get("greeting"),
            "sections": content.get("sections", {}),
            "weekly_weather": weekly_weather,
            "weekly_reports": weekly_reports,
            "puls": content.get("puls"),
            # Sekcja reklamowa „Polecane firmy" (plan Firma lokalna)
            "promoted_businesses": content.get("promoted_businesses", []),
            "business_announcements": content.get("business_announcements", []),
        }

        # Process events to extract day/month for display
        DATE_FORMATS = [
            "%Y-%m-%d",       # 2026-02-18
            "%d.%m.%Y",       # 18.02.2026
            "%d-%m-%Y",       # 18-02-2026
            "%d/%m/%Y",       # 18/02/2026
            "%d %B %Y",       # 18 February 2026
            "%d %b %Y",       # 18 Feb 2026
        ]
        MONTHS_PL_LONG = [
            "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
            "lipca", "sierpnia", "września", "października", "listopada", "grudnia"
        ]
        MONTHS_PL_SHORT = ["STY", "LUT", "MAR", "KWI", "MAJ", "CZE",
                           "LIP", "SIE", "WRZ", "PAŹ", "LIS", "GRU"]

        def parse_event_date(date_str: str):
            # Try Polish format first: "19 lutego 2026"
            parts = date_str.strip().split()
            if len(parts) == 3:
                try:
                    day = int(parts[0])
                    month_idx = next(
                        (i + 1 for i, m in enumerate(MONTHS_PL_LONG) if m == parts[1].lower()),
                        None
                    )
                    year = int(parts[2])
                    if month_idx and 1 <= day <= 31:
                        return datetime(year, month_idx, day)
                except (ValueError, StopIteration):
                    pass
            # Fallback: standard formats
            for fmt in DATE_FORMATS:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None

        # Wydarzenia liczymy z bazy; lista od AI to tylko fallback (może mieć zmyślone daty)
        events = content.get("events_db") or []
        if not events:
            events = context["sections"].get("events", [])
            for event in events:
                if "date" in event:
                    parsed = parse_event_date(event["date"])
                    if parsed:
                        event["day"] = parsed.day
                        event["month"] = MONTHS_PL_SHORT[parsed.month - 1]
                    else:
                        event["day"] = "?"
                        event["month"] = "?"

        context["events"] = events
        context["events_word"] = plural_pl(len(events), "wydarzenie", "wydarzenia", "wydarzeń")

        # Render template
        html = self.render_template("weekly.html", context)

        # Send email
        return await self.send_email(
            to_email=to_email,
            subject=context["subject"],
            html_content=html,
            unsubscribe_url=context["unsubscribe_url"]
        )

    async def send_daily_newsletter(
        self,
        to_email: str,
        content: Dict[str, Any],
        unsubscribe_token: str,
        weather_temp: Optional[float] = None,
        recipient_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send daily newsletter to a Premium subscriber.

        Args:
            to_email: Subscriber's email
            content: Newsletter content from generator
            unsubscribe_token: Token for unsubscribe link
            weather_temp: Current temperature
            recipient_name: Imię odbiorcy do powitania (mianownik — inne przypadki
                wymagałyby odmiany, więc imię pada tylko w „Dzień dobry, X.")

        Returns:
            Send result
        """
        air_quality = content.get("air_quality")
        if air_quality:
            air_quality["color"] = CAQI_COLORS.get(air_quality.get("caqi_level"), "#a1a1a1")

        weather = content.get("weather")
        if not weather and weather_temp is not None:
            weather = {"temperature": round(weather_temp), "description": None,
                       "temp_min": None, "temp_max": None, "wind_kmh": None}

        # Wnioski AI jako karty agentów — kolor i nazwa muszą pochodzić z naszej
        # listy, nie z odpowiedzi modelu (fallback: Redaktor)
        highlights = []
        for item in content.get("sections", {}).get("highlights", []) or []:
            agent = item.get("agent") if item.get("agent") in AGENT_COLORS else DEFAULT_AGENT
            highlights.append({
                "agent": agent,
                "color": AGENT_COLORS[agent],
                "meta": item.get("meta") or "",
                "text": item.get("text", ""),
            })

        reports = []
        for r in content.get("reports_today", []) or []:
            label, color = REPORT_CATEGORIES.get(r.get("category"), REPORT_CATEGORIES["other"])
            reports.append({**r, "category_label": label, "color": color})

        events = content.get("events_today_db") or content.get("sections", {}).get("events_today", [])
        sources_count = content.get("sources_count") or 0

        context = {
            **self._common_context(to_email, unsubscribe_token, "briefing"),
            "subject": content.get("subject", "Poranny briefing"),
            "preheader": content.get("preview_text", ""),
            "date_header": content.get("date_header", ""),
            "status_line": content.get("sections", {}).get("status_line")
                           or content.get("sections", {}).get("greeting"),
            "recipient_name": recipient_name,
            "sections": content.get("sections", {}),
            "weather": weather,
            "air_quality": air_quality,
            "name_days": content.get("name_days", []),
            "special_day": content.get("special_day", ""),
            "highlights": highlights,
            "sources_count": sources_count,
            "sources_word": plural_pl(sources_count, "źródło", "źródła", "źródeł"),
            "cinema_evening": content.get("cinema_evening", []),
            "reports_today": reports,
            "reports_date_label": content.get("reports_date_label", "dzisiaj"),
            "events": events,
            "events_word": plural_pl(len(events), "wydarzenie", "wydarzenia", "wydarzeń"),
            "promoted_businesses": content.get("promoted_businesses", []),
            "business_announcements": content.get("business_announcements", []),
        }

        # Render template
        html = self.render_template("daily.html", context)

        # Send email
        return await self.send_email(
            to_email=to_email,
            subject=context["subject"],
            html_content=html,
            unsubscribe_url=context["unsubscribe_url"]
        )

    async def send_batch(
        self,
        emails: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Send emails in batch.

        Args:
            emails: List of dicts with 'to', 'subject', 'html' keys

        Returns:
            Summary of results
        """
        results = {
            "total": len(emails),
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

        for email_data in emails:
            result = await self.send_email(
                to_email=email_data["to"],
                subject=email_data["subject"],
                html_content=email_data["html"]
            )

            if result["status"] == "sent":
                results["sent"] += 1
            elif result["status"] == "failed":
                results["failed"] += 1
                results["errors"].append({
                    "to": email_data["to"],
                    "error": result.get("error")
                })
            else:
                results["skipped"] += 1

        return results

    async def send_confirmation_email(
        self,
        to_email: str,
        confirmation_token: str
    ) -> Dict[str, Any]:
        """
        Send subscription confirmation email.

        Args:
            to_email: New subscriber's email
            confirmation_token: Token for confirmation link

        Returns:
            Send result
        """
        confirmation_url = f"{settings.APP_URL}/newsletter/confirm?token={confirmation_token}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; line-height: 1.6; color: #333; }}
                .btn {{ display: inline-block; background: #1e3a5f; color: white; padding: 12px 30px;
                        text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h2>Potwierdź subskrypcję newslettera</h2>
            <p>Dziękujemy za zapisanie się do newslettera RybnoLive!</p>
            <p>Kliknij poniższy przycisk, aby potwierdzić swoją subskrypcję:</p>
            <a href="{confirmation_url}" class="btn">Potwierdzam subskrypcję</a>
            <p style="font-size: 12px; color: #888;">
                Jeśli nie zapisywałeś/aś się na newsletter, zignoruj tę wiadomość.
            </p>
        </body>
        </html>
        """

        return await self.send_email(
            to_email=to_email,
            subject="Potwierdź subskrypcję newslettera - RybnoLive",
            html_content=html
        )

    async def send_business_claim_decision(
        self,
        to_email: str,
        business_name: str,
        approved: bool,
    ) -> Dict[str, Any]:
        """Decyzja w sprawie przejęcia wizytówki — do zgłaszającego.

        Wysyłamy TAKŻE odmowę, choć milczenie byłoby wygodniejsze. Zgłoszenie,
        które znika bez słowa, wygląda dla człowieka jak awaria serwisu — wraca
        więc i składa je ponownie, a my za każdym razem oceniamy je od zera.
        Odmowa nie podaje powodu (bywa nim „nie potwierdziliśmy, że to Pana
        firma"), za to zawsze wskazuje drogę odwoławczą: adres, pod którym
        siedzi człowiek.
        """
        panel_url = app_link("/profil", campaign="wizytowka")

        if approved:
            subject = f"✅ Wizytówka „{business_name}” jest Twoja"
            body = f"""
            <h2>Wizytówka potwierdzona</h2>
            <p>Potwierdziliśmy Twoje zgłoszenie firmy <strong>{business_name}</strong>.
               Od teraz karta jest przypisana do Twojego konta.</p>
            <p>W zakładce <strong>Moja firma</strong> w profilu uzupełnisz telefon,
               godziny otwarcia i opis — to one decydują, czy mieszkaniec zadzwoni.</p>
            <a href="{panel_url}" class="btn">Uzupełnij wizytówkę</a>
            """
        else:
            subject = f"Zgłoszenie firmy „{business_name}” — decyzja"
            body = f"""
            <h2>Nie potwierdziliśmy zgłoszenia</h2>
            <p>Twój wniosek o wizytówkę firmy <strong>{business_name}</strong>
               nie został potwierdzony, więc karta wraca do puli.</p>
            <p>Jeśli to Twoja firma, odpisz na tę wiadomość albo napisz na
               <a href="mailto:biuro@lumargo.pl">biuro@lumargo.pl</a> — wystarczy
               cokolwiek, co wiąże Cię z firmą (pieczątka, faktura, wpis w CEIDG).
               Załatwimy to od ręki, bez czekania na kolejny wniosek.</p>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: sans-serif; line-height: 1.6; color: #333; }}
                .btn {{ display: inline-block; background: #1e3a5f; color: white; padding: 12px 30px;
                        text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            {body}
            <p style="font-size: 12px; color: #888; margin-top: 30px;">
                RybnoLive — katalog firm gminy Rybno
            </p>
        </body>
        </html>
        """

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            reply_to="biuro@lumargo.pl",
        )
