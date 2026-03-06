"""
PGVector Data Ingestion Logic

This module handles:
1. Re-using chunking logic from ingest.py
2. Inserting dense embeddings into PostgreSQL via pgvector
"""

from __future__ import annotations

import asyncio
import json
import structlog
from typing import Any
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector_async
from fastembed import TextEmbedding

from psychtrainer.config import settings
from psychtrainer.rag.ingest import TextChunk

logger = structlog.get_logger(__name__)

async def init_pgvector_db(pool_or_uri: str | AsyncConnectionPool):
    """Ensure the vector extension and table exist in Postgres."""
    close_pool = False
    if isinstance(pool_or_uri, str):
        pool = AsyncConnectionPool(conninfo=pool_or_uri, min_size=1, max_size=5)
        close_pool = True
    else:
        pool = pool_or_uri
    
    try:
        async with pool.connection() as conn:
            # Install extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            # Register the vector type mapping
            await register_vector_async(conn)
            
            # Create our embeddings table
            dim = settings.embedding_dimension
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    id SERIAL PRIMARY KEY,
                    collection_name VARCHAR(255) NOT NULL,
                    text TEXT NOT NULL,
                    metadata JSONB,
                    embedding vector({dim})
                );
                """
            )
            # Create index to speed up exact matches and filtering
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS document_embeddings_collection_idx 
                ON document_embeddings (collection_name);
                """
            )
            # Create a GIN index on text for full-text keyword search
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS document_embeddings_text_idx 
                ON document_embeddings USING GIN (to_tsvector('english', text));
                """
            )
            logger.info("pgvector_db_initialized", table="document_embeddings")
    except Exception as e:
        logger.error("pgvector_init_failed", error=str(e))
        raise
    finally:
        if close_pool:
            await pool.close()

async def index_chunks_pg(
    chunks: list[TextChunk],
    collection_name: str,
    pool_uri: str,
    model: TextEmbedding,
) -> int:
    """Embed chunks and insert them into PostgreSQL."""
    
    pool = AsyncConnectionPool(conninfo=pool_uri, min_size=1, max_size=5)
    
    try:
        # First ensure the db schema is ready
        await init_pgvector_db(pool)
        
        texts = [c.text for c in chunks]
        
        # We wrap in run_in_executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        dense_embeddings = await loop.run_in_executor(None, lambda: list(model.embed(texts)))
        
        total_inserted = 0
        
        async with pool.connection() as conn:
            await register_vector_async(conn)
            async with conn.cursor() as cur:
                # To make it idempotent, we optionally delete existing from this collection 
                # or insert new rows. We'll simply insert for now. 
                # Or delete before:
                # await cur.execute("DELETE FROM document_embeddings WHERE collection_name = %s", (collection_name,))
                
                batch_size = 100
                for i in range(0, len(chunks), batch_size):
                    batch_chunks = chunks[i: i + batch_size]
                    batch_embs = dense_embeddings[i: i + batch_size]
                    
                    data_to_insert = [
                        (collection_name, chunk.text, json.dumps(chunk.metadata), emb.tolist())
                        for chunk, emb in zip(batch_chunks, batch_embs)
                    ]
                    
                    # Mass insert using executemany
                    await cur.executemany(
                        """
                        INSERT INTO document_embeddings (collection_name, text, metadata, embedding) 
                        VALUES (%s, %s, %s, %s)
                        """,
                        data_to_insert
                    )
                    total_inserted += len(batch_chunks)
        
        logger.info("indexed_chunks_pg", count=total_inserted, collection=collection_name)
        return total_inserted

    finally:
        await pool.close()
