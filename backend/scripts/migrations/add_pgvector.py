"""
Migration: Add pgvector extension + document_embeddings table
Run: cd backend && python scripts/migrations/add_pgvector.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


async def run_migration():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        # 1. Enable pgvector extension
        print("Enabling pgvector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # 2. Create document_embeddings table
        print("Creating document_embeddings table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_embeddings (
                id SERIAL PRIMARY KEY,
                source_type VARCHAR(50) NOT NULL,
                source_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                chunk_text TEXT NOT NULL,
                embedding vector(1536),
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW(),

                UNIQUE(source_type, source_id, chunk_index)
            )
        """))

        # 3. Create IVFFlat index for fast similarity search
        print("Creating IVFFlat index...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_vector
            ON document_embeddings
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))

        # 4. Create indexes for filtering
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_source_type
            ON document_embeddings (source_type)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_source_id
            ON document_embeddings (source_type, source_id)
        """))

        # 5. Add 'embedded' column to articles table
        print("Adding 'embedded' column to articles...")
        await conn.execute(text("""
            ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS embedded BOOLEAN DEFAULT FALSE
        """))

        # 6. Create chat tables
        print("Creating conversations table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title VARCHAR(200),
                agent_name VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        print("Creating chat_messages table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                sources JSONB DEFAULT '[]',
                agent_name VARCHAR(50),
                tokens_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_conversations_user
            ON conversations (user_id, updated_at DESC)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
            ON chat_messages (conversation_id, created_at)
        """))

        # 7. Create GUS narratives table
        print("Creating gus_narratives table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gus_narratives (
                id SERIAL PRIMARY KEY,
                section_key VARCHAR(50) NOT NULL,
                narrative TEXT NOT NULL,
                key_insights JSONB DEFAULT '[]',
                generated_at TIMESTAMP DEFAULT NOW(),
                valid_until TIMESTAMP NOT NULL,

                UNIQUE(section_key)
            )
        """))

        # 8. Create cost tracking table
        print("Creating api_cost_log table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_cost_log (
                id SERIAL PRIMARY KEY,
                service VARCHAR(50) NOT NULL,
                model VARCHAR(100) NOT NULL,
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                estimated_cost_usd FLOAT DEFAULT 0,
                endpoint VARCHAR(100),
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_cost_log_service_date
            ON api_cost_log (service, created_at DESC)
        """))

    await engine.dispose()
    print("\nMigration completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_migration())
