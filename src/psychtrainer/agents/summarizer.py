"""
Summarizer Agent — Token Optimization.

This module provides a LangGraph node that monitors the conversation length.
If the conversation exceeds a certain length, it summarizes the oldest messages
to save tokens, returning a truncated message array.
"""

import logging

import litellm

from psychtrainer.config import settings
from psychtrainer.workflow.state import SimulationState

logger = logging.getLogger(__name__)

SUMMARIZER_PROMPT = """\
You are an expert clinical scribe.
Your task is to summarize the following older portion of a clinical interview \
between a student doctor (STUDENT) and a patient (PATIENT).

Create a concise, objective summary of the key clinical facts discussed below.
Focus on symptoms, history, rapport dynamics, and any clinical flags.

Previous Summary (if any):
{previous_summary}

New Messages to incorporate:
{messages_to_summarize}

Return ONLY the new, combined summary paragraph. Do not include introductory text.
"""

# Thresholds
MAX_MESSAGES = 16  # If we have more than this, we summarize
MESSAGES_TO_KEEP = 6  # How many recent messages to keep un-summarized


def summarize_conversation_node(state: SimulationState) -> dict:
    """
    Checks if the message history is too long. If so, summarizes the 
    oldest messages and truncates the active state.
    """
    messages = state["messages"]

    # Safety check: if we are under the limit, do nothing.
    if len(messages) <= MAX_MESSAGES:
        return {}

    logger.info(f"Triggering summarization. Total messages: {len(messages)}")

    split_index = len(messages) - MESSAGES_TO_KEEP
    messages_to_summarize = messages[:split_index]
    messages_to_keep = messages[split_index:]

    convo_text = "\n".join(
        f"{m.role.value.upper()}: {m.content}" for m in messages_to_summarize
    )
    
    prompt = SUMMARIZER_PROMPT.format(
        previous_summary=state.get("summary", "None"),
        messages_to_summarize=convo_text
    )

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=250,
            api_key=settings.groq_api_key,
        )
        new_summary = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Summarizer LLM error: {e}")
        return {}  # Abort compression if LLM fails

    # Return the new state update.
    # We use our custom dict flag `__replace__` to tell the reducer to OVERWRITE the array 
    # instead of appending.
    return {
        "summary": new_summary,
        "messages": {
            "__replace__": True,
            "messages": messages_to_keep
        }
    }
