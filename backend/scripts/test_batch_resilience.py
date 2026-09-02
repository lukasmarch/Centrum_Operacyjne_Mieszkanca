"""
Czy pojedyncza porażka w pętli batcha kosztuje wyłącznie siebie.

`process_article` przy błędzie robi `session.rollback()` i podnosi wyjątek dalej.
Rollback UNIEWAŻNIA wszystkie wczytane obiekty ORM — także wtedy, gdy sesja ma
`expire_on_commit=False` (tak ją stawia `scheduler/ai_jobs.py`). Handler w pętli
sięgał po `article.id`, czyli próbował dociągnąć wygaszony wpis z bazy w kodzie
synchronicznym, i wywracał CAŁY przebieg na `MissingGreenlet` — z wnętrza
`except`, więc `continue` nie miało już czego ratować.

2.09.2026: wyczerpane kredyty OpenAI ubiły pierwszy artykuł z batcha, a ten
zabrał pozostałych czternaście. Log produkcji:

    Found 15 articles to process
    Processing article 5740: 🌅 Dzień dobry wszystkim mieszkańcom...
    ✗ Error processing article 5740: 429 credit_balance_exhausted
    ✗ AI processing job failed: greenlet_spawn has not been called

Do modelu nie trafił ŻADEN wpis, choć zawiódł jeden. Ta sama poprawka co
w `ai/event_extractor.py` z 22.08.2026 (tam „jeden felerny artykuł zabrał
pozostałe trzynaście") — tamta pętla ją dostała, ta została pominięta.

Test podmienia samą kategoryzację, ale sesja, rollback i `process_batch` są
prawdziwe: pułapka siedzi w semantyce SQLAlchemy, więc atrapa sesji nic by
nie dowiodła. Dane idą do osobnego schematu `batch_test`, kasowanego na końcu.

Użycie:
    cd backend && python -m scripts.test_batch_resilience
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from src.ai.article_processor import ArticleProcessor
from src.config import settings
from src.database.schema import Article, Source

SCHEMA = "batch_test"
BATCH = 5


class _Logger:
    def info(self, m):
        print(f"    INFO  {m}")

    def error(self, m):
        print(f"    ERROR {m}")

    def warning(self, m):
        print(f"    WARN  {m}")


class FailingProcessor(ArticleProcessor):
    """Kategoryzacja podmieniona: pierwszy artykuł pada tak jak przy 429 od OpenAI."""

    def __init__(self):
        self.logger = _Logger()
        self.attempted = []

    async def process_article(self, article, session):
        self.attempted.append(article.id)
        if len(self.attempted) == 1:
            # dokładnie ta ścieżka co w produkcji: log, rollback, raise
            self.logger.error(
                f"✗ Error processing article {article.id}: 429 credit_balance_exhausted"
            )
            await session.rollback()
            raise RuntimeError("429 credit_balance_exhausted")
        article.processed = True
        session.add(article)
        await session.commit()
        return article


async def run() -> int:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        await conn.execute(text(f"SET search_path TO {SCHEMA}"))
        await conn.run_sync(
            SQLModel.metadata.create_all,
            tables=[Source.__table__, Article.__table__],
        )

    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"\n  Batch: {BATCH} artykułów, pierwszy pada na 429\n")

    async with maker() as session:
        await session.execute(text(f"SET search_path TO {SCHEMA}"))
        session.add(Source(id=1, name="Test", type="rss", url="http://x", is_active=True))
        await session.commit()
        now = datetime.utcnow()
        for i in range(BATCH):
            session.add(Article(
                source_id=1, title=f"Artykuł {i}", content="treść testowa",
                url=f"http://x/{i}", published_at=now, scraped_at=now, processed=False,
            ))
        await session.commit()

        processor = FailingProcessor()
        counted = await processor.process_batch(session, batch_size=100, days_back=2)

        result = await session.execute(select(Article).where(Article.processed == True))  # noqa: E712
        stored = len(result.scalars().all())

    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
    await engine.dispose()

    attempted = len(processor.attempted)
    print()
    print(f"  próbowano przetworzyć  : {attempted}/{BATCH}")
    print(f"  zwrócony licznik       : {counted}")
    print(f"  processed=True w bazie : {stored}")
    print()

    failures = 0
    for label, got, want in (
        ("każdy artykuł trafił do modelu", attempted, BATCH),
        ("licznik pomija tylko felerny", counted, BATCH - 1),
        ("zapisane wszystkie poza felernym", stored, BATCH - 1),
    ):
        ok = got == want
        failures += 0 if ok else 1
        print(f"  {'✅' if ok else '❌'} {label}: {got} (oczekiwano {want})")

    return failures


if __name__ == "__main__":
    try:
        failed = asyncio.run(run())
    except Exception as exc:  # noqa: BLE001 — o to w tym teście chodzi
        print(f"\n  ❌ WYJĄTEK UBIŁ CAŁY PRZEBIEG: {type(exc).__name__}: {exc}")
        sys.exit(1)
    print()
    sys.exit(1 if failed else 0)
