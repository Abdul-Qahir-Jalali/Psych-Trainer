"""
WebSocket Handler — Real-time chat.

• Persistence: Uses SQLite-backed LangGraph state.
• Thread-Safety: Runs sync workflow in Executor.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from psychtrainer.agents.professor import generate_final_grade
from psychtrainer.workflow.state import ChatMessage, MessageRole

logger = logging.getLogger(__name__)
router = APIRouter()
executor = ThreadPoolExecutor(max_workers=5)


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Real-time chat endpoint with persistence.
    """
    await websocket.accept()

    workflow = websocket.app.state.workflow
    config = {"configurable": {"thread_id": session_id}}

    # Verify session exists
    try:
        # Run sync `get_state` in thread
        snapshot = await asyncio.get_running_loop().run_in_executor(
            executor, workflow.get_state, config
        )
        if not snapshot.values:
            # If no state, session is invalid or not started via API
            await websocket.close(reason="Session not found")
            return
    except Exception:
        await websocket.close(reason="Session error")
        return

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "end":
                await _handle_end_session(websocket, workflow, config)
                break

            content = data.get("content", "").strip()
            if not content:
                continue

            # 1. Prepare Input
            turn_count = snapshot.values.get("turn_count", 0)
            msg = ChatMessage(
                role=MessageRole.STUDENT,
                content=content,
                metadata={"turn": turn_count}
            )
            
            inputs = {
                "messages": [msg],
                "turn_count": turn_count + 1
            }

            # 2. Run Workflow (Sync -> Async Executor)
            result = await asyncio.get_running_loop().run_in_executor(
                executor, workflow.invoke, inputs, config
            )
            
            # Update snapshot for next loop
            # Actually invoke returns final state, but loop needs fresh snapshot?
            # Result IS the final state values.
            # But let's be safe and rely on what invoke returns.
            pass

            # 3. Send Response
            await _send_update(websocket, result)

    except WebSocketDisconnect:
        logger.info(f"WS disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WS Error: {e}")
        try:
            await websocket.close()
        except:
            pass


async def _handle_end_session(ws: WebSocket, workflow, config: dict):
    # Run in executor
    loop = asyncio.get_running_loop()
    
    def _compute_grade():
        state = workflow.get_state(config).values
        if not state.get("grade_report"):
            report = generate_final_grade(state)
            workflow.update_state(config, {
                "grade_report": report,
                "is_ended": True
            })
            return report
        return state["grade_report"]

    report = await loop.run_in_executor(executor, _compute_grade)
    
    await ws.send_json({
        "type": "grade_report",
        "report": report.model_dump()
    })


async def _send_update(ws: WebSocket, state: dict):
    # Find last patient message
    patient_reply = ""
    # State has full history now due to reducer
    messages = state.get("messages", [])
    
    for m in reversed(messages):
        if m.role == MessageRole.PATIENT:
            patient_reply = m.content
            break
    
    # Find last note
    notes = state.get("professor_notes", [])
    note = notes[-1] if notes else None

    await ws.send_json({
        "type": "patient_response",
        "content": patient_reply,
        "phase": state.get("phase"),
        "turn_count": state.get("turn_count", 0),
        "professor_note": note,
        "is_ended": state.get("is_ended", False)
    })
