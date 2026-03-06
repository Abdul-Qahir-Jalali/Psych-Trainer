"""
PGVector Knowledge Retrieval — The interface to the vector database.

This module provides the `PGRetriever` class which:
1. Connects to PostgreSQL using psycopg
2. Embeds incoming queries
3. Searches specific collections using cosine similarity
4. Reranks using cross-encoder
5. Returns context strings for the LLM.
"""

from __future__ import annotations

import asyncio
import json
import structlog
from fastembed import TextEmbedding
from sentence_transformers import CrossEncoder
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector_async

from psychtrainer.config import settings

logger = structlog.get_logger(__name__)

class PGRetriever:
    """ Retrieves relevant context from Postgres pgvector based on semantic similarity. """

    def __init__(self):
        self.pool_uri = settings.postgres_uri
        # Initialize an async pool. We open it lazily on first query.
        self.pool = AsyncConnectionPool(conninfo=self.pool_uri, min_size=1, max_size=10, open=False)
        self.model = TextEmbedding(settings.embedding_model)
        self.cross_encoder = CrossEncoder(settings.cross_encoder_model)
        self._pool_ready = False

    async def _ensure_pool(self):
        if not self._pool_ready:
            await self.pool.open()
            # Register pgvector type handler for this pool
            async with self.pool.connection() as conn:
                await register_vector_async(conn)
            self._pool_ready = True

    async def search(self, query: str, collection_name: str, limit: int = 3) -> str:
        """Search a collection using PGVector Cosine Distance + CrossEncoder Reranking."""
        await self._ensure_pool()
        loop = asyncio.get_running_loop()

        def _embed_query():
            return list(self.model.embed([query]))[0].tolist()

        dense_vector = await loop.run_in_executor(None, _embed_query)

        chunks = []
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    # We query the document_embeddings table created during ingestion
                    await cur.execute(
                        """
                        SELECT text 
                        FROM document_embeddings 
                        WHERE collection_name = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT 20
                        """,
                        (collection_name, str(dense_vector))
                    )
                    rows = await cur.fetchall()
                    chunks = [row[0] for row in rows]
        except Exception as e:
            logger.error("pgvector_search_failed", error=str(e), collection=collection_name)
            return ""

        if not chunks:
            return ""

        def _rerank():
            pairs = [[query, chunk] for chunk in chunks]
            scores = self.cross_encoder.predict(pairs)
            scored = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
            return "\n---\n".join([chunk for score, chunk in scored[:limit]])

        return await loop.run_in_executor(None, _rerank)

    async def get_patient_context(self, query: str) -> str:
        """Find relevant lines from the OSCE script."""
        return await self.search(query, "patient_script", limit=3)

    async def get_grading_criteria(self, query: str) -> str:
        """Find relevant grading rules from the rubric."""
        return await self.search(query, "grading_rubric", limit=3)

    async def get_medical_knowledge(self, query: str) -> str:
        """Find relevant medical facts (MedQA)."""
        return await self.search(query, "medical_knowledge", limit=2)

    async def close(self):
        if self._pool_ready:
            await self.pool.close()
