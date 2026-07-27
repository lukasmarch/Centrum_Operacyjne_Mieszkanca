#!/usr/bin/env python3
"""
Test wysyłki newslettera - Weekly i Daily

Użycie:
    python scripts/test_newsletter_send.py twoj@email.com
    python scripts/test_newsletter_send.py twoj@email.com --type weekly
    python scripts/test_newsletter_send.py twoj@email.com --type daily

    # podgląd bez wysyłki — zapisuje HTML do plików i nic nie wychodzi na świat
    python scripts/test_newsletter_send.py podglad@example.com --preview-dir /tmp/newsletter
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.newsletter.generator import NewsletterGenerator
from src.newsletter.email_service import EmailService


def enable_preview_mode(preview_dir: Path):
    """Podmienia wysyłkę na zapis HTML do pliku — nic nie idzie do Resend."""
    preview_dir.mkdir(parents=True, exist_ok=True)
    counter = {"n": 0}

    async def save_instead_of_send(self, to_email, subject, html_content,
                                   reply_to=None, unsubscribe_url=None):
        counter["n"] += 1
        path = preview_dir / f"newsletter_{counter['n']}.html"
        path.write_text(html_content)
        print(f"   💾 Podgląd zapisany: {path}")
        print(f"      temat: {subject}")
        print(f"      wypis: {unsubscribe_url}")
        return {"status": "sent", "id": "preview", "to": to_email}

    EmailService.send_email = save_instead_of_send


async def test_weekly_newsletter(session: AsyncSession, to_email: str):
    """Generuje i wysyła testowy newsletter tygodniowy"""
    print("\n" + "="*60)
    print("📧 WEEKLY NEWSLETTER TEST")
    print("="*60)

    # 1. Generuj treść
    print("\n🤖 Generowanie treści przez AI...")
    generator = NewsletterGenerator()
    content = await generator.generate_weekly(session, location="Rybno")

    print(f"   ✅ Temat: {content.get('subject', 'brak')}")
    print(f"   ✅ Preview: {content.get('preview_text', 'brak')[:50]}...")

    sections = content.get('sections', {})
    print(f"   ✅ Sekcje: {list(sections.keys())}")

    # 2. Wyślij email
    print(f"\n📤 Wysyłanie do: {to_email}...")
    email_service = EmailService()

    result = await email_service.send_weekly_newsletter(
        to_email=to_email,
        content=content,
        unsubscribe_token="test-token-12345"
    )

    if result.get('status') == 'sent':
        print(f"   ✅ Email wysłany! ID: {result.get('id')}")
    else:
        print(f"   ❌ Błąd: {result}")

    return result


async def test_daily_newsletter(session: AsyncSession, to_email: str):
    """Generuje i wysyła testowy newsletter dzienny"""
    print("\n" + "="*60)
    print("☀️ DAILY NEWSLETTER TEST (Premium)")
    print("="*60)

    # 1. Generuj treść
    print("\n🤖 Generowanie treści przez AI...")
    generator = NewsletterGenerator()
    content = await generator.generate_daily(session, location="Rybno")

    print(f"   ✅ Temat: {content.get('subject', 'brak')}")
    print(f"   ✅ Preview: {content.get('preview_text', 'brak')[:50]}...")

    sections = content.get('sections', {})
    print(f"   ✅ Sekcje: {list(sections.keys())}")

    # 2. Wyślij email
    print(f"\n📤 Wysyłanie do: {to_email}...")
    email_service = EmailService()

    result = await email_service.send_daily_newsletter(
        to_email=to_email,
        content=content,
        unsubscribe_token="test-token-67890",
        weather_temp=5.0  # przykładowa temperatura
    )

    if result.get('status') == 'sent':
        print(f"   ✅ Email wysłany! ID: {result.get('id')}")
    else:
        print(f"   ❌ Błąd: {result}")

    return result


async def main():
    parser = argparse.ArgumentParser(description='Test wysyłki newslettera')
    parser.add_argument('email', help='Adres email do testu')
    parser.add_argument('--type', choices=['weekly', 'daily', 'both'],
                        default='both', help='Typ newslettera (default: both)')
    parser.add_argument('--preview-dir', default=None,
                        help='Zapisz HTML do katalogu zamiast wysyłać maila')

    args = parser.parse_args()

    print("\n" + "🚀 "*20)
    print("TEST WYSYŁKI NEWSLETTERA")
    print("🚀 "*20)
    print(f"\n📬 Email: {args.email}")
    print(f"📝 Typ: {args.type}")

    if args.preview_dir:
        enable_preview_mode(Path(args.preview_dir))
        print(f"👀 Tryb podglądu — nic nie zostanie wysłane ({args.preview_dir})")
    elif not settings.RESEND_API_KEY:
        print("\n❌ BŁĄD: Brak RESEND_API_KEY w .env!")
        print("   Dodaj: RESEND_API_KEY=re_xxx")
        return
    else:
        print(f"🔑 Resend API: {settings.RESEND_API_KEY[:10]}...")

    # Połącz z bazą
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        if args.type in ['weekly', 'both']:
            await test_weekly_newsletter(session, args.email)

        if args.type in ['daily', 'both']:
            await test_daily_newsletter(session, args.email)

    print("\n" + "="*60)
    print("✅ TEST ZAKOŃCZONY - Sprawdź swoją skrzynkę!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
