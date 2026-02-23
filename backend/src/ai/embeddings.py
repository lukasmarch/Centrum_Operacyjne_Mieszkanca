"""
EmbeddingService - generates and searches vector embeddings using OpenAI text-embedding-3-small
"""
import json
import openai
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("EmbeddingService")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingService:
    """Generates embeddings and performs semantic search using pgvector"""

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def embed_text(self, text_input: str) -> list[float]:
        """Generate embedding for a single text"""
        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text_input,
            dimensions=EMBEDDING_DIMENSIONS
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (max 2048 per batch)"""
        if not texts:
            return []

        # OpenAI supports up to 2048 inputs per batch
        all_embeddings = []
        batch_size = 100  # Conservative batch size

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIMENSIONS
            )
            all_embeddings.extend([d.embedding for d in response.data])

        return all_embeddings

    async def store_embedding(
        self,
        session: AsyncSession,
        source_type: str,
        source_id: int,
        chunk_index: int,
        chunk_text: str,
        embedding: list[float],
        metadata: dict
    ):
        """Store a single embedding in the database"""
        # asyncpg doesn't support :param::vector casting - interpolate literals directly
        # Use dollar-quoting ($emb$...$emb$) to avoid issues with special chars in metadata
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        metadata_str = json.dumps(metadata, ensure_ascii=False) if metadata else "{}"

        await session.execute(
            text(f"""
                INSERT INTO document_embeddings (source_type, source_id, chunk_index, chunk_text, embedding, metadata)
                VALUES (:source_type, :source_id, :chunk_index, :chunk_text, $emb${embedding_str}$emb$::vector, $meta${metadata_str}$meta$::jsonb)
                ON CONFLICT (source_type, source_id, chunk_index)
                DO UPDATE SET chunk_text = :chunk_text, embedding = $emb${embedding_str}$emb$::vector, metadata = $meta${metadata_str}$meta$::jsonb, created_at = NOW()
            """),
            {
                "source_type": source_type,
                "source_id": source_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
            }
        )

    async def semantic_search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        source_types: Optional[list[str]] = None,
        similarity_threshold: float = 0.3
    ) -> list[dict]:
        """
        Search for semantically similar documents.
        Returns list of {chunk_text, source_type, source_id, metadata, similarity}
        """
        query_embedding = await self.embed_text(query)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build filter clause
        # Note: embedding_str is interpolated directly (not a param) because
        # asyncpg doesn't support :param::vector casting syntax
        filter_clause = ""
        params: dict = {"top_k": top_k, "threshold": similarity_threshold}

        if source_types:
            placeholders = ", ".join(f":st_{i}" for i in range(len(source_types)))
            filter_clause = f"AND source_type IN ({placeholders})"
            for i, st in enumerate(source_types):
                params[f"st_{i}"] = st

        result = await session.execute(
            text(f"""
                SELECT
                    chunk_text,
                    source_type,
                    source_id,
                    metadata,
                    1 - (embedding <=> '{embedding_str}'::vector) AS similarity
                FROM document_embeddings
                WHERE 1 - (embedding <=> '{embedding_str}'::vector) > :threshold
                {filter_clause}
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :top_k
            """),
            params
        )

        rows = result.fetchall()
        return [
            {
                "chunk_text": row[0],
                "source_type": row[1],
                "source_id": row[2],
                "metadata": row[3] or {},
                "similarity": round(float(row[4]), 4)
            }
            for row in rows
        ]


# Singleton
embedding_service = EmbeddingService()
