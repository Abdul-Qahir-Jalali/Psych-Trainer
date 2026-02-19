"""
Persistence Layer — Managing simulation state checkpoints.

Uses LangGraph's SqliteSaver to persist conversation history to disk.
This ensures sessions survive server restarts.
"""

import sqlite3
from contextlib import contextmanager

from langgraph.checkpoint.sqlite import SqliteSaver

from psychtrainer.config import settings


@contextmanager
def get_checkpointer():
    """
    Yields a SqliteSaver instance connected to the database.
    Use this context manager to ensure the connection is closed properly.
    """
    # Database path
    db_path = settings.PROJECT_ROOT / "psychtrainer.db"
    
    # Establish connection
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    try:
        # Initialize checkpointer
        checkpointer = SqliteSaver(conn)
        yield checkpointer
    finally:
        conn.close()
