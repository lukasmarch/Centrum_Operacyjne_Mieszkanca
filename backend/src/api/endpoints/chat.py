"""
Chat API endpoints with SSE streaming
POST /api/chat/message - send message (SSE streaming)
GET /api/chat/history - get conversation history
GET /api/chat/suggestions - get context-aware suggestions
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session
from src.database.connection import async_session
from src.database.vectors import Conversation, ChatMessage
from src.ai.agents.orchestrator import orchestrator
from src.auth.dependencies import get_optional_user
from src.database.schema import User
from src.utils.logger import setup_logger

logger = setup_logger("ChatAPI")

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    agent_name: Optional[str] = None  # Route to specific agent
    stream: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    conversation_id: int
    tokens_used: int
    agent_name: Optional[str] = None


@router.post("/message")
async def send_message(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(get_optional_user)
):
    """Send a chat message and get AI response with RAG"""
    user_id = user.id if user else None

    # Rate limiting for free users
    if user and user.tier == "free":
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        count_result = await session.execute(
            select(ChatMessage)
            .join(Conversation)
            .where(Conversation.user_id == user_id)
            .where(ChatMessage.role == "user")
            .where(ChatMessage.created_at >= today_start)
        )
        daily_count = len(count_result.scalars().all())
        if daily_count >= 10:
            raise HTTPException(
                status_code=429,
                detail="Limit 10 pytan dziennie dla darmowego planu. Przejdz na Premium!"
            )

    # Get or create conversation
    if request.conversation_id:
        conv_result = await session.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
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
                    stream=True
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
                logger.error(f"Chat stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

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
        stream=False
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
        agent_name=request.agent_name
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
        # Get specific conversation
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
