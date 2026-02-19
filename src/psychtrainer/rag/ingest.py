"""
Data Ingestion Logic — PDF Loaders, Chunking, and Embedding.

This module handles:
1. Loading raw data (PDFs, JSONL, CSVs).
2. Splitting text into manageable chunks.
3. Generating embeddings via SentenceTransformers.
4. Indexing vectors into Qdrant.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from qdrant_client import QdrantClient, models as qdrant_models
from sentence_transformers import SentenceTransformer

from psychtrainer.config import settings

logger = logging.getLogger(__name__)


# ── Internal Type ────────────────────────────────────────────────

@dataclass
class TextChunk:
    """A single chunk of text with source metadata."""
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ── PDF & Text Processing ────────────────────────────────────────

def _split_text(
    text: str,
    chunk_size: int = settings.chunk_size,
    overlap: int = settings.chunk_overlap,
) -> list[str]:
    """Split text into overlapping chunks."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


def load_pdf(pdf_path: str, collection_name: str) -> list[TextChunk]:
    """Extract and chunk text from a PDF file."""
    reader = PdfReader(pdf_path)
    chunks: list[TextChunk] = []

    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue

        for idx, chunk_text in enumerate(_split_text(page_text)):
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    metadata={
                        "source": Path(pdf_path).name,
                        "collection": collection_name,
                        "page": page_num,
                        "chunk_index": idx,
                    },
                )
            )
    return chunks


def load_medqa() -> list[TextChunk]:
    """Load Q&A pairs from MedQA JSONL."""
    chunks: list[TextChunk] = []
    path = Path(settings.medqa_jsonl)

    if not path.exists():
        logger.warning(f"MedQA file missing: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            try:
                data = json.loads(line)
                text = (
                    f"Question: {data.get('question','')}\n"
                    f"Options: {data.get('options',{})}\n"
                    f"Answer: {data.get('answer','')}"
                )
                chunks.append(
                    TextChunk(
                        text=text,
                        metadata={
                            "source": "medqa",
                            "collection": "medical_knowledge",
                            "index": idx,
                        },
                    )
                )
            except json.JSONDecodeError:
                continue
    return chunks


def load_few_shot_examples() -> str:
    """Load example dialogues from CSVs into a single prompt string."""
    path = Path(settings.csv_data_dir)
    examples: list[str] = []

    if not path.exists():
        return ""

    for csv_file in path.glob("*.csv"):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                p_in = row.get("patient_input")
                s_resp = row.get("student_response")
                if p_in and s_resp:
                    examples.append(f"Student: {s_resp}\nPatient: {p_in}")

    return "\n\n".join(examples)


# ── Embedding & Indexing ─────────────────────────────────────────

_model: SentenceTransformer | None = None
_client: QdrantClient | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=settings.qdrant_path)
    return _client


def index_chunks(
    chunks: list[TextChunk],
    collection_name: str,
    client: QdrantClient,
    model: SentenceTransformer,
) -> int:
    """Embed chunks and upsert them into Qdrant."""
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=model.get_sentence_embedding_dimension(),
                distance=qdrant_models.Distance.COSINE,
            ),
        )

    points: list[qdrant_models.PointStruct] = []
    texts = [c.text for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)

    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        points.append(
            qdrant_models.PointStruct(
                id=i,
                vector=vector.tolist(),
                payload={"text": chunk.text, **chunk.metadata},
            )
        )

    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=collection_name,
            points=points[i : i + batch_size],
        )

    return len(points)
