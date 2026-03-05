"""
Knowledge Retrieval — The interface to the vector database.

This module provides the `Retriever` class which:
1. Connects to the Qdrant instance
2. Embeds incoming queries
3. Searches specific collections (patient_script, grading_rubric, etc.)
4. Returns context strings for the LLM.
"""

from __future__ import annotations

import structlog

import asyncio
from fastembed import TextEmbedding, SparseTextEmbedding
from sentence_transformers import CrossEncoder
from qdrant_client import QdrantClient, models as qdrant_models

from psychtrainer.config import settings

logger = structlog.get_logger(__name__)


class Retriever:
    """ Retrieves relevant context from Qdrant based on semantic similarity. """

    def __init__(self):
        self.client = QdrantClient(path=settings.qdrant_path)
        self.model = TextEmbedding(settings.embedding_model)
        self.sparse_model = SparseTextEmbedding(settings.sparse_embedding_model)
        self.cross_encoder = CrossEncoder(settings.cross_encoder_model)

    async def search(self, query: str, collection_name: str, limit: int = 3) -> str:
        """Search a collection using Hybrid Search + CrossEncoder Reranking."""
        if not self.client.collection_exists(collection_name):
            return ""

        loop = asyncio.get_running_loop()

        def _sync_query():
            dense_vector = list(self.model.embed([query]))[0].tolist()
            sparse_vector = list(self.sparse_model.embed([query]))[0].as_object()
            
            return self.client.query_points(
                collection_name=collection_name,
                prefetch=[
                    qdrant_models.Prefetch(
                        query=sparse_vector,
                        using="sparse",
                        limit=20,
                    ),
                    qdrant_models.Prefetch(
                        query=dense_vector,
                        using="dense",
                        limit=20,
                    ),
                ],
                query=qdrant_models.FusionQuery(fusion=qdrant_models.Fusion.RRF),
                limit=20,
            )

        results = await loop.run_in_executor(None, _sync_query)
        chunks = [hit.payload.get("text", "") for hit in results.points]

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
