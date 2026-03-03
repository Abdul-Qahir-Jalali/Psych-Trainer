"""
ARQ Worker Node for PsychTrainer.

This background worker connects to the Upstash Redis queue and executes
heavy background tasks (like LLM title generation) fully isolated from the main FastAPI ASGI server.
This provides infinite retry resilience and prevents OOM crashes.
"""

from __future__ import annotations

import logging
from typing import Any

import litellm
import redis.asyncio as redis
from arq.connections import RedisSettings
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from psychtrainer.config import settings
from psychtrainer.workflow.graph import build_workflow
from psychtrainer.rag.knowledge import Retriever

logger = logging.getLogger(__name__)


async def generate_title_task(ctx: dict[str, Any], session_id: str, student_msg: str, patient_msg: str) -> str:
    """
    Background worker job to generate a conversational title using the LLM.
    Runs entirely separately from the main FastAPI server.
    """
    try:
        prompt = (
            "Summarize the following exchange into a short, professional, 3-5 word title "
            "for a clinical interview session. DO NOT use quotes. Example: 'OCD Initial Assessment' or 'Sleep Trouble History'.\n\n"
            f"Student: {student_msg}\nPatient: {patient_msg}"
        )
        response = await litellm.acompletion(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=20,
            api_key=settings.groq_api_key,
        )
        title = response.choices[0].message.content.strip().strip('"').strip("'")
        
        # Save to LangGraph state using the connected checkpointer
        config = {"configurable": {"thread_id": session_id}}
        workflow = ctx["workflow"]
        await workflow.aupdate_state(config, {"title": title})
        
        # Save to Supabase UI Table
        from psychtrainer.workflow.prompt_registry import supabase
        try:
            supabase.table("sessions").update({"title": title}).eq("id", session_id).execute()
        except Exception as e:
            logger.error(f"Failed to update Supabase UI title: {e}")
            
        logger.info(f"Generated title for {session_id}: {title}")
        return title
    except Exception as e:
        logger.error(f"Title generation failed: {e}")
        raise e  # Allow ARQ to automatically retry if Groq is down


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize Postgres database pool and LangGraph for the worker."""
    logger.info("Initializing ARQ Worker Node...")
    
    # 1. Database Connection
    pool = AsyncConnectionPool(conninfo=settings.postgres_uri)
    ctx["pool"] = pool
    
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.asetup()
    
    # 2. Rebuild workflow
    retriever = Retriever()
    workflow = build_workflow(retriever, checkpointer=checkpointer)
    ctx["workflow"] = workflow
    
    logger.info("ARQ Worker Database connected.")

async def shutdown(ctx: dict[str, Any]) -> None:
    """Cleanup Postgres pool on shutdown."""
    logger.info("Shutting down ARQ Worker...")
    if pool := ctx.get("pool"):
        await pool.close()

# ARQ Configuration Object
# Fastapi/arq parses the redis_uri into RedisSettings implicitly
class WorkerSettings:
    functions = [generate_title_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_uri)
    max_tries = 3  # Enterprise resilience: retry 3 times if LLM API is down
