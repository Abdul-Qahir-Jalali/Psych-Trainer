"""
Centralized configuration loaded from .env via Pydantic Settings.

All settings are validated at startup — if a required key is missing,
the app fails fast with a clear error message.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is two levels up from this file (src/psychtrainer/config.py → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    """Application-wide settings sourced from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # ── Path Utils ───────────────────────────────────────
    PROJECT_ROOT: Path = PROJECT_ROOT

    # ── LLM ──────────────────────────────────────────────
    groq_api_key: str = ""
    llm_model: str = "groq/llama-3.3-70b-versatile"

    # ── Embeddings ───────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384  # MiniLM-L6-v2 output dim

    # ── Qdrant ───────────────────────────────────────────
    qdrant_path: str = str(PROJECT_ROOT / "qdrant_storage")

    # ── Data Files ───────────────────────────────────────
    osce_pdf: str = str(DATA_DIR / "September-2017-OSCE-Station-10.pdf")
    depression_toolkit_pdf: str = str(
        DATA_DIR / "Adolescent-Depression-Screening-and-Initial-Treatment-Toolkit.pdf"
    )
    medqa_jsonl: str = str(DATA_DIR / "agentclinic_medqa.jsonl")
    interview_csv: str = str(DATA_DIR / "Interview_Data_6K.csv")
    csv_data_dir: Path = DATA_DIR

    # ── Server ───────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── RAG ──────────────────────────────────────────────
    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k: int = 5


# Singleton — import `settings` from anywhere
settings = Settings()
