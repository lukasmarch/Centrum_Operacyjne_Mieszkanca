"""
Powitanie dla kont założonych przed 20.08.2026 (jednorazowo).

Do 20.08 rejestracja nie zakładała subskrypcji newslettera ani nie wysyłała
powitania. Konta z tamtego okresu mają Premium z okresu próbnego, nie wiedzą,
że jest on ograniczony, i nie dostają briefingu, choć obiecuje go cennik.

Skrypt dopisuje subskrypcję i wysyła mail powitalny — wyłącznie do adresów
podanych jawnie w wywołaniu. Bez `--send` niczego nie zapisuje ani nie wysyła:
to jest mail do prawdziwego człowieka, więc lista musi być decyzją, nie skutkiem
ubocznym zapytania SQL.

Użycie:
    cd backend && python -m scripts.send_missing_welcome --email ktos@example.com
    cd backend && python -m scripts.send_missing_welcome --email ktos@example.com --send
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.config import settings
from src.database.schema import User, NewsletterSubscriber
from src.newsletter.email_service import EmailService
from src.newsletter.subscriptions import ensure_subscription


async def run(emails, send: bool) -> int:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    problems = 0

    async with async_session() as session:
        for email in emails:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not user:
                print(f"❌ {email}: nie ma takiego konta")
                problems += 1
                continue

            existing = (await session.execute(
                select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
            )).scalar_one_or_none()

            print(f"\n👤 {email} (id {user.id}, plan {user.tier})")
            print(f"   okres próbny do: {user.trial_ends_at or '—'}")
            print(f"   subskrypcja:     {existing.frequency + '/' + existing.status if existing else 'BRAK'}")

            if not send:
                print("   ⏸  podgląd — dopisz --send, żeby wykonać")
                continue

            subscriber = await ensure_subscription(session, user)
            if subscriber is None:
                print("   ⏭  adres wypisany z newslettera — nie wskrzeszam, mail nie idzie")
                continue
            await session.commit()
            await session.refresh(subscriber)
            print(f"   ✓ subskrypcja: {subscriber.frequency}")

            result = await EmailService().send_welcome_email(
                to_email=user.email,
                recipient_name=user.full_name,
                trial_ends_at=user.trial_ends_at,
                unsubscribe_token=subscriber.unsubscribe_token,
            )
            if result.get("status") == "sent":
                print("   ✉️  powitanie wysłane")
            else:
                print(f"   ❌ mail nie wyszedł: {result}")
                problems += 1

    await engine.dispose()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Powitanie dla kont sprzed 20.08.2026")
    parser.add_argument("--email", action="append", required=True,
                        help="adres konta (można podać wielokrotnie)")
    parser.add_argument("--send", action="store_true",
                        help="wykonaj: zapisz subskrypcję i wyślij maila")
    args = parser.parse_args()

    if args.send and not settings.RESEND_API_KEY:
        print("❌ Brak RESEND_API_KEY — mail nie miałby jak wyjść")
        return 1
    return 1 if asyncio.run(run(args.email, args.send)) else 0


if __name__ == "__main__":
    sys.exit(main())
