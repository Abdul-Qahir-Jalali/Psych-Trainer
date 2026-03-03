"""
Knowledge Retrieval — The interface to the vector database.

This module provides the `Retriever` class which:
1. Connects to the Qdrant instance
2. Embeds incoming queries
3. Searches specific collections (patient_script, grading_rubric, etc.)
4. Returns context strings for the LLM.
"""

from __future__ import annotations

import logging

import asyncio
from fastembed import TextEmbedding
from qdrant_client import QdrantClient

from psychtrainer.config import settings

logger = logging.getLogger(__name__)


class Retriever:
    """ Retrieves relevant context from Qdrant based on semantic similarity. """

    def __init__(self):
        self.client = QdrantClient(path=settings.qdrant_path)
        self.model = TextEmbedding(settings.embedding_model)

    async def search(self, query: str, collection_name: str, limit: int = 3) -> str:
        """Search a collection and return concatenated text results asynchronously."""
        if not self.client.collection_exists(collection_name):
            return ""

        loop = asyncio.get_running_loop()

        def _sync_query():
            query_vector = list(self.model.embed([query]))[0].tolist()
            return self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
            )

        results = await loop.run_in_executor(None, _sync_query)

        return "\n---\n".join([hit.payload.get("text", "") for hit in results.points])

    async def get_patient_context(self, query: str) -> str:
        """Find relevant lines from the OSCE script."""
        return await self.search(query, "patient_script", limit=3)

    async def get_grading_criteria(self, query: str) -> str:
        """Find relevant grading rules from the rubric."""
        return await self.search(query, "grading_rubric", limit=3)

    async def get_medical_knowledge(self, query: str) -> str:
        """Find relevant medical facts (MedQA)."""
        return await self.search(query, "medical_knowledge", limit=2)
