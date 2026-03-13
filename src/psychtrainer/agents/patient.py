"""
Patient Agent — Logic and Persona.

This module defines "James", the simulated patient.
It combines the system prompt (persona) with the RAG + LLM execution logic.
"""

from __future__ import annotations

import structlog
import litellm
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from tenacity import retry, stop_after_attempt, wait_exponential

from psychtrainer.config import settings
from psychtrainer.rag.knowledge import Retriever
from psychtrainer.workflow.state import ChatMessage, MessageRole, Phase, SimulationState
from psychtrainer.workflow.prompt_registry import get_system_prompt

logger = structlog.get_logger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def _invoke_llm_with_retry(messages: list) -> str:
    """Executes the LLM with enterprise algebraic fallback (exponential backoff)."""
    response = await litellm.acompletion(
        model=settings.llm_model,
        messages=messages,
        temperature=0.7,
        max_tokens=150,
        api_key=settings.groq_api_key,
    )
    return response.choices[0].message.content.strip()


# ── The Agent Logic ──────────────────────────────────────────────

async def patient_node(state: SimulationState, config: RunnableConfig, retriever: Retriever) -> dict:
    """
    Executes the Patient's turn asynchronously.
    1. Retrieves context (RAG).
    2. Builds prompt with current Phase.
    3. Calls LLM (Non-blocking).
    """
    student_msg = state["messages"][-1].content
    phase = state["phase"]

    # 1. Retrieve Context
    try:
        patient_context = await retriever.get_patient_context(student_msg)
        medical_context = await retriever.get_medical_knowledge(student_msg)
    except Exception as e:
        logger.error(f"Retriever error (Patient): {e}")
        patient_context = ""
        medical_context = ""

    # 2. Build Prompt — Fetch dynamic registry prompt asynchronously
    base_prompt_template = await get_system_prompt("patient_persona")

    system_prompt = base_prompt_template.format(
        patient_context=patient_context,
        medical_context=medical_context,
        phase=phase.value,
        few_shot_examples=state.get("few_shot_examples", ""),
        summary=state.get("summary", "None available yet."),
    )

    # 3. Build litellm-compatible message list (same format as professor.py)
    lc_messages = [{"role": "system", "content": system_prompt}]
    for msg in state["messages"]:
        role = "assistant" if msg.role == MessageRole.PATIENT else "user"
        lc_messages.append({"role": role, "content": msg.content})

    try:
        content = await _invoke_llm_with_retry(lc_messages)
    except Exception as e:
        logger.error(f"Patient LLM error exhausted all retries: {e}")
        raise e  # Fail-fast to trigger HTTP 500 error on the frontend

    return {
        "messages": [ChatMessage(role=MessageRole.PATIENT, content=content)],
        "patient_context": patient_context,
        "medical_context": medical_context,
    }
