"""
Prompt Registry — The Cache Layer for Dynamic LLM Instructions.

This module guarantees 0-downtime prompt engineering. 
1. It immediately queries Upstash Redis for cached persona instructions.
2. If missing, it securely fetches from the Supabase public.system_prompts table.
3. Automatically caches the new instruction in Redis for 12 hours.
"""

import logging
from redis.asyncio import Redis, ConnectionPool
from supabase import create_client, Client

from psychtrainer.config import settings

logger = logging.getLogger(__name__)

# Re-use the FastAPI lifespan pool if available, but define for standalone testing
pool = ConnectionPool.from_url(str(settings.redis_uri), decode_responses=True)
redis_client = Redis(connection_pool=pool)

supabase: Client = create_client(settings.supabase_url, settings.supabase_anon_key)

async def get_system_prompt(role: str, ignore_cache: bool = False) -> str:
    """
    Retrieves the system prompt payload for a given clinical role.
    
    Args:
        role (str): The primary key ID (e.g., 'patient_persona', 'professor_grader')
        ignore_cache (bool): Force a clean read from Supabase DB to refresh cache.
    """
    cache_key = f"prompt:{role}"
    
    if not ignore_cache:
        try:
            cached_val = await redis_client.get(cache_key)
            if cached_val:
                logger.debug(f"⚡ Redis Cache HIT for Prompt [{role}]")
                return cached_val
        except Exception as e:
            logger.warning(f"⚠️ Redis prompt cache failure: {e}")

    logger.info(f"☁️ Fetching Prompt [{role}] from Supabase Registry...")
    try:
        response = supabase.table("system_prompts").select("content").eq("role", role).execute()
        
        if not response.data:
            raise ValueError(f"CRITICAL: Prompt role '{role}' missing from Supabase DB!")
            
        content = response.data[0]["content"]
        
        # Cache for 12 hours (43200 seconds)
        try:
            await redis_client.setex(cache_key, 43200, content)
        except Exception:
            pass # Non-fatal if cache write fails
            
        return content

    except Exception as e:
        logger.error(f"❌ Supabase Prompt Registry failure: {e}")
        # Fallback strings to guarantee application DOES NOT CRASH
        if role == "patient_persona":
            return "You are a psychiatric patient."
        elif role == "professor_grader":
            return "You are a grading professor."
        elif role == "phase_router":
            return "Return the next phase. Options: introduction, examination, diagnosis, debrief."
        raise e
