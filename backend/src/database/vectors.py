"""
Vector database models for RAG (Retrieval Augmented Generation)
Uses pgvector for semantic search over document embeddings
"""
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB


class DocumentEmbedding(SQLModel, table=True):
    """Embeddings of document chunks for RAG semantic search"""
    __tablename__ = "document_embeddings"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Source identification
    source_type: str = Field(max_length=50, index=True)  # "article", "bip", "event", "report"
    source_id: int = Field(index=True)  # ID in source table
    chunk_index: int = Field(default=0)  # Chunk position within document

    # Content
    chunk_text: str  # The actual text chunk

    # Note: embedding column (vector(1536)) is managed by pgvector extension
    # SQLModel/SQLAlchemy doesn't natively handle vector type, so we use raw SQL for queries

    # Metadata for filtering and context (renamed from 'metadata' - reserved by SQLAlchemy)
    doc_meta: Optional[dict] = Field(default_factory=dict, sa_column=Column("metadata", JSONB))
    # doc_meta example: {"title": "...", "source_name": "...", "category": "...", "url": "..."}

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(SQLModel, table=True):
    """Chat conversations"""
    __tablename__ = "conversations"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    title: Optional[str] = Field(default=None, max_length=200)
    agent_name: Optional[str] = Field(default=None, max_length=50)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    """Individual chat messages"""
    __tablename__ = "chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    role: str = Field(max_length=20)  # "user", "assistant", "system"
    content: str
    sources: Optional[list] = Field(default_factory=list, sa_column=Column(JSONB))
    agent_name: Optional[str] = Field(default=None, max_length=50)
    tokens_used: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessageFeedback(SQLModel, table=True):
    """Oceny 👍/👎 odpowiedzi agentów — dane do poprawy RAG i dowód jakości.
    Jeden głos na wiadomość na konto / hash IP (UNIQUE w migracji)."""
    __tablename__ = "chat_message_feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(foreign_key="chat_messages.id", index=True)
    rating: int  # +1 (pomogło) / -1 (nie pomogło)
    voter_key: str = Field(max_length=60, index=True)  # "user:{id}" lub "ip:{hash}"

    created_at: datetime = Field(default_factory=datetime.utcnow)


class GUSNarrative(SQLModel, table=True):
    """AI-generated data storytelling narratives for GUS sections"""
    __tablename__ = "gus_narratives"

    id: Optional[int] = Field(default=None, primary_key=True)
    section_key: str = Field(max_length=50, unique=True)
    narrative: str  # Main narrative text
    key_insights: Optional[list] = Field(default_factory=list, sa_column=Column(JSONB))

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: datetime


class APICostLog(SQLModel, table=True):
    """Track API costs for budgeting"""
    __tablename__ = "api_cost_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    service: str = Field(max_length=50)  # "openai", "gemini"
    model: str = Field(max_length=100)  # "gpt-4o", "text-embedding-3-small"
    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    estimated_cost_usd: float = Field(default=0)
    endpoint: Optional[str] = Field(default=None, max_length=100)
    user_id: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentToolCall(SQLModel, table=True):
    """Ślad po jednym wywołaniu narzędzia przez agenta (etap 6, 2026-08-24).

    Powstała, bo o dziurze w danych dowiadywaliśmy się przypadkiem: 21.08
    Przewodnik powiedział „nie mam prognozy", mając ją w bazie. Po przejściu
    agentów na narzędzia dziura ma stały kształt — narzędzie zawołane, wynik
    pusty — więc da się ją policzyć zamiast zauważać.

    `state` i `error` to dwie różne informacje. `empty` znaczy „szukałem i nie
    ma" i naprawia się je w ŹRÓDLE danych; `error` to nasza awaria i naprawia
    się ją w kodzie. Wrzucone do jednej kolumny przestałyby się różnić.

    `args` bywa jedynym miejscem, w którym widać błąd promptu: model wołający
    `days=1` na pytanie o jutro (22.08) wygląda w statystykach jak poprawne
    wywołanie zakończone sukcesem.

    RODO: `question` i `user_id` czyści `retention_job` po 30 dniach, wiersz
    znika po 180. Liczniki przeżywają — do analityki wystarczy nazwa i stan.
    """
    __tablename__ = "agent_tool_calls"

    id: Optional[int] = Field(default=None, primary_key=True)
    agent_name: str = Field(max_length=50)
    tool_name: str = Field(max_length=60)
    state: str = Field(max_length=20)          # "done" | "empty" | "error"
    error: Optional[str] = Field(default=None, max_length=30)  # timeout, bad_arguments…
    args: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    duration_ms: int = Field(default=0)
    question: Optional[str] = Field(default=None, max_length=200)
    user_id: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
