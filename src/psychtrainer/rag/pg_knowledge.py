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
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector_async

from psychtrainer.config import settings
from psychtrainer.rag.cloud_inference import CloudEmbedder, CloudReranker

logger = structlog.get_logger(__name__)

class PGRetriever:
    """ Retrieves relevant context from Postgres pgvector based on semantic similarity. """

    def __init__(self):
        self.pool_uri = settings.postgres_uri
        # Initialize an async pool. We open it lazily on first query.
        self.pool = AsyncConnectionPool(conninfo=self.pool_uri, min_size=1, max_size=10, open=False)
        self.embedder = CloudEmbedder()
        self.reranker = CloudReranker()
        self._pool_ready = False

    async def _ensure_pool(self):
        if not self._pool_ready:
            await self.pool.open()
            # Register pgvector type handler for this pool
            async with self.pool.connection() as conn:
                await register_vector_async(conn)
            self._pool_ready = True

    async def search(self, query: str, collection_name: str, limit: int = 3) -> str:
        """Search a collection using PGVector Cosine Distance + Native FTS Keyword Search + CrossEncoder Reranking."""
        await self._ensure_pool()
        
        # Await async cloud embeddings mapping
        embedding_responses = await self.embedder.embed_texts([query])
        dense_vector = embedding_responses[0]

        chunks = []
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    # Execute Hybrid Search (Vector Cosine + Native Full Text Search) with RRF
                    await cur.execute(
                        """
                        WITH semantic_search AS (
                            SELECT text, ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
                            FROM document_embeddings 
                            WHERE collection_name = %s 
                            LIMIT 20
                        ),
                        keyword_search AS (
                            SELECT text, ROW_NUMBER() OVER (
                                ORDER BY ts_rank(to_tsvector('english', text), websearch_to_tsquery('english', %s)) DESC
                            ) AS rank
                            FROM document_embeddings
                            WHERE collection_name = %s 
                              AND to_tsvector('english', text) @@ websearch_to_tsquery('english', %s)
                            LIMIT 20
                        )
                        SELECT COALESCE(ss.text, ks.text) AS merged_text,
                               (COALESCE(1.0 / (60 + ss.rank), 0.0) + COALESCE(1.0 / (60 + ks.rank), 0.0)) AS rrf_score
                        FROM semantic_search ss
                        FULL OUTER JOIN keyword_search ks ON ss.text = ks.text
                        ORDER BY rrf_score DESC
                        LIMIT 20;
                        """,
                        (str(dense_vector), collection_name, query, collection_name, query)
                    )
                    rows = await cur.fetchall()
                    chunks = [row[0] for row in rows]
        except Exception as e:
            logger.error("pgvector_hybrid_search_failed", error=str(e), collection=collection_name)
            return ""

        if not chunks:
            return ""

        # Delegate top_k chunks for High Accuracy Reranking through our Cloud engine
        rescored_docs = await self.reranker.rerank(query=query, documents=chunks, top_n=limit)
        return "\n---\n".join(rescored_docs)

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
