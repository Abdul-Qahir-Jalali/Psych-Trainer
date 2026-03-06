"""
FastAPI Application — The main entry point.

• Lifespan: Initializes AsyncPostgresSaver for session persistence.
• Routes: Uses `thread_id` to manage state via LangGraph.
• Store: Replaces in-memory store with permanent SQLite DB.
"""

from __future__ import annotations

import asyncio
import json
import queue
import structlog
from psychtrainer.logger_setup import setup_logger
import threading
import uuid
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings

from psychtrainer.agents.professor import generate_final_grade
from psychtrainer.config import settings
from psychtrainer.rag.ingest import load_few_shot_examples
from psychtrainer.rag.knowledge import Retriever
from psychtrainer.rag.pg_knowledge import PGRetriever
from psychtrainer.service.schema import (
    ChatRequest,
    ChatResponse,
    GradeRequest,
    GradeResponse,
    SessionStartResponse,
    SessionStateResponse,
    SessionListResponse,  # Will create this below or inline
)
from psychtrainer.service.socket import router as socket_router
from psychtrainer.workflow.graph import build_workflow
from psychtrainer.workflow.state import ChatMessage, MessageRole, Phase

setup_logger()
logger = structlog.get_logger(__name__)

security = HTTPBearer()

limiter = Limiter(key_func=lambda req: req.state.user_id if hasattr(req.state, "user_id") else get_remote_address(req))

def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Cryptographically validates the Supabase JWT locally (Zero-Latency)."""
    try:
        # Avoid 500ms network round trips by doing the math locally
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated"
        )
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("JWT missing subject (user_id).")
        request.state.user_id = user_id
        return user_id
    except jwt.ExpiredSignatureError:
        logger.error("auth_failure", reason="Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error("auth_failure", detail=str(e), reason="invalid_token")
        raise HTTPException(status_code=401, detail="Invalid token signature")
    except Exception as e:
        logger.error("auth_failure", detail=str(e))
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
    1. Connect to SQLite DB for checkpoints.
    2. Load RAG + Workflow.
    """
    logger.info("Initializing PsychTrainer...")
    
    # 1. Database Connection
    # Uses psycopg async connection pool for high-concurrency connections
    pool = AsyncConnectionPool(conninfo=settings.postgres_uri)
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.asetup() # Automatically creates all LangGraph tables securely
    
    # 1b. Rate Limiting (Redis)
    redis_client = redis.from_url(settings.redis_uri, encoding="utf8", decode_responses=True)
    
    # 2. Observability (LangSmith)
    import litellm
    if settings.langchain_tracing_v2.lower() == "true" and settings.langchain_api_key:
        logger.info("LangSmith tracing enabled via LiteLLM.")
        litellm.success_callback = ["langsmith"]
        litellm.failure_callback = ["langsmith"]
    else:
        logger.info("LangSmith tracing is disabled.")

    # 3. RAG & Workflow
    if settings.vector_store == "pgvector":
        retriever = PGRetriever()
        logger.info("Using PGVector for vector search.")
    else:
        retriever = Retriever()
        logger.info("Using Qdrant for vector search.")
        
    examples = load_few_shot_examples()
    workflow = build_workflow(retriever, checkpointer=checkpointer)
    
    # 4. Store in App State
    app.state.pool = pool
    app.state.checkpointer = checkpointer
    app.state.retriever = retriever
    app.state.few_shot_examples = examples
    app.state.workflow = workflow
    
    # 5. Connect to ARQ Redis Pool (for background worker jobs)
    arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_uri))
    app.state.arq_pool = arq_pool
    
    logger.info("✅ System Ready (with Persistence & ARQ).")
    yield
    
    logger.info("🛑 Shutting down & closing DB...")
    await pool.close()
    await redis_client.close()
    await arq_pool.close()


app = FastAPI(title="PsychTrainer", version="3.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket routes
app.include_router(socket_router, prefix="/api")




# ── REST Endpoints (Sync for ThreadPool execution) ────────────────

@app.get("/api/sessions")
def list_sessions(user_id: str = Depends(get_current_user)):
    """
    Returns a list of all historical session IDs with their dynamically generated titles.
    Refactored to query the Supabase UI table instead of looping LangGraph checkpoints (O(1) vs O(N)).
    """
    from psychtrainer.workflow.prompt_registry import supabase
    
    try:
        response = supabase.table("sessions").select("id, title").eq("user_id", user_id).order("last_active", desc=True).limit(50).execute()
        
        # Map Supabase response format to the expected Frontend format
        sessions = [{"session_id": row["id"], "title": row["title"]} for row in response.data]
        return {"sessions": sessions}
        
    except Exception as e:
        logger.error(f"Failed to list sessions from Supabase: {e}")
        return {"sessions": []}

@app.post("/api/session/start", response_model=SessionStartResponse)
async def start_session(user_id: str = Depends(get_current_user)):
    """Begin a new session asynchronously. Initializes state in DB."""
    session_id = f"{user_id}_{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": session_id}}
    
    # Initialize State
    initial_state = {
        "session_id": session_id,
        "title": "New Conversation",
        "phase": Phase.INTRODUCTION,
        "messages": [],
        "professor_notes": [],
        "turn_count": 0,
        "patient_context": "",
        "grading_criteria": "",
        "medical_context": "",
        "few_shot_examples": app.state.few_shot_examples,
        "is_ended": False,
        "grade_report": None,
    }
    
    # Commit UI Session to Supabase (Fast Read Table)
    from psychtrainer.workflow.prompt_registry import supabase
    try:
        supabase.table("sessions").insert({
            "id": session_id,
            "user_id": user_id,
            "title": "New Conversation",
            "is_ended": False
        }).execute()
    except Exception as e:
        logger.error(f"Failed to create Supabase session UI record: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to initialize session in database. Please try again."
        )
    
    # Commit initial deep state to DB (LangGraph)
    await app.state.workflow.aupdate_state(config, initial_state)

    return SessionStartResponse(
        session_id=session_id,
        message="Session started. You are meeting James (21, OCD).",
        phase=Phase.INTRODUCTION,
    )


@app.get("/api/session/{session_id}", response_model=SessionStateResponse)
async def get_session_state(session_id: str, user_id: str = Depends(get_current_user)):
    """Retrieve full session state asynchronously for resumption."""
    if not session_id.startswith(f"{user_id}_"):
        raise HTTPException(status_code=403, detail="Unauthorized access to session")
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        snapshot = await app.state.workflow.aget_state(config)
        current_state = snapshot.values
        if not current_state:
             raise HTTPException(404, "Session not found")
    except Exception:
        raise HTTPException(404, "Session not found")

    return SessionStateResponse(
        session_id=session_id,
        phase=current_state["phase"],
        turn_count=current_state["turn_count"],
        messages=current_state["messages"],
        is_ended=current_state["is_ended"],
        grade_report=current_state.get("grade_report"),
    )


@app.post("/api/session/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """Process student message via persistent workflow natively (async)."""
    if not request.session_id.startswith(f"{user_id}_"):
        raise HTTPException(status_code=403, detail="Unauthorized access to session")
    config = {"configurable": {"thread_id": request.session_id}}
    
    # Check if session exists (by trying to get state)
    try:
        snapshot = await app.state.workflow.aget_state(config)
        current_state = snapshot.values
        if not current_state:
             raise HTTPException(404, "Session not found")
    except Exception:
        raise HTTPException(404, "Session not found")

    if current_state.get("is_ended"):
        raise HTTPException(400, "Session ended. Please start new one.")

    # 1. Update with User Message
    msg = ChatMessage(
        role=MessageRole.STUDENT,
        content=request.message,
        metadata={"turn": current_state.get("turn_count", 0)}
    )
    
    # 2. Invoke Workflow
    # Note: State update uses append semantics handled by SimulationState
    input_update = {
        "messages": [msg], 
        "turn_count": current_state["turn_count"] + 1
    }
    
    result = await app.state.workflow.ainvoke(input_update, config)
    
    # 3. Extract Response
    patient_reply = ""
    for m in reversed(result["messages"]):
        if m.role == MessageRole.PATIENT:
            patient_reply = m.content
            break
            
    note = result.get("professor_notes", [])[-1] if result.get("professor_notes") else None

    # 4. Async Title Generation on turn 1
    if result["turn_count"] == 1:
        # Safely enqueue to ARQ Redis worker
        await app.state.arq_pool.enqueue_job("generate_title_task", request.session_id, request.message, patient_reply)

    return ChatResponse(
        session_id=request.session_id,
        patient_response=patient_reply,
        phase=result["phase"],
        turn_count=result["turn_count"],
        professor_note=note,
    )


@app.post("/api/session/stream_chat")
@limiter.limit("20/minute")
async def stream_chat(request: Request, payload: ChatRequest, user_id: str = Depends(get_current_user)):
    """Process student message and stream tokens back natively via SSE (No Threading)."""
    if not payload.session_id.startswith(f"{user_id}_"):
        raise HTTPException(status_code=403, detail="Unauthorized access to session")
    session_id = payload.session_id
    config = {
        "configurable": {
            "thread_id": session_id,
        }
    }
    
    # 1. State setup and validation
    try:
        snapshot = await app.state.workflow.aget_state(config)
        current_state = snapshot.values
        if not current_state:
             raise HTTPException(404, "Session not found")
    except Exception:
        raise HTTPException(404, "Session not found")

    if current_state.get("is_ended"):
        raise HTTPException(400, "Session ended. Please start new one.")

    msg = ChatMessage(
        role=MessageRole.STUDENT,
        content=payload.message,
        metadata={"turn": current_state.get("turn_count", 0)}
    )
    input_update = {
        "messages": [msg], 
        "turn_count": current_state["turn_count"] + 1
    }

    # 2. Native Async Generator for SSE
    async def event_generator():
        try:
            async for event in app.state.workflow.astream_events(input_update, config, version="v2"):
                # Stream the patient's LLM tokens as they arrive
                if event["event"] == "on_chat_model_stream" and event["metadata"].get("langgraph_node") == "patient":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"data: {json.dumps({'token': chunk.content})}\n\n"
                        
            # Graph finished executing, fetch the final state snapshot
            final_snapshot = await app.state.workflow.aget_state(config)
            result = final_snapshot.values
            
            # 3. Async Title Generation on turn 1
            if result["turn_count"] == 1:
                patient_reply = ""
                for m in reversed(result["messages"]):
                    if m.role == MessageRole.PATIENT:
                        patient_reply = m.content
                        break
                # Safely enqueue to ARQ Redis worker
                await app.state.arq_pool.enqueue_job("generate_title_task", session_id, payload.message, patient_reply)

            note = result.get("professor_notes", [])[-1] if result.get("professor_notes") else None
            phase_val = result["phase"].value if hasattr(result["phase"], "value") else result["phase"]
            final_data = {
                "phase": phase_val,
                "turn_count": result["turn_count"],
                "professor_note": note,
            }
            yield f"event: done\ndata: {json.dumps(final_data)}\n\n"

        except Exception as e:
            logger.error(f"Graph stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/session/end", response_model=GradeResponse)
@limiter.limit("5/minute")
async def end_session(request: Request, payload: GradeRequest, user_id: str = Depends(get_current_user)):
    """End session asynchronously and persist grade."""
    if not payload.session_id.startswith(f"{user_id}_"):
        raise HTTPException(status_code=403, detail="Unauthorized access to session")
    config = {"configurable": {"thread_id": payload.session_id}}
    
    try:
        # Get state snapshot
        snapshot = await app.state.workflow.aget_state(config)
        state = snapshot.values
        if not state:
             raise HTTPException(404, "Session not found")
    except Exception:
        raise HTTPException(404, "Session not found")

    if not state.get("grade_report"):
        report = await generate_final_grade(state)
        # Update state with report
        await app.state.workflow.aupdate_state(config, {
            "grade_report": report,
            "is_ended": True
        })
        state["grade_report"] = report
        
        # Sync to UI table
        from psychtrainer.workflow.prompt_registry import supabase
        try:
            supabase.table("sessions").update({"is_ended": True}).eq("id", payload.session_id).execute()
        except Exception as e:
            logger.error(f"Failed to flag Supabase UI session as ended: {e}")

    return GradeResponse(
        session_id=payload.session_id,
        report=state["grade_report"],
    )


import os

# Mount Static
frontend_dir = "frontend-react/dist" if os.path.exists("frontend-react/dist") else "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
