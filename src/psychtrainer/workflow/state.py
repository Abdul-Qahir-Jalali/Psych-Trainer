"""
Simulation State & Types — The core data structures of the simulation.

• Enums: MessageRole, Phase
• Models: ChatMessage, CriterionScore, GradeReport
• State: The SimulationState dict used by LangGraph
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

def replace_or_append_messages(left: list[ChatMessage], right: list[ChatMessage] | dict) -> list[ChatMessage]:
    """
    Custom reducer.
    If 'right' is a dict with '__replace__': True, we overwrite the list.
    Otherwise, we append the messages as usual.
    """
    if isinstance(right, dict) and right.get("__replace__"):
        return right.get("messages", [])
    if isinstance(right, list):
        return left + right
    return left + [right]  # Fallback if single message passed


# ── Core Enums ───────────────────────────────────────────────────

class MessageRole(str, Enum):
    """Who sent the message."""
    STUDENT = "student"
    PATIENT = "patient"
    SYSTEM = "system"


class Phase(str, Enum):
    """Progress stages of the clinical interview."""
    INTRODUCTION = "introduction"
    EXAMINATION = "examination"
    DIAGNOSIS = "diagnosis"
    DEBRIEF = "debrief"


# ── Data Models ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in the history."""
    role: MessageRole
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CriterionScore(BaseModel):
    """Score for a specific grading criterion."""
    criterion: str
    score: float = Field(ge=0, le=10)
    feedback: str = ""


class GradeReport(BaseModel):
    """Final evaluation of the student's performance."""
    overall_score: float = Field(ge=0, le=100)
    letter_grade: str
    summary: str = ""
    criteria: list[CriterionScore] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)


# ── Workflow State ───────────────────────────────────────────────

class SimulationState(TypedDict):
    """
    The shared state dictionary for the LangGraph workflow.
    Tracks everything happening in the session.
    """
    session_id: str
    title: str
    phase: Phase
    # Use custom reducer to allow appending normal messages, but overwriting when summarizing
    messages: Annotated[list[ChatMessage], replace_or_append_messages]
    professor_notes: Annotated[list[str], operator.add]
    turn_count: int
    patient_context: str
    grading_criteria: str
    medical_context: str
    few_shot_examples: str
    is_ended: bool
    summary: str
    grade_report: GradeReport | None
