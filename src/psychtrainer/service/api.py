"""
FastAPI Application — The main entry point.

• Lifespan: Initializes SqliteSaver for session persistence.
• Routes: Uses `thread_id` to manage state via LangGraph.
• Store: Replaces in-memory store with permanent SQLite DB.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from psychtrainer.agents.professor import generate_final_grade
from psychtrainer.config import settings
from psychtrainer.rag.ingest import load_few_shot_examples
from psychtrainer.rag.knowledge import Retriever
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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
    1. Connect to SQLite DB for checkpoints.
    2. Load RAG + Workflow.
    """
    logger.info("Initializing PsychTrainer...")
    
    # 1. Database Connection
    # Uses psycopg connection pool for concurrent connections
    pool = ConnectionPool(conninfo=settings.postgres_uri)
    checkpointer = PostgresSaver(pool)
    checkpointer.setup() # Automatically creates all LangGraph tables if they don't exist
    
    # 2. Observability (LangSmith)
    import litellm
    if settings.langchain_tracing_v2.lower() == "true" and settings.langchain_api_key:
        logger.info("LangSmith tracing enabled via LiteLLM.")
        litellm.success_callback = ["langsmith"]
        litellm.failure_callback = ["langsmith"]
    else:
        logger.info("LangSmith tracing is disabled.")

    # 3. RAG & Workflow
    retriever = Retriever()
    examples = load_few_shot_examples()
    workflow = build_workflow(retriever, checkpointer=checkpointer)
    
    # 3. Store in App State
    app.state.pool = pool
    app.state.checkpointer = checkpointer
    app.state.retriever = retriever
    app.state.few_shot_examples = examples
    app.state.workflow = workflow
    
    logger.info("✅ System Ready (with Persistence).")
    yield
    
    logger.info("🛑 Shutting down & closing DB...")
    pool.close()


app = FastAPI(title="PsychTrainer", version="3.1.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket routes
app.include_router(socket_router, prefix="/api")


def generate_title_task(session_id: str, student_msg: str, patient_msg: str, app: FastAPI):
    """Background task to generate a conversational title using the LLM."""
    try:
        import litellm
        from psychtrainer.config import settings

        prompt = (
            "Summarize the following exchange into a short, professional, 3-5 word title "
            "for a clinical interview session. DO NOT use quotes. Example: 'OCD Initial Assessment' or 'Sleep Trouble History'.\n\n"
            f"Student: {student_msg}\nPatient: {patient_msg}"
        )
        response = litellm.completion(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=20,
            api_key=settings.groq_api_key,
        )
        title = response.choices[0].message.content.strip().strip('"').strip("'")
        
        # Save to LangGraph state
        config = {"configurable": {"thread_id": session_id}}
        app.state.workflow.update_state(config, {"title": title})
        logger.info(f"Generated title for {session_id}: {title}")
    except Exception as e:
        logger.error(f"Title generation failed: {e}")

# ── REST Endpoints (Sync for ThreadPool execution) ────────────────

@app.get("/api/sessions")
def list_sessions():
    """Returns a list of all historical session IDs with their dynamically generated titles."""
    try:
        # 1. Use official Checkpointer API to safely retrieve highest-level checkpoint info
        checkpoints = app.state.workflow.checkpointer.list(None)
        
        seen_threads = set()
        thread_ids = []
        for c in checkpoints:
            tid = c.config.get("configurable", {}).get("thread_id")
            if tid and tid not in seen_threads:
                seen_threads.add(tid)
                thread_ids.append(tid)
                if len(thread_ids) >= 50:
                    break

        sessions = []
        for thread_id in thread_ids:
            if not thread_id:
                continue
            
            # Fetch state to get title (or generate fallback)
            try:
                state = app.state.workflow.get_state({"configurable": {"thread_id": thread_id}}).values
                title = state.get("title")
                
                if not title or title == "New Conversation":
                    messages = state.get("messages", [])
                    if messages and messages[0].role.value == "student":
                        msg = messages[0].content
                        title = (msg[:30] + "...") if len(msg) > 30 else msg
                    else:
                        title = "New Conversation"

                sessions.append({"session_id": thread_id, "title": title})
            except Exception:
                sessions.append({"session_id": thread_id, "title": f"Session {thread_id[:6]}"})

        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return {"sessions": []}

@app.post("/api/session/start", response_model=SessionStartResponse)
def start_session():
    """Begin a new session. Initializes state in DB."""
    session_id = uuid.uuid4().hex[:12]
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
    
    # Commit initial state to DB
    app.state.workflow.update_state(config, initial_state)

    return SessionStartResponse(
        session_id=session_id,
        message="Session started. You are meeting James (21, OCD).",
        phase=Phase.INTRODUCTION,
    )


@app.get("/api/session/{session_id}", response_model=SessionStateResponse)
def get_session_state(session_id: str):
    """Retrieve full session state for resumption."""
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        current_state = app.state.workflow.get_state(config).values
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
def chat(request: ChatRequest):
    """Process student message via persistent workflow."""
    config = {"configurable": {"thread_id": request.session_id}}
    
    # Check if session exists (by trying to get state)
    try:
        current_state = app.state.workflow.get_state(config).values
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
    
    result = app.state.workflow.invoke(input_update, config)
    
    # 3. Extract Response
    patient_reply = ""
    for m in reversed(result["messages"]):
        if m.role == MessageRole.PATIENT:
            patient_reply = m.content
            break
            
    note = result.get("professor_notes", [])[-1] if result.get("professor_notes") else None

    # 4. Async Title Generation on turn 1
    if result["turn_count"] == 1:
        threading.Thread(target=generate_title_task, args=(request.session_id, request.message, patient_reply, app)).start()

    return ChatResponse(
        session_id=request.session_id,
        patient_response=patient_reply,
        phase=result["phase"],
        turn_count=result["turn_count"],
        professor_note=note,
    )


class AsyncQueueWrapper:
    """Bridges synchronous producer (LangGraph thread) to pure async FastAPI generator."""
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.queue = asyncio.Queue()
        
    def put(self, item):
        self.loop.call_soon_threadsafe(self.queue.put_nowait, item)
        
    async def get(self):
        return await self.queue.get()


@app.post("/api/session/stream_chat")
async def stream_chat(request: ChatRequest):
    """Process student message and stream tokens back via SSE."""
    session_id = request.session_id
    stream_queue = AsyncQueueWrapper()
    config = {
        "configurable": {
            "thread_id": session_id,
            "stream_queue": stream_queue
        }
    }
    
    # 1. State setup and validation
    try:
        current_state = app.state.workflow.get_state(config).values
        if not current_state:
             raise HTTPException(404, "Session not found")
    except Exception:
        raise HTTPException(404, "Session not found")

    if current_state.get("is_ended"):
        raise HTTPException(400, "Session ended. Please start new one.")

    msg = ChatMessage(
        role=MessageRole.STUDENT,
        content=request.message,
        metadata={"turn": current_state.get("turn_count", 0)}
    )
    input_update = {
        "messages": [msg], 
        "turn_count": current_state["turn_count"] + 1
    }

    # 2. Generator for SSE
    async def event_generator():
        def run_graph():
            try:
                result = app.state.workflow.invoke(input_update, config)
                stream_queue.put({"__done__": True, "result": result})
            except Exception as e:
                logger.error(f"Graph stream error: {e}")
                stream_queue.put({"__error__": str(e)})

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, run_graph)

        while True:
            item = await stream_queue.get()

            if isinstance(item, dict):
                if "__done__" in item:
                    result = item["result"]
                    
                    # 3. Async Title Generation on turn 1
                    if result["turn_count"] == 1:
                        patient_reply = ""
                        for m in reversed(result["messages"]):
                            if m.role == MessageRole.PATIENT:
                                patient_reply = m.content
                                break
                        loop = asyncio.get_running_loop()
                        loop.run_in_executor(None, generate_title_task, session_id, request.message, patient_reply, app)

                    note = result.get("professor_notes", [])[-1] if result.get("professor_notes") else None
                    phase_val = result["phase"].value if hasattr(result["phase"], "value") else result["phase"]
                    final_data = {
                        "phase": phase_val,
                        "turn_count": result["turn_count"],
                        "professor_note": note,
                    }
                    yield f"event: done\ndata: {json.dumps(final_data)}\n\n"
                    break
                elif "__error__" in item:
                    yield f"event: error\ndata: {json.dumps({'error': item['__error__']})}\n\n"
                    break
            else:
                yield f"data: {json.dumps({'token': item})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/session/end", response_model=GradeResponse)
def end_session(request: GradeRequest):
    """End session and persist grade."""
    config = {"configurable": {"thread_id": request.session_id}}
    
    try:
        # Get state snapshot
        snapshot = app.state.workflow.get_state(config)
        state = snapshot.values
        if not state:
             raise HTTPException(404, "Session not found")
    except Exception:
        raise HTTPException(404, "Session not found")

    if not state.get("grade_report"):
        report = generate_final_grade(state)
        # Update state with report
        app.state.workflow.update_state(config, {
            "grade_report": report,
            "is_ended": True
        })
        state["grade_report"] = report

    return GradeResponse(
        session_id=request.session_id,
        report=state["grade_report"],
    )


# Mount Static
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
