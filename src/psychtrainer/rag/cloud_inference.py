"""
Enterprise API Multiplexing logic for externalizing Embeddings and Reranking.
Automatically routes requests to cloud providers (Cohere, Gemini) using litellm
and gracefully falls back to local fastembed models if API keys are missing or 
rate-limits are completely exhausted.
"""
import asyncio
import structlog
from typing import List, Optional
from litellm import aembedding
from fastembed import TextEmbedding
from sentence_transformers import CrossEncoder

from psychtrainer.config import settings

logger = structlog.get_logger(__name__)

class CloudEmbedder:
    """Handles vector embedding math through litellm API Routing or Local Fallback."""
    def __init__(self):
         # If no API keys are provided, we'll instantiate fastembed as the ultimate local fallback.
         # CRITICAL: We DO NOT fallback dynamically during runtime. If a cloud key is present,
         # we strictly stick to it to prevent DB vector dimensionality corruption.
         self._local_model = None
         self.has_cloud = bool(settings.cohere_api_key)
         if not self.has_cloud:
             logger.info("Initializing Local fastembed (384d) due to missing Cloud keys.")
             self._local_model = TextEmbedding(settings.embedding_model)
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Takes a list of strings, routes them to Cloud providers, 
        and returns Dense Vectors in the identical fastembed List of Lists format.
        """
        # 1. Provide ultimate fallback logic if no Internet/Cloud keys exist
        if not self.has_cloud:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: list(self._local_model.embed(texts)))

        # 2. Strict Single-Provider Cloud Route
        model = "cohere/embed-english-v3.0"
            
        try:
            # We strictly enforce Cohere without fallbacks to prevent inserting 768d Gemini vectors 
            # into a 1024d Cohere database, which breaks RAG retrieval and crashes Postgres.
            response = await aembedding(
                model=model,
                input=texts,
                input_type="search_document"
            )
            
            # The API response returns a list of data objects with .embedding floats
            return [data['embedding'] for data in response['data']]
        except Exception as e:
            logger.error("Cohere embedding API failed. Fatal error to prevent vector corruption.", error=str(e))
            raise e

class CloudReranker:
    """Handles Cross-Encoder logic. Cohere provides an industry standard Reranking API."""
    def __init__(self):
        self._local_model = None
        self.can_rerank_cloud = bool(settings.cohere_api_key)
        if not self.can_rerank_cloud:
            logger.info("Initializing Local sentence-transformers due to missing Cohere key.")
            self._local_model = CrossEncoder(settings.cross_encoder_model)
    
    async def rerank(self, query: str, documents: List[str], top_n: int = 3) -> List[str]:
        """
        Submits pairs of (query, doc) to Cohere or local model, 
        returning the highest scoring document strings.
        """
        if not documents:
            return []
            
        # 1. Local Fallback Route
        if not self.can_rerank_cloud:
            def _local_rerank():
                pairs = [[query, doc] for doc in documents]
                scores = self._local_model.predict(pairs)
                scored = sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
                return [doc for score, doc in scored[:top_n]]
            
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _local_rerank)
            
        # 2. Cloud Cohere Routing (Wait on litellm's generic rerank abstraction, or import direct HTTPX)
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.cohere.com/v1/rerank",
                    headers={
                        "Authorization": f"Bearer {settings.cohere_api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    json={
                        "model": "rerank-english-v3.0",
                        "query": query,
                        "documents": documents,
                        "top_n": top_n,
                        "return_documents": True
                    },
                    timeout=10.0
                )
                res.raise_for_status()
                data = res.json()
                # Extract text chunks directly from the returned ordered results
                return [item["document"]["text"] for item in data.get("results", [])]
        except Exception as e:
            logger.error("Cohere Rerank API Failed. Initializing Local CPU Fallback.", error=str(e))
            if not self._local_model:
                self._local_model = CrossEncoder(settings.cross_encoder_model)
            # Duplicate local route inline
            def _emergency_rerank():
                pairs = [[query, doc] for doc in documents]
                scores = self._local_model.predict(pairs)
                scored = sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
                return [doc for score, doc in scored[:top_n]]
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _emergency_rerank)
