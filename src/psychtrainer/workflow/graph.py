"""
Workflow Graph — The Conversation State Machine.

This module orchestrates the flow:
Student → Patient → Professor → Router → (Loop or End)
"""

from __future__ import annotations

import logging
from functools import partial

import litellm
from langgraph.graph import END, StateGraph

from psychtrainer.agents.patient import patient_node
from psychtrainer.agents.professor import professor_node
from psychtrainer.agents.summarizer import summarize_conversation_node
from psychtrainer.config import settings
from psychtrainer.rag.knowledge import Retriever
from psychtrainer.workflow.state import Phase, SimulationState

logger = logging.getLogger(__name__)


from psychtrainer.workflow.prompt_registry import get_system_prompt


def _router_node(state: SimulationState) -> dict:
    """Decides the next phase based on conversation history."""
    messages = state["messages"]
    current_phase = state["phase"]
    turn_count = state["turn_count"]

    # Hard limits
    if turn_count > 20:
        return {"phase": Phase.DEBRIEF, "is_ended": True}

    # Need enough data
    if len(messages) < 3:
        return {"phase": current_phase}

    # Prepare prompt
    recent_messages = "\n".join(
        f"{m.role.value.upper()}: {m.content}" for m in messages[-6:]
    )
    # Execute LLM to determine next phase using the DYNAMIC registry
    router_prompt_template = asyncio.run(get_system_prompt("phase_router"))
    prompt = router_prompt_template.format(
        recent_messages=recent_messages,
        current_phase=current_phase.value,
        turn_count=turn_count,
    )

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
            api_key=settings.groq_api_key,
        )
        raw_phase = response.choices[0].message.content.strip().lower()

        # Phase transition logic
        for phase in Phase:
            if phase.value in raw_phase:
                old_idx = list(Phase).index(current_phase)
                new_idx = list(Phase).index(phase)
                if new_idx >= old_idx:
                    return {"phase": phase, "is_ended": phase == Phase.DEBRIEF}
    except Exception:
        pass

    return {"phase": current_phase}


def _should_continue(state: SimulationState) -> str:
    return "end" if state.get("is_ended") else "continue"


# ── The Graph Builder ────────────────────────────────────────────

def build_workflow(retriever: Retriever, checkpointer=None) -> StateGraph:
    """
    Constructs the LangGraph simulation workflow.
    Dependencies (like Retriever) are injected here.
    """
    # Bind dependencies to nodes
    patient = partial(patient_node, retriever=retriever)
    professor = partial(professor_node, retriever=retriever)

    graph = StateGraph(SimulationState)

    # Add Nodes
    graph.add_node("summarizer", summarize_conversation_node)
    graph.add_node("patient", patient)
    graph.add_node("professor", professor)
    graph.add_node("router", _router_node)

    # Define Edges
    # Entry point is summarizer. It checks length, compresses if needed, then ALWAYS goes to patient.
    graph.set_entry_point("summarizer")
    graph.add_edge("summarizer", "patient")
    graph.add_edge("patient", "professor")
    graph.add_edge("professor", "router")
    graph.add_conditional_edges(
        "router",
        _should_continue,
        {"continue": END, "end": END},
    )

    return graph.compile(checkpointer=checkpointer)
