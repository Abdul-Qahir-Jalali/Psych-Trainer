#!/usr/bin/env python3
"""
Data ingestion script — run once to populate Qdrant with all data sources.

Usage:
    uv run python scripts/ingest_data.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from psychtrainer.config import settings
from psychtrainer.rag.ingest import (
    get_embedding_model,
    get_qdrant_client,
    index_chunks,
    load_medqa,
    load_pdf,
)
from psychtrainer.logger_setup import setup_logger

import structlog

setup_logger()
logger = structlog.get_logger(__name__)


def main():
    logger.info("═" * 60)
    logger.info("  🧠 PsychTrainer — Component Architecture Ingestion")
    logger.info("═" * 60)

    # Shared resources
    client = get_qdrant_client()
    model = get_embedding_model()

    # ── 1. OSCE Patient Script ──
    logger.info("\n📄 Loading OSCE Patient Script...")
    osce_chunks = load_pdf(settings.osce_pdf, "patient_script")
    logger.info("   Extracted %d chunks from OSCE PDF", len(osce_chunks))
    count = index_chunks(osce_chunks, "patient_script", client=client, model=model)
    logger.info("   ✓ Indexed %d chunks into 'patient_script'", count)

    # ── 2. Depression Toolkit ──
    logger.info("\n📄 Loading Depression Screening Toolkit...")
    toolkit_chunks = load_pdf(settings.depression_toolkit_pdf, "grading_rubric")
    logger.info("   Extracted %d chunks from Toolkit PDF", len(toolkit_chunks))
    count = index_chunks(toolkit_chunks, "grading_rubric", client=client, model=model)
    logger.info("   ✓ Indexed %d chunks into 'grading_rubric'", count)

    # ── 3. MedQA Knowledge Base ──
    logger.info("\n📋 Loading MedQA JSONL...")
    medqa_chunks = load_medqa()
    logger.info("   Extracted %d chunks from MedQA", len(medqa_chunks))
    count = index_chunks(medqa_chunks, "medical_knowledge", client=client, model=model)
    logger.info("   ✓ Indexed %d chunks into 'medical_knowledge'", count)

    # ── Summary ──
    logger.info("\n" + "═" * 60)
    collections = client.get_collections().collections
    for col in collections:
        info = client.get_collection(col.name)
        logger.info("   Collection '%s': %d points", col.name, info.points_count)
    logger.info("═" * 60)
    logger.info("  ✅ Data ingestion complete!")
    logger.info("═" * 60)


if __name__ == "__main__":
    main()
