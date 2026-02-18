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
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email via Resend.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            reply_to: Optional reply-to address

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
        # Build context for template
        context = {
            "subject": content.get("subject", "Tydzień w Działdowie"),
            "date": datetime.now().strftime("%d.%m.%Y"),
            "sections": content.get("sections", {}),
            "unsubscribe_url": f"{settings.APP_URL}/newsletter/unsubscribe?token={unsubscribe_token}",
            "preferences_url": f"{settings.APP_URL}/newsletter/preferences?token={unsubscribe_token}",
            "premium_url": f"{settings.APP_URL}/premium",
            "weekly_weather": content.get("weekly_weather"),
            "weekly_reports": content.get("weekly_reports"),
        }

        # Process events to extract day/month for display
        events = context["sections"].get("events", [])
        for event in events:
            if "date" in event:
                try:
                    date_obj = datetime.strptime(event["date"], "%Y-%m-%d")
                    event["day"] = date_obj.day
                    event["month"] = date_obj.strftime("%b").upper()
                except ValueError:
                    event["day"] = "?"
                    event["month"] = "?"

        # Render template
        html = self.render_template("weekly.html", context)

        # Send email
        return await self.send_email(
            to_email=to_email,
            subject=context["subject"],
            html_content=html
        )

    async def send_daily_newsletter(
        self,
        to_email: str,
        content: Dict[str, Any],
        unsubscribe_token: str,
        weather_temp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send daily newsletter to a Premium subscriber.

        Args:
            to_email: Subscriber's email
            content: Newsletter content from generator
            unsubscribe_token: Token for unsubscribe link
            weather_temp: Current temperature

        Returns:
            Send result
        """
        # Build context
        air_quality = content.get("air_quality")
        context = {
            "subject": content.get("subject", "Dzień Dobry!"),
            "sections": content.get("sections", {}),
            "weather_temp": weather_temp or (air_quality or {}).get("temperature") or "?",
            "air_quality": air_quality,
            "name_days": content.get("name_days", []),
            "special_day": content.get("special_day", ""),
            "cinema_evening": content.get("cinema_evening", []),
            "reports_today": content.get("reports_today", []),
            "reports_date_label": content.get("reports_date_label", "dzisiaj"),
            "unsubscribe_url": f"{settings.APP_URL}/newsletter/unsubscribe?token={unsubscribe_token}",
            "preferences_url": f"{settings.APP_URL}/newsletter/preferences?token={unsubscribe_token}",
        }

        # Render template
        html = self.render_template("daily.html", context)

        # Send email
        return await self.send_email(
            to_email=to_email,
            subject=context["subject"],
            html_content=html
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
            <p>Dziękujemy za zapisanie się do newslettera Centrum Operacyjnego Mieszkańca!</p>
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
            subject="Potwierdź subskrypcję newslettera - Centrum Operacyjne",
            html_content=html
        )
