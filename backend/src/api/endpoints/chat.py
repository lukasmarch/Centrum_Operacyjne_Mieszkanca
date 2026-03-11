"""
Chat API endpoints with SSE streaming
POST /api/chat/message - send message (SSE streaming)
GET /api/chat/history - get conversation history
GET /api/chat/suggestions - get context-aware suggestions
"""
import json
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session
from src.database.connection import async_session
from src.database.vectors import Conversation, ChatMessage
from src.ai.agents.orchestrator import orchestrator
from src.auth.dependencies import get_optional_user
from src.database.schema import User, AnonymousChatUsage
from src.utils.logger import setup_logger

logger = setup_logger("ChatAPI")

router = APIRouter(prefix="/api/chat", tags=["chat"])

DAILY_LIMITS = {
    "anonymous": 3,
    "free": 5,
    "premium": 50,
    "business": None,  # unlimited
}


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
    today = date.today()
    reset_at = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # Reset is next midnight UTC
    from datetime import timedelta
    reset_at = (reset_at + timedelta(days=1)).isoformat() + "Z"

    if user is None:
        # Anonymous user - check by IP
        ip = http_request.client.host if http_request.client else "unknown"
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

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        count_result = await session.execute(
            select(ChatMessage)
            .join(Conversation)
            .where(Conversation.user_id == user_id)
            .where(ChatMessage.role == "user")
            .where(ChatMessage.created_at >= today_start)
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

    # Get conversation history
    history_result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at)
        .limit(20)
    )
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_result.scalars().all()
    ]

    if request.stream:
        # SSE streaming response
        async def event_stream():
            try:
                result = await orchestrator.handle(
                    session=session,
                    user_message=request.message,
                    agent_name=request.agent_name,
                    conversation_history=history,
                    stream=True,
                    user=user
                )

                # Send conversation_id first
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation.id})}\n\n"

                full_content = ""
                sources = []

                async for line in result:
                    data = json.loads(line)
                    if data["type"] == "chunk":
                        full_content += data["content"]
                        yield f"data: {line}\n\n"
                    elif data["type"] == "sources":
                        sources = data["sources"]
                        yield f"data: {line}\n\n"
                    elif data["type"] == "chart_data":
                        yield f"data: {line}\n\n"
                    elif data["type"] == "done":
                        yield f"data: {line}\n\n"

                # Save assistant message
                async with async_session() as save_session:
                    assistant_msg = ChatMessage(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=full_content,
                        sources=sources,
                        agent_name=request.agent_name,
                        tokens_used=0
                    )
                    save_session.add(assistant_msg)
                    await save_session.commit()

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
    result = await orchestrator.handle(
        session=session,
        user_message=request.message,
        agent_name=request.agent_name,
        conversation_history=history,
        stream=False,
        user=user
    )

    # Save assistant message
    assistant_msg = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result["answer"],
        sources=result["sources"],
        agent_name=request.agent_name,
        tokens_used=result["tokens_used"]
    )
    session.add(assistant_msg)
    await session.commit()

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        conversation_id=conversation.id,
        tokens_used=result["tokens_used"],
        agent_name=request.agent_name,
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
    """Get example questions from all agents as suggestions"""
    suggestions = []
    for agent in orchestrator.agents.values():
        suggestions.extend(agent.example_questions[:2])
    return {"suggestions": suggestions[:8]}


@router.get("/agents")
async def get_agents():
    """List all available AI agents with their descriptions"""
    return {"agents": orchestrator.get_agents()}
