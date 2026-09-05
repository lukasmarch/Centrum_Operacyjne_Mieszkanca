"""
Chat API endpoints with SSE streaming
POST /api/chat/message - send message (SSE streaming)
GET /api/chat/history - get conversation history
GET /api/chat/suggestions - get context-aware suggestions
"""
import hashlib
import json
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session
from src.database.connection import async_session
from src.database.vectors import Conversation, ChatMessage, ChatMessageFeedback, APICostLog
from src.ai.agents.orchestrator import orchestrator
from src.auth.dependencies import get_optional_user
from src.database.schema import User, AnonymousChatUsage
from src.utils.logger import setup_logger
from src.services.time_span import local_day_bounds, local_now

logger = setup_logger("ChatAPI")

router = APIRouter(prefix="/api/chat", tags=["chat"])

DAILY_LIMITS = {
    "anonymous": 3,
    "free": 5,
    "premium": None,  # unlimited
    "business": None,  # unlimited
}


def _log_chat_cost(session, tokens: int, agent_name: Optional[str], user_id: Optional[int]) -> None:
    """
    Zapis kosztu wywołania AI do api_cost_log (kontrola marży planów).
    Agenci nie zwracają podziału input/output — przyjmujemy szacunkowo 60/40
    i cennik gpt-4o-mini ($0.15/1M in, $0.60/1M out). Wpis to estymata.
    """
    if not tokens:
        return
    tokens_in = int(tokens * 0.6)
    tokens_out = tokens - tokens_in
    cost = tokens_in * 0.15 / 1_000_000 + tokens_out * 0.60 / 1_000_000
    session.add(APICostLog(
        service="openai",
        model="gpt-4o-mini",
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        estimated_cost_usd=round(cost, 8),
        endpoint=f"/api/chat/message:{agent_name or 'auto'}",
        user_id=user_id,
    ))


async def _generate_followups(question: str, answer: str, agent_name: Optional[str]) -> list:
    """
    3 pytania pomocnicze (chipy pod odpowiedzią) — zachęta do kontynuowania
    rozmowy. Osobne, tanie wywołanie gpt-4o-mini po zakończeniu streamu;
    błąd nigdy nie psuje odpowiedzi (zwracamy pustą listę).
    """
    import openai
    from src.config import settings
    try:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "Jesteś asystentem portalu lokalnego gminy Rybno. Na podstawie pytania "
                    "użytkownika i odpowiedzi agenta zaproponuj 3 krótkie pytania kontynuacyjne "
                    "(max 60 znaków każde), które użytkownik mógłby zadać jako następne. "
                    "Pytania po polsku, konkretne, dotyczące gminy Rybno i okolic. "
                    "Zwróć JSON: {\"questions\": [\"...\", \"...\", \"...\"]}"
                )},
                {"role": "user", "content": (
                    f"Agent: {agent_name or 'auto'}\n"
                    f"Pytanie: {question}\n"
                    f"Odpowiedź: {answer[:1500]}"
                )},
            ],
        )
        data = json.loads(response.choices[0].message.content)
        questions = [q for q in data.get("questions", []) if isinstance(q, str) and q.strip()]
        return questions[:3]
    except Exception as e:
        logger.warning(f"Followups generation failed: {e}")
        return []


def _hash_ip(ip: str) -> str:
    """
    Pseudonimizacja IP (RODO art. 5 — minimalizacja): do dziennego limitu
    anonimowego wystarczy stabilny identyfikator, nie sam adres.
    Sól z konfiguracji uniemożliwia odtworzenie IP z hasha bez dostępu do env.
    """
    from src.config import settings
    salt = getattr(settings, "IP_HASH_SALT", "rybnolive-ip-salt")
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:40]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[int] = None
    agent_name: Optional[str] = None  # Route to specific agent
    stream: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    conversation_id: int
    tokens_used: int
    agent_name: Optional[str] = None
    chart_data: Optional[list] = None


async def check_rate_limit(
    http_request: Request,
    session: AsyncSession,
    user: Optional[User],
    user_id: Optional[int],
) -> None:
    """Check rate limit. Raises HTTPException(429) with structured detail if exceeded."""
    # Doba LOKALNA, jedna dla obu gałęzi. Do 5.09.2026 anonimowi liczyli się
    # po dacie lokalnej (`date.today()`), a zalogowani po dobie UTC — więc
    # między północą a 2:00 jedni mieli już nowy dzień, drudzy jeszcze stary,
    # a komunikat „limit odnowi się o północy" mijał się z prawdą o dwie godziny.
    day_start, day_end = local_day_bounds()
    today = local_now().date()
    reset_at = day_end.isoformat() + "Z"

    if user is None:
        # Anonymous user — limit po zahaszowanym IP (nie przechowujemy adresu wprost)
        raw_ip = http_request.client.host if http_request.client else "unknown"
        ip = _hash_ip(raw_ip)
        limit = DAILY_LIMITS["anonymous"]

        result = await session.execute(
            select(AnonymousChatUsage)
            .where(AnonymousChatUsage.ip_address == ip)
            .where(AnonymousChatUsage.usage_date == today)
        )
        usage = result.scalar_one_or_none()
        used = usage.count if usage else 0

        if used >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "limit_reached",
                    "tier": "anonymous",
                    "limit": limit,
                    "used": used,
                    "reset_at": reset_at,
                }
            )

        # Increment counter
        if usage:
            usage.count += 1
            session.add(usage)
        else:
            new_usage = AnonymousChatUsage(ip_address=ip, usage_date=today, count=1)
            session.add(new_usage)
        await session.commit()

    elif user.tier == "business":
        # Business tier: unlimited
        return

    else:
        # Free or Premium - count today's messages
        tier = user.tier if isinstance(user.tier, str) else user.tier.value
        limit = DAILY_LIMITS.get(tier)
        if limit is None:
            return  # Safety fallback

        count_result = await session.execute(
            select(ChatMessage)
            .join(Conversation)
            .where(Conversation.user_id == user_id)
            .where(ChatMessage.role == "user")
            .where(ChatMessage.created_at >= day_start)
        )
        daily_count = len(count_result.scalars().all())

        if daily_count >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "limit_reached",
                    "tier": tier,
                    "limit": limit,
                    "used": daily_count,
                    "reset_at": reset_at,
                }
            )


@router.post("/message")
async def send_message(
    request: ChatRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user)
):
    """Send a chat message and get AI response with RAG"""
    user_id = user.id if user else None

    await check_rate_limit(http_request, session, user, user_id)

    # Get or create conversation
    if request.conversation_id:
        if user_id is None:
            # Anonymous users cannot resume specific conversations
            raise HTTPException(status_code=403, detail="Forbidden")
        conv_result = await session.execute(
            select(Conversation)
            .where(Conversation.id == request.conversation_id)
            .where(Conversation.user_id == user_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user_id,
            title=request.message[:100],
            agent_name=request.agent_name
        )
        session.add(conversation)
        await session.flush()

    # Save user message
    user_msg = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message
    )
    session.add(user_msg)
    await session.commit()

    # Get conversation history — OSTATNIE 20 wiadomości (desc + reverse);
    # rosnąco z limitem zwracało 20 najstarszych i długie rozmowy traciły
    # świeży kontekst
    history_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history_msgs = list(reversed(history_result.scalars().all()))
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_msgs
    ]
    # Ostatni agent w rozmowie — router używa go do obsługi pytań kontynuacyjnych
    last_agent = next(
        (m.agent_name for m in reversed(history_msgs)
         if m.role == "assistant" and m.agent_name),
        None
    )

    if request.stream:
        # SSE streaming response
        async def event_stream():
            try:
                # Send conversation_id first + widoczny krok pracy (routing + RAG
                # trwają 1-3 s — użytkownik widzi, że coś się dzieje)
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation.id})}\n\n"
                yield f"data: {json.dumps({'type': 'status', 'message': 'Analizuję pytanie i wybieram agenta…'})}\n\n"

                # `run()`, nie `handle()`: agent, któremu brakuje narzędzi,
                # oddaje pytanie następnemu zamiast odmawiać (etap 7).
                result = await orchestrator.run(
                    session=session,
                    user_message=request.message,
                    agent_name=request.agent_name,
                    conversation_history=history,
                    stream=True,
                    user=user,
                    last_agent=last_agent
                )

                full_content = ""
                sources = []
                resolved_agent_name = request.agent_name
                resolved_tokens = 0

                async for line in result:
                    data = json.loads(line)
                    if data["type"] == "chunk":
                        full_content += data["content"]
                        yield f"data: {line}\n\n"
                    elif data["type"] == "status":
                        # Przekazanie pytania: tekst poprzedniego agenta idzie
                        # do kosza także TUTAJ, nie tylko na ekranie. Bez tego
                        # w bazie zostałaby odmowa sklejona z odpowiedzią —
                        # i to ona wróciłaby do rozmowy jako historia.
                        if data.get("discard_text"):
                            full_content = ""
                        yield f"data: {line}\n\n"
                    elif data["type"] == "sources":
                        sources = data["sources"]
                        yield f"data: {line}\n\n"
                    elif data["type"] == "chart_data":
                        yield f"data: {line}\n\n"
                    elif data["type"] == "done":
                        resolved_agent_name = data.get("agent_name", request.agent_name)
                        resolved_tokens = data.get("tokens_used", 0)
                        yield f"data: {line}\n\n"

                # Pytania pomocnicze — chipy pod odpowiedzią (osobne tanie
                # wywołanie po streamie; odpowiedź jest już widoczna)
                if full_content:
                    followups = await _generate_followups(
                        request.message, full_content, resolved_agent_name
                    )
                    if followups:
                        yield f"data: {json.dumps({'type': 'followups', 'questions': followups})}\n\n"

                # Save assistant message with resolved agent_name and tokens_used
                async with async_session() as save_session:
                    await save_session.execute(
                        update(ChatMessage)
                        .where(ChatMessage.id == user_msg.id)
                        .values(agent_name=resolved_agent_name)
                    )
                    assistant_msg = ChatMessage(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=full_content,
                        sources=sources,
                        agent_name=resolved_agent_name,
                        tokens_used=resolved_tokens
                    )
                    save_session.add(assistant_msg)
                    _log_chat_cost(save_session, resolved_tokens, resolved_agent_name,
                                   user.id if user else None)
                    await save_session.commit()
                    await save_session.refresh(assistant_msg)

                # ID zapisanej wiadomości — potrzebne do ocen 👍/👎
                yield f"data: {json.dumps({'type': 'saved', 'message_id': assistant_msg.id})}\n\n"

            except Exception as e:
                logger.error(f"Chat stream error: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': 'Wystąpił błąd wewnętrzny. Spróbuj ponownie.'})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    # Non-streaming response
    result = await orchestrator.run(
        session=session,
        user_message=request.message,
        agent_name=request.agent_name,
        conversation_history=history,
        stream=False,
        user=user,
        last_agent=last_agent
    )

    # Agent ROZSTRZYGNIĘTY, nie żądany: przy trybie Auto `request.agent_name`
    # jest pusty, a po przekazaniu pytania (etap 7) odpowiada ktoś inny niż ten,
    # kogo wybrał router. Zapisanie żądania zamiast wyniku gubiło `last_agent`,
    # więc pytanie kontynuacyjne („a w zeszłym roku?") traciło wątek.
    resolved_agent = result.get("agent_name") or request.agent_name

    # Save assistant message
    assistant_msg = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result["answer"],
        sources=result["sources"],
        agent_name=resolved_agent,
        tokens_used=result["tokens_used"]
    )
    session.add(assistant_msg)
    _log_chat_cost(session, result["tokens_used"], resolved_agent,
                   user.id if user else None)
    await session.commit()

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        conversation_id=conversation.id,
        tokens_used=result["tokens_used"],
        agent_name=resolved_agent,
        chart_data=result.get("chart_data")
    )


@router.get("/history")
async def get_chat_history(
    conversation_id: Optional[int] = None,
    limit: int = Query(default=20, le=50),
    session: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user)
):
    """Get conversation history"""
    user_id = user.id if user else None

    if conversation_id:
        # Verify ownership before returning messages
        conv_result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conv.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        return {"messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "agent_name": m.agent_name,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]}

    # Get recent conversations
    query = select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)
    if user_id:
        query = query.where(Conversation.user_id == user_id)

    result = await session.execute(query)
    conversations = result.scalars().all()

    return {"conversations": [
        {
            "id": c.id,
            "title": c.title,
            "agent_name": c.agent_name,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat()
        }
        for c in conversations
    ]}


@router.get("/suggestions")
async def get_suggestions():
    """Example questions from all agents + deterministyczne pytanie dnia
    (rotacja po dniu roku — obniża próg wejścia w pustym czacie)."""
    suggestions = []
    pool = []
    for agent in orchestrator.agents.values():
        suggestions.extend(agent.example_questions[:2])
        pool.extend(agent.example_questions)

    question_of_day = None
    if pool:
        question_of_day = pool[date.today().timetuple().tm_yday % len(pool)]

    return {
        "suggestions": suggestions[:8],
        "question_of_day": question_of_day,
    }


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int = Field(..., description="+1 (pomogło) lub -1 (nie pomogło)")


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    http_request: Request,
    user: Optional[User] = Depends(get_optional_user),
):
    """Ocena odpowiedzi agenta 👍/👎 — jeden głos na wiadomość na konto/IP,
    ponowny głos nadpisuje ocenę (można zmienić zdanie)."""
    if request.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="rating musi być 1 lub -1")

    if user:
        voter_key = f"user:{user.id}"
    else:
        raw_ip = http_request.client.host if http_request.client else "unknown"
        voter_key = f"ip:{_hash_ip(raw_ip)[:40]}"

    async with async_session() as session:
        msg_result = await session.execute(
            select(ChatMessage).where(ChatMessage.id == request.message_id)
        )
        if not msg_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Wiadomość nie istnieje")

        existing = await session.execute(
            select(ChatMessageFeedback)
            .where(ChatMessageFeedback.message_id == request.message_id)
            .where(ChatMessageFeedback.voter_key == voter_key)
        )
        feedback = existing.scalar_one_or_none()
        if feedback:
            feedback.rating = request.rating
        else:
            feedback = ChatMessageFeedback(
                message_id=request.message_id,
                rating=request.rating,
                voter_key=voter_key,
            )
        session.add(feedback)
        await session.commit()

    return {"status": "ok", "rating": request.rating}


@router.get("/agents")
async def get_agents():
    """List all available AI agents with their descriptions"""
    return {"agents": orchestrator.get_agents()}
