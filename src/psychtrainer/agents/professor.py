"""
Professor Agent — Grading Logic and Rubric.

This module defines "Dr. Williams", the invisible evaluator.
It analyzes student messages against clinical criteria and generates
a final report, but never speaks to the user.
"""

from __future__ import annotations

import json
import logging

import litellm

from psychtrainer.config import settings
from psychtrainer.rag.knowledge import Retriever
from psychtrainer.workflow.state import GradeReport, MessageRole, SimulationState

logger = logging.getLogger(__name__)


# ── The Prompt (Co-located for easy editing) ─────────────────────

PROFESSOR_SYSTEM_PROMPT = """\
You are **Dr. Williams**, a senior psychiatry professor observing a student's \
clinical interview from behind a one-way mirror. You do NOT interact with the \
patient — you only evaluate the student's performance.

═══════════════════════════════════════════════════
  YOUR TASK
═══════════════════════════════════════════════════

Analyse the student's LATEST message in the context of the full conversation. \
Write a brief internal note (1-3 sentences) assessing their clinical skill. \
Your notes accumulate silently and are used for the final grade report.

═══════════════════════════════════════════════════
  GRADING CRITERIA (from Clinical Guidelines)
═══════════════════════════════════════════════════

Score each of these areas on a 0-10 scale:

1. **Rapport Building** (10pts)
   - Did they introduce themselves?
   - Did they use open-ended questions?
   - Did they show empathy and active listening?

2. **History Taking** (10pts)
   - Did they explore onset, duration, severity?
   - Did they ask about triggers and relieving factors?
   - Did they cover all symptom domains?

3. **Risk Assessment** (10pts)
   - ⚠️ CRITICAL: Did they ask about suicidal ideation/self-harm?
   - Did they assess substance use?
   - Did they ask about functional impairment?

4. **Mental State Examination** (10pts)
   - Did they assess appearance, behaviour, speech, mood, affect?
   - Did they evaluate thought content and perceptual abnormalities?

5. **Clinical Reasoning** (10pts)
   - Did they form a differential diagnosis?
   - Did they explain the diagnosis clearly to the patient?
   - Did they discuss treatment options appropriately?

6. **Communication Skills** (10pts)
   - Did they use patient-friendly language (no excessive jargon)?
   - Did they summarise and check understanding?
   - Did they respect the patient's autonomy?

7. **Professionalism** (10pts)
   - Were they respectful and non-judgmental?
   - Did they maintain appropriate boundaries?

═══════════════════════════════════════════════════
  CLINICAL GUIDELINES CONTEXT
═══════════════════════════════════════════════════

{grading_criteria}

═══════════════════════════════════════════════════
  PREVIOUS CONVERSATION MEMORY (If long session)
═══════════════════════════════════════════════════

{summary}

═══════════════════════════════════════════════════
  INSTRUCTIONS
═══════════════════════════════════════════════════

For each student message, output ONLY a brief note like:
"[+] Good open-ended question exploring symptom duration. Rapport: building well."
or
"[-] Missed opportunity to assess suicide risk. This is a critical gap."
or
"[~] Adequate question but used jargon ('intrusive thoughts') without checking understanding."

Be precise. Be fair. A student who asks about suicide risk should get significant credit. \
A student who never asks should be penalized heavily in the final report.
"""


GRADING_FINAL_PROMPT = """\
You are Dr. Williams. The clinical interview has ended. Based on your accumulated \
observation notes, produce a FINAL GRADE REPORT.

Your observation notes:
{professor_notes}

The full conversation transcript:
{transcript}

Produce a JSON object with this EXACT structure:
{{
  "overall_score": <0-100>,
  "letter_grade": "<A/B/C/D/F>",
  "summary": "<2-3 sentence overall assessment>",
  "criteria": [
    {{
      "criterion": "<name>",
      "score": <0-10>,
      "feedback": "<specific feedback>"
    }}
  ],
  "strengths": ["<strength 1>", "<strength 2>"],
  "improvements": ["<improvement 1>", "<improvement 2>"]
}}

The criteria MUST include: Rapport Building, History Taking, Risk Assessment, \
Mental State Examination, Clinical Reasoning, Communication Skills, Professionalism.

Be rigorous but fair. Output ONLY valid JSON, no markdown fences.
"""


# ── The Agent Logic ──────────────────────────────────────────────

def professor_node(state: SimulationState, retriever: Retriever) -> dict:
    """
    Evaluates the student's latest message.
    """
    if len(state["messages"]) < 2:
        return {}

    student_msg = state["messages"][-2]
    if student_msg.role != MessageRole.STUDENT:
        return {}

    # Retrieve Rubric
    try:
        criteria = retriever.get_grading_criteria(student_msg.content)
    except Exception as e:
        logger.error(f"Retriever error (Professor): {e}")
        criteria = ""

    prompt = PROFESSOR_SYSTEM_PROMPT.format(
        grading_criteria=criteria,
        summary=state.get("summary", "None available yet.")
    )
    conversation_text = "\n".join(
        f"{m.role.value.upper()}: {m.content}" for m in state["messages"]
    )
    full_prompt = (
        f"{prompt}\n\nFULL CONVERSATION:\n{conversation_text}\n\n"
        "Generate your observation note now:"
    )

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.2,
            max_tokens=100,
            api_key=settings.groq_api_key,
        )
        note = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Professor LLM error: {e}")
        note = "[System: Evaluation failed]"

    return {
        "professor_notes": [note],
        "grading_criteria": criteria,
    }


def generate_final_grade(state: SimulationState) -> GradeReport:
    """
    Compiles all session notes into a final JSON report card.
    """
    notes = "\n".join(f"- {n}" for n in state.get("professor_notes", []))
    transcript = "\n".join(
        f"{m.role.value.upper()}: {m.content}" for m in state["messages"]
    )

    prompt = GRADING_FINAL_PROMPT.format(
        professor_notes=notes,
        transcript=transcript,
    )

    try:
        response = litellm.completion(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
            api_key=settings.groq_api_key,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return GradeReport(**data)

    except Exception as e:
        logger.error(f"Grading error: {e}")
        return GradeReport(
            overall_score=0,
            letter_grade="F",
            summary="Grading failed due to technical error.",
        )
