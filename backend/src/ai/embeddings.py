"""
EmbeddingService - generates and searches vector embeddings using OpenAI text-embedding-3-small
"""
import json
import openai
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("EmbeddingService")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# Ile kandydatów wolno OBEJRZEĆ indeksowi przybliżonemu, zanim odda wynik.
#
# ⚠️ To NIE jest strojenie wydajności, tylko warunek poprawności — i kosztował
# nas fałszywą odpowiedź (5.09.2026). Indeks wektorowy jest PRZYBLIŻONY: zwraca
# najbliższych sąsiadów spośród tych, które zdążył obejrzeć, i nigdy nie mówi,
# że czegoś nie obejrzał. Zapytanie kończy się sukcesem, a właściwego dokumentu
# w wyniku po prostu nie ma.
#
# Domyślne `ivfflat.probes = 1` znaczy „przejrzyj jedną ze 100 list", czyli ~1%
# korpusu. Pomiar na 15 realnych pytaniach: widoczne 54% właściwego top-12,
# przy dwóch pytaniach 0%. Na pytanie „nocny bieg organizowany przez
# Nadleśnictwo" artykuł o biegu, który odbywał się TEGO DNIA, miał najwyższe
# podobieństwo w całej bazie (0,582) i nie pojawił się w wynikach wcale.
#
# `hnsw.ef_search` ma DRUGI, twardszy skutek: HNSW zwraca najwyżej `ef_search`
# wierszy, więc wartość mniejsza od `LIMIT` zapytania obcina wynik po cichu.
# Musi być ≥ największego `candidate_limit` z `hybrid_search` (dziś 96).
#
# Ustawiamy OBA, bo baza lokalna i produkcyjna mogą stać na różnych indeksach —
# nieużywany GUC nic nie kosztuje, a milcząca różnica trafności między
# środowiskami kosztowałaby dzień śledztwa.
HNSW_EF_SEARCH = 200
IVFFLAT_PROBES = 20


class EmbeddingService:
    """Generates embeddings and performs semantic search using pgvector"""

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        # Tokeny zużyte przez ostatnie wywołanie embed_text/embed_batch —
        # odczytywane przez embedding_job do wpisu w api_cost_log
        self.last_usage_tokens: int = 0

    async def embed_text(self, text_input: str) -> list[float]:
        """Generate embedding for a single text"""
        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text_input,
            dimensions=EMBEDDING_DIMENSIONS
        )
        self.last_usage_tokens = response.usage.total_tokens if response.usage else 0
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (max 2048 per batch)"""
        if not texts:
            self.last_usage_tokens = 0
            return []

        # OpenAI supports up to 2048 inputs per batch
        all_embeddings = []
        batch_size = 100  # Conservative batch size
        used_tokens = 0

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIMENSIONS
            )
            all_embeddings.extend([d.embedding for d in response.data])
            used_tokens += response.usage.total_tokens if response.usage else 0

        self.last_usage_tokens = used_tokens
        return all_embeddings

    @staticmethod
    async def _widen_index_scan(session: AsyncSession) -> None:
        """Otwiera indeksowi przybliżonemu pole widzenia na czas TEGO zapytania.

        `SET LOCAL`, więc ustawienie znika wraz z transakcją i nie wycieka na
        inne zapytania sesji — a sesje bierzemy z puli, więc wartość globalna
        nie miałaby jak się utrzymać.

        Błąd jest połykany świadomie: starsze pgvector nie zna `hnsw.ef_search`,
        a wyszukiwanie z węższym polem widzenia jest lepsze niż brak wyszukiwania.
        """
        for guc, value in (("hnsw.ef_search", HNSW_EF_SEARCH),
                           ("ivfflat.probes", IVFFLAT_PROBES)):
            try:
                await session.execute(text(f"SET LOCAL {guc} = {int(value)}"))
            except Exception as e:  # noqa: BLE001 — patrz docstring
                logger.debug(f"Nie ustawiono {guc}: {e}")

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
        await self._widen_index_scan(session)

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


    async def hybrid_search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        source_types: Optional[list[str]] = None,
        similarity_threshold: float = 0.35,
        semantic_weight: float = 0.70,
        recency_boost: float = 0.0,
        rrf_k: int = 60
    ) -> list[dict]:
        """Hybrid: pgvector semantic + tsvector BM25 with RRF fusion.
        Falls back to semantic-only if tsvector column doesn't exist.
        """
        query_embedding = await self.embed_text(query)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        await self._widen_index_scan(session)

        candidate_limit = max(top_k * 6, 40)
        filter_clause = ""
        params: dict = {"candidate_limit": candidate_limit, "threshold": similarity_threshold}

        if source_types:
            placeholders = ", ".join(f":st_{i}" for i in range(len(source_types)))
            filter_clause = f"AND source_type IN ({placeholders})"
            for i, st in enumerate(source_types):
                params[f"st_{i}"] = st

        # Semantic candidates
        sem_sql = f"""
            SELECT id, chunk_text, source_type, source_id, metadata,
                   1 - (embedding <=> '{embedding_str}'::vector) AS score,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> '{embedding_str}'::vector) AS rank
            FROM document_embeddings
            WHERE 1 - (embedding <=> '{embedding_str}'::vector) > :threshold
            {filter_clause}
            ORDER BY embedding <=> '{embedding_str}'::vector
            LIMIT :candidate_limit
        """

        sem_result = await session.execute(text(sem_sql), params)
        sem_rows = {row[0]: row for row in sem_result.fetchall()}

        # BM25 candidates (tsvector) — graceful fallback if column missing.
        # Prefiksy (slowo:*) to namiastka polskiego stemmingu w konfiguracji
        # 'simple': "przetarg:*" dopasuje "przetargu", "przetargiem" itd.
        bm25_rows: dict = {}
        bm25_terms = [
            "".join(c for c in w.strip() if c.isalnum())
            for w in query.split()
        ]
        bm25_query_str = " | ".join(f"{t}:*" for t in bm25_terms if len(t) > 2)
        if bm25_query_str:
            params_bm25 = {**params, "bm25_query": bm25_query_str}
            bm25_sql = f"""
                SELECT id, chunk_text, source_type, source_id, metadata,
                       ts_rank_cd(search_vector, to_tsquery('simple', unaccent(:bm25_query))) AS score,
                       ROW_NUMBER() OVER (
                           ORDER BY ts_rank_cd(search_vector, to_tsquery('simple', unaccent(:bm25_query))) DESC
                       ) AS rank
                FROM document_embeddings
                WHERE search_vector IS NOT NULL
                  AND search_vector @@ to_tsquery('simple', unaccent(:bm25_query))
                {filter_clause}
                ORDER BY score DESC
                LIMIT :candidate_limit
            """
            try:
                bm25_result = await session.execute(text(bm25_sql), params_bm25)
                bm25_rows = {row[0]: row for row in bm25_result.fetchall()}
            except Exception as e:
                logger.warning(f"BM25 search failed (tsvector not ready?): {e}")

        # RRF Fusion
        all_ids = set(sem_rows) | set(bm25_rows)
        if not all_ids:
            return []

        rrf_scores: dict = {}
        for doc_id in all_ids:
            sem_rank = sem_rows[doc_id][6] if doc_id in sem_rows else (candidate_limit + 1)
            bm25_rank = bm25_rows[doc_id][6] if doc_id in bm25_rows else (candidate_limit + 1)
            rrf_scores[doc_id] = (
                semantic_weight * (1.0 / (rrf_k + sem_rank)) +
                (1 - semantic_weight) * (1.0 / (rrf_k + bm25_rank))
            )

        # Recency boost (optional)
        if recency_boost > 0:
            now = datetime.now(timezone.utc)
            HALF_LIFE_DAYS = 90
            for doc_id in all_ids:
                row = sem_rows.get(doc_id) or bm25_rows.get(doc_id)
                meta = row[4] or {}
                pub_raw = meta.get('published_at', '') or meta.get('event_date', '')
                if pub_raw:
                    try:
                        dt = datetime.fromisoformat(pub_raw.replace('Z', '+00:00'))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        age_days = (now - dt).days
                        decay = 2 ** (-age_days / HALF_LIFE_DAYS)
                        rrf_scores[doc_id] *= (1.0 + recency_boost * decay)
                    except Exception:
                        pass

        top_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        # Kosinusowe podobieństwo dla dokumentów tylko-BM25 (nie było ich wśród
        # kandydatów semantycznych) — jedno tanie zapytanie po id.
        # "similarity" MUSI być kosinusem 0-1: base_agent porównuje je
        # z source_display_threshold, a LLM dostaje je jako "Trafność".
        cosine_by_id = {doc_id: float(sem_rows[doc_id][5]) for doc_id in top_ids if doc_id in sem_rows}
        missing = [doc_id for doc_id in top_ids if doc_id not in cosine_by_id]
        if missing:
            placeholders = ", ".join(f":id_{i}" for i in range(len(missing)))
            cos_sql = f"""
                SELECT id, 1 - (embedding <=> '{embedding_str}'::vector) AS score
                FROM document_embeddings
                WHERE id IN ({placeholders})
            """
            cos_result = await session.execute(
                text(cos_sql), {f"id_{i}": v for i, v in enumerate(missing)}
            )
            for row in cos_result.fetchall():
                cosine_by_id[row[0]] = float(row[1])

        results = []
        for doc_id in top_ids:
            row = sem_rows.get(doc_id) or bm25_rows.get(doc_id)
            results.append({
                "chunk_text": row[1],
                "source_type": row[2],
                "source_id": row[3],
                "metadata": row[4] or {},
                "similarity": round(cosine_by_id.get(doc_id, 0.0), 4),
                "rrf_score": round(rrf_scores[doc_id], 6),
            })
        return results


# Singleton
embedding_service = EmbeddingService()
