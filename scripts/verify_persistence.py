"""
Persistence Verification Script.

Proves that conversation state survives a "server restart" by:
1. Creating a workflow & database connection.
2. Running Turn 1 (saving state).
3. Closing the connection (destroying workflow object).
4. Opening a NEW connection to the SAME database.
5. Creating a NEW workflow object.
6. Retrieving the state to verify history is preserved.
"""

import sqlite3
import uuid
import sys
from pathlib import Path

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from langgraph.checkpoint.sqlite import SqliteSaver
from psychtrainer.workflow.graph import build_workflow
from psychtrainer.workflow.state import Phase
from psychtrainer.rag.knowledge import Retriever

DB_PATH = "verify_persistence.db"
SESSION_ID = "test_persistence_" + uuid.uuid4().hex[:8]


def run_first_session():
    print(f"\n--- [SESSION 1] Starting Session {SESSION_ID} ---")
    
    # 1. Open DB
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    
    # 2. Build Graph
    # We use a dummy retriever since we only care about state mechanics here
    # (mocking it avoids loading heavy models)
    class MockRetriever:
        def get_patient_context(self, *args): return "Context"
        def get_grading_criteria(self, *args): return "Criteria"
        def get_medical_context(self, *args): return "Medical Context"

    workflow = build_workflow(MockRetriever(), checkpointer=checkpointer)
    
    # 3. Initialize State
    config = {"configurable": {"thread_id": SESSION_ID}}
    initial_state = {
        "session_id": SESSION_ID,
        "phase": Phase.INTRODUCTION,
        "messages": [],
        "professor_notes": [],
        "turn_count": 0,
        "patient_context": "",
        "grading_criteria": "",
        "medical_context": "",
        "few_shot_examples": "",
        "is_ended": False,
        "grade_report": None,
    }
    
    print("Saving Initial State...")
    workflow.update_state(config, initial_state)
    
    # 4. Verify Turn Count 0
    state_0 = workflow.get_state(config).values
    print(f"Turn Count: {state_0['turn_count']}")
    
    # 5. Simulate One Turn (Update State manually to mock graph execution)
    # Since we mocked retriever, graph execution might fail on heavy logic if not careful.
    # But update_state works regardless.
    print("Updating State (Simulating Chat)...")
    workflow.update_state(config, {"turn_count": 1, "messages": [{"role": "student", "content": "Hello", "metadata": {}}]})
    
    conn.close()
    print("--- [SESSION 1] Database Closed (Server Stop) ---\n")


def run_second_session():
    print(f"--- [SESSION 2] Restarting with Session {SESSION_ID} ---")
    
    # 1. Open NEW Connection
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    
    class MockRetriever: pass
    workflow = build_workflow(MockRetriever(), checkpointer=checkpointer)
    
    # 2. Retrieve State
    config = {"configurable": {"thread_id": SESSION_ID}}
    snapshot = workflow.get_state(config)
    
    if not snapshot.values:
        print("❌ FAILED: State not found!")
        return

    # 3. Check Data
    turn = snapshot.values.get("turn_count")
    msgs = snapshot.values.get("messages", [])
    
    print(f"Recovered Turn Count: {turn}")
    print(f"Recovered Message Count: {len(msgs)}")
    
    if turn == 1 and len(msgs) == 1:
        print("\n[SUCCESS]: Persistence Verified! State was recovered correctly.")
    else:
        print(f"\n[FAILED]: Expected turn 1, got {turn}")

    conn.close()
    
    # Cleanup
    Path(DB_PATH).unlink(missing_ok=True)


if __name__ == "__main__":
    run_first_session()
    run_second_session()
