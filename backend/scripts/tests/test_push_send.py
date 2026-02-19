"""
Test: Wyślij push notification do wszystkich aktywnych subskrybentów

Użycie:
    cd backend
    python -u scripts/tests/test_push_send.py

    # Custom wiadomość:
    python -u scripts/tests/test_push_send.py "Tytuł" "Treść" "/url"
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from src.config import settings
from src.database.schema import PushSubscription
from src.services.push_service import push_service


async def test_push(title: str, body: str, url: str = "/"):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Pokaż aktywne subskrypcje
        result = await session.execute(
            select(PushSubscription).where(PushSubscription.active == True)
        )
        subs = result.scalars().all()
        print(f"Aktywne subskrypcje: {len(subs)}")
        for s in subs:
            print(f"  - ID={s.id}, user={s.email}, endpoint={s.endpoint[:60]}...")

        if not subs:
            print("\n❌ Brak aktywnych subskrypcji – włącz push w Profilu")
            return

        print(f"\nWysyłam push:")
        print(f"  Tytuł: {title}")
        print(f"  Treść: {body}")
        print(f"  URL: {url}")
        print()

        sent = await push_service.send_to_category(
            session=session,
            category="alerty",  # "alerty" = wszyscy bez filtrowania
            title=title,
            body=body,
            url=url,
        )

        print(f"✅ Wysłano do {sent}/{len(subs)} subskrybentów")

    await engine.dispose()


if __name__ == "__main__":
    title = sys.argv[1] if len(sys.argv) > 1 else "TEST – Centrum Operacyjne"
    body  = sys.argv[2] if len(sys.argv) > 2 else "To jest testowe powiadomienie push 🔔"
    url   = sys.argv[3] if len(sys.argv) > 3 else "/"

    asyncio.run(test_push(title, body, url))
