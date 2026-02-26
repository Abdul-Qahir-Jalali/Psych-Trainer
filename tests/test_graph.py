import pytest
from psychtrainer.workflow.graph import _router_node
from psychtrainer.workflow.state import Phase

def test_router_node_early_phases():
    """
    Test that the router correctly identifies when a session should continue 
    vs when it should transition to the professor debrief.
    """
    # Test active early phase
    intro_state = {"phase": Phase.INTRODUCTION, "messages": [], "turn_count": 1}
    result = _router_node(intro_state)
    assert result == "patient", "Router should direct early phases to the patient agent."

    diff_state = {"phase": Phase.DIFFERENTIAL_DIAGNOSIS, "messages": [], "turn_count": 10}
    result = _router_node(diff_state)
    assert result == "patient", "Router should direct middle phases to the patient agent."

def test_router_node_debrief_transition():
    """
    Test that the router immediately cuts off the patient 
    when the Phase switches to Debrief.
    """
    debrief_state = {"phase": Phase.DEBRIEF, "messages": [], "turn_count": 25}
    result = _router_node(debrief_state)
    assert result == "professor", "Router MUST direct Debrief phase to the grading professor."

def test_router_node_invalid_phase():
    """
    Ensure the system defaults to the patient if the LLM outputted a hallucinated phase.
    """
    invalid_state = {"phase": "HALLUCINATED_PHASE", "messages": [], "turn_count": 1}
    result = _router_node(invalid_state)
    assert result == "patient", "Router must default to patient if phase is invalid to prevent graph crashing."
