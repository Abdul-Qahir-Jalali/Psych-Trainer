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

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from psychtrainer.config import settings

logger = logging.getLogger(__name__)


class Retriever:
    """ Retrieves relevant context from Qdrant based on semantic similarity. """

    def __init__(self):
        self.client = QdrantClient(path=settings.qdrant_path)
        self.model = SentenceTransformer(settings.embedding_model)

    def search(self, query: str, collection_name: str, limit: int = 3) -> str:
        """Search a collection and return concatenated text results."""
        if not self.client.collection_exists(collection_name):
            return ""

        query_vector = self.model.encode(query).tolist()
        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
        )

        return "\n---\n".join([hit.payload.get("text", "") for hit in results.points])

    def get_patient_context(self, query: str) -> str:
        """Find relevant lines from the OSCE script."""
        return self.search(query, "patient_script", limit=3)

    def get_grading_criteria(self, query: str) -> str:
        """Find relevant grading rules from the rubric."""
        return self.search(query, "grading_rubric", limit=3)

    def get_medical_knowledge(self, query: str) -> str:
        """Find relevant medical facts (MedQA)."""
        return self.search(query, "medical_knowledge", limit=2)
