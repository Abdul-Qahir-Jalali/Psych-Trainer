import pytest
from psychtrainer.workflow.graph import _router_node
from psychtrainer.workflow.state import Phase

@pytest.mark.asyncio
async def test_router_node_early_phases():
    """
    Test that the router correctly identifies when a session should continue 
    vs when it should transition to the professor debrief.
    """
    # Test active early phase
    intro_state = {"phase": Phase.INTRODUCTION, "messages": [], "turn_count": 1}
    result = await _router_node(intro_state)
    assert result.get("phase") == Phase.INTRODUCTION, "Router should maintain early phase."

    diff_state = {"phase": Phase.EXAMINATION, "messages": [], "turn_count": 10}
    result = await _router_node(diff_state)
    assert result.get("phase") == Phase.EXAMINATION, "Router should maintain middle phase."

@pytest.mark.asyncio
async def test_router_node_debrief_transition():
    """
    Test that the router immediately cuts off the patient 
    when the Phase switches to Debrief.
    """
    debrief_state = {"phase": Phase.DEBRIEF, "messages": [], "turn_count": 25}
    result = await _router_node(debrief_state)
    assert result.get("is_ended") is True, "Router MUST flag session as ended during Debrief."

@pytest.mark.asyncio
async def test_router_node_invalid_phase():
    """
    Ensure the system defaults to the patient if the LLM outputted a hallucinated phase.
    """
    invalid_state = {"phase": "HALLUCINATED_PHASE", "messages": [], "turn_count": 1}
    result = await _router_node(invalid_state)
    assert result.get("phase") == "HALLUCINATED_PHASE", "Router preserves state if conditions not met."
