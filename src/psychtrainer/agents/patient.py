"""
Patient Agent — Logic and Persona.

This module defines "James", the simulated patient.
It combines the system prompt (persona) with the RAG + LLM execution logic.
"""

from __future__ import annotations

import logging

from langchain_community.chat_models import ChatLiteLLM
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from psychtrainer.config import settings
from psychtrainer.rag.knowledge import Retriever
from psychtrainer.workflow.state import ChatMessage, MessageRole, Phase, SimulationState

logger = logging.getLogger(__name__)

from psychtrainer.workflow.prompt_registry import get_system_prompt


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
        patient_context = retriever.get_patient_context(student_msg)
        medical_context = retriever.get_medical_knowledge(student_msg)
    except Exception as e:
        logger.error(f"Retriever error (Patient): {e}")
        patient_context = ""
        medical_context = ""

    # 2. Build Prompt
    # FETCH DYNAMIC REGISTRY PROMPT asynchronously
    base_prompt_template = await get_system_prompt("patient_persona")
    
    system_prompt = base_prompt_template.format(
        patient_context=patient_context,
        medical_context=medical_context,
        phase=phase.value,
        few_shot_examples=state.get("few_shot_examples", ""),
        summary=state.get("summary", "None available yet."),
    )

    lc_messages = [SystemMessage(content=system_prompt)]
    for msg in state["messages"]:
        if msg.role == MessageRole.PATIENT:
            lc_messages.append(AIMessage(content=msg.content))
        else:
            lc_messages.append(HumanMessage(content=msg.content))

    llm = ChatLiteLLM(
        model=settings.llm_model,
        temperature=0.7,
        max_tokens=150,
        api_key=settings.groq_api_key,
    )

    try:
        response = await llm.ainvoke(lc_messages, config)
        content = response.content
            
            
    except Exception as e:
        logger.error(f"Patient LLM error: {e}")
        content = "I'm... not sure how to answer that."  # Better fallback

    return {
        "messages": [ChatMessage(role=MessageRole.PATIENT, content=content)],
        "patient_context": patient_context,
        "medical_context": medical_context,
    }
