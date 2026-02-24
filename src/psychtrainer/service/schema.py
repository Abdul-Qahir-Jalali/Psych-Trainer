"""
API Schemas — The external contract for the REST API.

Defines the JSON structures for Requests and Responses.
"""

from __future__ import annotations

from pydantic import BaseModel

from psychtrainer.workflow.state import ChatMessage, GradeReport, Phase


# ── Session Management ───────────────────────────────────────────

class SessionStartResponse(BaseModel):
    """Response payload for POST /api/session/start"""
    session_id: str
    message: str
    phase: Phase


class SessionStateResponse(BaseModel):
    """Payload for GET /api/session/{session_id}"""
    session_id: str
    phase: Phase
    turn_count: int
    messages: list[ChatMessage]
    is_ended: bool
    grade_report: GradeReport | None = None


class SessionListResponse(BaseModel):
    """Payload for GET /api/sessions"""
    sessions: list[dict[str, str]]


# ── Chat Operations ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request payload for POST /api/session/chat"""
    session_id: str
    message: str


class ChatResponse(BaseModel):
    """Response payload for POST /api/session/chat"""
    session_id: str
    patient_response: str
    phase: Phase
    turn_count: int
    professor_note: str | None = None


# ── Grading Operations ───────────────────────────────────────────

class GradeRequest(BaseModel):
    """Request payload for POST /api/session/end"""
    session_id: str


class GradeResponse(BaseModel):
    """Response payload for POST /api/session/end"""
    session_id: str
    report: GradeReport
