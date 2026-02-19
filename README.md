# 🧠 PsychTrainer

**Industrial AI Clinical Simulation Platform**

Train medical students in psychiatric diagnosis by interviewing an AI patient (James, 21, presenting with OCD) while a silent AI professor grades your clinical skills in real-time.

## ⚡ Tech Stack

| Layer           | Tool                  | Why                               |
| --------------- | --------------------- | --------------------------------- |
| Package Manager | `uv`                  | 10-100x faster than pip           |
| Orchestration   | LangGraph             | Stateful multi-agent workflows    |
| LLM Interface   | LiteLLM               | Swap models without code changes  |
| Vector DB       | Qdrant (local)        | Rust-based, zero Docker needed    |
| Backend         | FastAPI + Pydantic v2 | Async, validated, auto-documented |
| Embeddings      | sentence-transformers | Free, local, no API key           |
| LLM Provider    | Groq (free tier)      | Llama 3.3 70B at blazing speed    |

## 🚀 Quick Start

```bash
# 1. Set your Groq API key in .env
#    Edit .env and replace 'paste_your_groq_api_key_here'

# 2. Ingest data into vector database
uv run python scripts/ingest_data.py

# 3. Start the server
uv run uvicorn src.psychtrainer.api.main:app --reload --host 0.0.0.0 --port 8000

# 4. Open browser
#    http://localhost:8000
```

## 🏗️ Architecture

```
Student ──► FastAPI ──► LangGraph Workflow
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
           Patient      Professor    Router
           Agent        Agent        (Phase)
                │           │
                ▼           ▼
            Qdrant RAG   Qdrant RAG
           (OSCE PDF)   (Toolkit PDF)
                │
                ▼
            MedQA KB
```

## 📁 Project Structure

```
src/psychtrainer/
├── config.py          # Centralized settings from .env
├── models.py          # Pydantic v2 schemas
├── ingest/            # Data loading & embedding pipeline
├── agents/            # Patient + Professor agent logic
├── graph/             # LangGraph workflow orchestration
├── rag/               # Qdrant semantic retrieval
└── api/               # FastAPI routes + WebSocket
frontend/              # Dark-mode chat UI
scripts/               # Data ingestion CLI
data/                  # Source PDFs, JSONL, CSV
```

## 📋 Grading Criteria (7 dimensions)

1. **Rapport Building** — Empathy, open questions, active listening
2. **History Taking** — Onset, duration, severity, triggers
3. **Risk Assessment** — ⚠️ Suicidal ideation, substance use, impairment
4. **Mental State Exam** — Appearance, mood, thought content
5. **Clinical Reasoning** — Differential diagnosis, explanation
6. **Communication** — Patient-friendly language, summarization
7. **Professionalism** — Respectful, non-judgmental, boundaries

## 📜 License

Open source — free for educational use.
