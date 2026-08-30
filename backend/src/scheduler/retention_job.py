"""
Retention Job — codziennie o 3:30 (RODO art. 5 — ograniczenie przechowywania)

Czyści dane osobowe, których okres przechowywania minął (zgodnie z tabelą
retencji w Polityce prywatności):
  - anonymous_chat_usage:  liczniki starsze niż 2 dni (limit jest dzienny)
  - conversations bez user_id (anonimowe) + ich chat_messages: > 90 dni
  - newsletter_logs: > 90 dni
  - api_cost_log: wpisy z user_id starsze niż 90 dni są odpinane od konta
    (user_id -> NULL, koszty zostają do analityki)
  - reports rozwiązane > 12 mies.: anonimizacja danych autora (treść zostaje)
  - agent_tool_calls: treść pytania i user_id znikają po 30 dniach,
    cały wiersz po 180 (liczniki narzędzi zostają do analityki)
  - site_events: session_id i user_id znikają po 90 dniach, cały wiersz po 180
    (liczniki zdarzeń i kampanii zostają do analityki)
"""
import asyncio
from datetime import datetime, timedelta, date

from sqlalchemy import delete, update, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.config import settings
from src.database.schema import AnonymousChatUsage, NewsletterLog, Report, SiteEvent
from src.database.vectors import Conversation, ChatMessage, APICostLog, AgentToolCall
from src.utils.logger import setup_logger

logger = setup_logger("RetentionJob")

RETENTION_ANON_USAGE_DAYS = 2
RETENTION_ANON_CHAT_DAYS = 90
RETENTION_NEWSLETTER_LOG_DAYS = 90
RETENTION_COST_LOG_USER_DAYS = 90
RETENTION_RESOLVED_REPORT_DAYS = 365
# Log narzędzi jest DIAGNOSTYCZNY — raport pyta o ostatnie dni, nie miesiące.
# Pytanie mieszkańca leży już w `chat_messages`, więc druga kopia ma żyć
# tylko tak długo, jak trwa jej użyteczność (art. 5 ust. 1 lit. e RODO).
RETENTION_TOOL_CALL_QUESTION_DAYS = 30
RETENTION_TOOL_CALL_DAYS = 180
# Pomiar strony. `session_id` wiąże zdarzenia w jedną wizytę i tylko po to
# istnieje — po kwartale odtwarzanie pojedynczej ścieżki nikomu już nie służy,
# a zestawienia liczą się po `event`, `section` i `utm_campaign`.
RETENTION_SITE_EVENT_SESSION_DAYS = 90
RETENTION_SITE_EVENT_DAYS = 180


async def run_retention_async():
    logger.info("=== Retention Job START ===")
    now = datetime.utcnow()

    # Własny engine dla event loopa APSchedulera (wzorzec z trial_expiry_job)
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # 1. Liczniki anonimowego czatu (limit jest dzienny — starsze zbędne)
        cutoff_usage = date.today() - timedelta(days=RETENTION_ANON_USAGE_DAYS)
        res = await session.execute(
            delete(AnonymousChatUsage).where(AnonymousChatUsage.usage_date < cutoff_usage)
        )
        logger.info(f"anonymous_chat_usage: usunięto {res.rowcount} wpisów (< {cutoff_usage})")

        # 2. Anonimowe rozmowy z AI starsze niż 90 dni
        cutoff_chat = now - timedelta(days=RETENTION_ANON_CHAT_DAYS)
        conv_ids = (await session.execute(
            select(Conversation.id).where(
                Conversation.user_id == None,  # noqa: E711
                Conversation.created_at < cutoff_chat,
            )
        )).scalars().all()
        if conv_ids:
            await session.execute(
                delete(ChatMessage).where(ChatMessage.conversation_id.in_(conv_ids))
            )
            await session.execute(
                delete(Conversation).where(Conversation.id.in_(conv_ids))
            )
        logger.info(f"anonimowe konwersacje: usunięto {len(conv_ids)} (< {cutoff_chat.date()})")

        # 3. Logi newslettera
        cutoff_nl = now - timedelta(days=RETENTION_NEWSLETTER_LOG_DAYS)
        res = await session.execute(
            delete(NewsletterLog).where(NewsletterLog.sent_at < cutoff_nl)
        )
        logger.info(f"newsletter_logs: usunięto {res.rowcount} wpisów")

        # 4. Koszty API — odpięcie od użytkownika po 90 dniach (dane kosztowe zostają)
        cutoff_cost = now - timedelta(days=RETENTION_COST_LOG_USER_DAYS)
        res = await session.execute(
            update(APICostLog)
            .where(APICostLog.user_id != None, APICostLog.created_at < cutoff_cost)  # noqa: E711
            .values(user_id=None)
        )
        logger.info(f"api_cost_log: odpięto user_id z {res.rowcount} wpisów")

        # 5. Rozwiązane zgłoszenia > 12 mies. — anonimizacja autora
        cutoff_rep = now - timedelta(days=RETENTION_RESOLVED_REPORT_DAYS)
        res = await session.execute(
            update(Report)
            .where(
                Report.resolved_at != None,  # noqa: E711
                Report.resolved_at < cutoff_rep,
                or_(
                    Report.author_name != None,   # noqa: E711
                    Report.author_email != None,  # noqa: E711
                    Report.author_phone != None,  # noqa: E711
                ),
            )
            .values(author_name=None, author_email=None, author_phone=None, user_id=None)
        )
        logger.info(f"reports: zanonimizowano autora w {res.rowcount} zgłoszeniach")

        # 6. Log narzędzi agentów — najpierw odpięcie od osoby, potem wiersz
        cutoff_tool_q = now - timedelta(days=RETENTION_TOOL_CALL_QUESTION_DAYS)
        res = await session.execute(
            update(AgentToolCall)
            .where(
                AgentToolCall.created_at < cutoff_tool_q,
                or_(
                    AgentToolCall.question != None,  # noqa: E711
                    AgentToolCall.user_id != None,   # noqa: E711
                ),
            )
            .values(question=None, user_id=None)
        )
        logger.info(f"agent_tool_calls: odpięto pytanie/user_id z {res.rowcount} wpisów")

        cutoff_tool = now - timedelta(days=RETENTION_TOOL_CALL_DAYS)
        res = await session.execute(
            delete(AgentToolCall).where(AgentToolCall.created_at < cutoff_tool)
        )
        logger.info(f"agent_tool_calls: usunięto {res.rowcount} wpisów")

        # 7. Pomiar strony — najpierw odpięcie od osoby i od wizyty, potem wiersz
        cutoff_se_sess = now - timedelta(days=RETENTION_SITE_EVENT_SESSION_DAYS)
        res = await session.execute(
            update(SiteEvent)
            .where(
                SiteEvent.occurred_at < cutoff_se_sess,
                or_(
                    SiteEvent.session_id != None,  # noqa: E711
                    SiteEvent.user_id != None,     # noqa: E711
                ),
            )
            .values(session_id=None, user_id=None)
        )
        logger.info(f"site_events: odpięto session_id/user_id z {res.rowcount} wpisów")

        cutoff_se = now - timedelta(days=RETENTION_SITE_EVENT_DAYS)
        res = await session.execute(
            delete(SiteEvent).where(SiteEvent.occurred_at < cutoff_se)
        )
        logger.info(f"site_events: usunięto {res.rowcount} wpisów")

        await session.commit()

    await engine.dispose()
    logger.info("=== Retention Job DONE ===")


def run_retention_job():
    """Wrapper synchroniczny dla APScheduler."""
    asyncio.run(run_retention_async())


if __name__ == "__main__":
    run_retention_job()
