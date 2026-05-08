# PsychTrainer — Full Tech Stack Explained

> This document explains every single framework, library, and tool used in this project — what it is, why we use it, and where it shows up in the code. Written in simple English so anyone can understand.

---

## What Is This Project?

**PsychTrainer** is an AI-powered clinical simulation platform for medical students. It simulates a real psychiatric patient ("James") that students can interview. An invisible AI professor watches the conversation and grades the student at the end. The whole thing runs in a browser and is powered by a Python backend and AI models.

---

## 📦 PROJECT STRUCTURE OVERVIEW

```
PsychTrainer/
├── src/psychtrainer/        ← Python Backend (the brain)
│   ├── agents/              ← AI agents (Patient, Professor, Summarizer)
│   ├── rag/                 ← Knowledge retrieval system
│   ├── service/             ← API server + WebSocket + Background worker
│   └── workflow/            ← LangGraph state machine
├── frontend-react/          ← React frontend (the face)
├── frontend/                ← Old HTML/JS frontend (still served as fallback)
├── docker-compose.yml       ← Runs everything together
└── pyproject.toml           ← Python dependencies list
```

---

## 🐍 BACKEND TECHNOLOGIES (Python)

---

### 1. FastAPI
**What it is:** A modern Python web framework for building APIs (Application Programming Interfaces — the way the frontend talks to the backend).

**Why we use it:** It is very fast, supports async (doing multiple things at once without waiting), and automatically creates a documentation page at `/docs` so you can test all API routes in your browser. It is the "front door" of our backend.

**Where it is used:** `src/psychtrainer/service/api.py` — This is the main file. All routes like `/api/session/start`, `/api/session/chat`, `/api/session/end` are defined here.

**Example:**
```python
@app.post("/api/session/chat")
async def chat(request: ChatRequest):
    # This runs when the frontend sends a student message
```

---

### 2. Uvicorn
**What it is:** A super-fast web server for Python. FastAPI needs a server to actually listen for requests — Uvicorn is that server.

**Why we use it:** It supports `async` Python natively, which is needed for streaming AI responses in real-time.

**Where it is used:** The app is started with:
```
uvicorn src.psychtrainer.service.api:app --host 0.0.0.0 --port 8000
```
This is also in the `Dockerfile` as the final `CMD`.

---

### 3. LangGraph
**What it is:** A framework for building "stateful" AI workflows as a graph (a flowchart of steps). Each step is called a **node** and they are connected by **edges**.

**Why we use it:** Our simulation has multiple AI agents that must run in a specific order: Summarizer → Patient → Professor → Router. LangGraph manages this pipeline AND automatically saves the state (the conversation) to a database after every step, so if the server restarts, the session is not lost.

**Where it is used:** `src/psychtrainer/workflow/graph.py`

```
Summarizer Node → Patient Node → Professor Node → Router Node → END
```

The whole graph is built with `StateGraph(SimulationState)` and compiled with a `checkpointer` (database saver).

---

### 4. LangGraph Checkpoint (Postgres + SQLite)
**What it is:** A plugin for LangGraph that saves the entire conversation state to a database automatically.

**Why we use it:** Without this, if the server crashes or the student refreshes the page, the entire conversation is lost. The checkpoint saves every single state update to PostgreSQL. The student can come back hours later and resume from exactly where they left off.

**Libraries:**
- `langgraph-checkpoint-postgres` — saves to PostgreSQL (production)
- `langgraph-checkpoint-sqlite` — saves to a local `.db` file (development/testing)

**Where it is used:** `src/psychtrainer/service/api.py` and `worker.py`:
```python
checkpointer = AsyncPostgresSaver(pool)
await checkpointer.setup()  # Creates all LangGraph tables in Postgres
workflow = build_workflow(retriever, checkpointer=checkpointer)
```

---

### 5. LiteLLM
**What it is:** A universal library that lets you call ANY AI model (Groq, OpenAI, Cohere, Gemini, Anthropic, etc.) using the same simple code. You just change the model name string.

**Why we use it:** We want to be flexible. Today we use Groq's Llama model. Tomorrow we might switch to OpenAI GPT-4. With LiteLLM, we change one line in the config file — nothing else changes. It also integrates with LangSmith for tracking.

**Where it is used:**
- `src/psychtrainer/workflow/graph.py` — Router node
- `src/psychtrainer/agents/professor.py` — Professor grading
- `src/psychtrainer/agents/summarizer.py` — Conversation summarization
- `src/psychtrainer/rag/cloud_inference.py` — Cloud embeddings

**Primary model used:** `groq/llama-3.3-70b-versatile`

---

### 6. LangChain + LangChain Community
**What it is:** A large framework for building LLM-powered apps. Provides useful classes like `HumanMessage`, `AIMessage`, `SystemMessage` for structuring conversations, and `ChatLiteLLM` for connecting to models through LiteLLM.

**Why we use it:** Our Patient agent builds a structured conversation history using LangChain message types, which is the standard format that all LLM APIs understand.

**Where it is used:** `src/psychtrainer/agents/patient.py`
```python
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
```

---

### 7. LangSmith
**What it is:** An observability platform by the LangChain team. It records every LLM call — what prompt was sent, what response came back, how many tokens were used, and how long it took.

**Why we use it:** So we can debug the AI's behavior. If the patient agent gives a strange response, we can go to the LangSmith dashboard and see the exact prompt that was sent to the model.

**Where it is used:** `src/psychtrainer/service/api.py` (startup):
```python
litellm.success_callback = ["langsmith"]
litellm.failure_callback = ["langsmith"]
```
Enabled only when `LANGCHAIN_TRACING_V2=true` is set in the `.env` file.

---

### 8. Pydantic
**What it is:** A Python library for data validation. You define what shape your data must have (e.g., "this must be a string, this must be a number between 0 and 100"), and Pydantic enforces it automatically.

**Why we use it:** Prevents bugs. If the AI returns a grade of `"abc"` instead of a number, Pydantic catches it immediately and raises a clear error. All our data models (`ChatMessage`, `GradeReport`, `CriterionScore`) use Pydantic.

**Where it is used:** `src/psychtrainer/workflow/state.py`
```python
class GradeReport(BaseModel):
    overall_score: float = Field(ge=0, le=100)  # Must be between 0 and 100
    letter_grade: str
```

---

### 9. Pydantic-Settings
**What it is:** An extension of Pydantic that reads configuration values from environment variables and `.env` files.

**Why we use it:** We never hardcode API keys in the code. Instead they live in a `.env` file. Pydantic-Settings reads that file at startup and validates that all required settings are present.

**Where it is used:** `src/psychtrainer/config.py`
```python
class Settings(BaseSettings):
    groq_api_key: str = ""
    supabase_url: str = ""
    # ... all other config
```

---

### 10. Psycopg (v3) + Psycopg-Pool
**What it is:** The official Python driver for connecting to PostgreSQL databases. `psycopg` is the base connector; `psycopg-pool` manages a "pool" of database connections (a group that gets reused instead of opening a new connection for every request).

**Why we use it:** Our app handles many users at once. Opening a new database connection for every request would be very slow. The pool keeps connections open and ready, making the app much faster.

**Where it is used:** `src/psychtrainer/service/api.py`:
```python
pool = AsyncConnectionPool(conninfo=settings.postgres_uri, kwargs={"autocommit": True})
await pool.open()
```
Also used in `pg_knowledge.py` for vector search queries.

---

### 11. PGVector
**What it is:** A PostgreSQL extension that adds the ability to store and search **vectors** (lists of numbers that represent the meaning of text). `pgvector` is the Python library that lets us use this from Python.

**Why we use it:** All medical knowledge (PDFs, exam scripts) is converted into vectors and stored in PostgreSQL. When a student asks a question, we convert the question to a vector and find the most similar stored knowledge. This is called **vector search** or **semantic search**.

**Where it is used:** `src/psychtrainer/rag/pg_knowledge.py`:
```python
# This SQL uses the <=> operator which is pgvector's cosine distance
SELECT text FROM document_embeddings ORDER BY embedding <=> %s::vector LIMIT 20
```
The Docker image `pgvector/pgvector:pg15` includes this extension pre-installed.

---

### 12. Qdrant + Qdrant-Client
**What it is:** Qdrant is a dedicated **vector database** — a database built specifically for storing and searching vectors. Unlike PGVector (which adds vector search to PostgreSQL), Qdrant is purpose-built for it.

**Why we use it:** It is an alternative vector store to PGVector. The project supports both. Qdrant runs locally on disk (no internet needed) and supports **hybrid search** (combining keyword search + semantic search in one query).

**Where it is used:** `src/psychtrainer/rag/ingest.py` and `rag/knowledge.py`. The local storage is in the `qdrant_storage/` folder.

Config switch: `VECTOR_STORE=qdrant` in `.env` uses Qdrant; `VECTOR_STORE=pgvector` uses PostgreSQL.

---

### 13. FastEmbed
**What it is:** A lightweight, fast library for converting text into vectors (embeddings) that runs **locally on your CPU** — no internet or API needed.

**Why we use it:** As a fallback when cloud API keys (Cohere, Gemini) are not available. It uses the `all-MiniLM-L6-v2` model which produces 384-dimensional vectors.

**Models used:**
- `TextEmbedding` — converts text to dense vectors
- `SparseTextEmbedding` with `Qdrant/bm25` — converts text to sparse vectors (keyword-based)

**Where it is used:** `src/psychtrainer/rag/ingest.py`, `rag/knowledge.py`, `rag/cloud_inference.py`

---

### 14. Sentence-Transformers
**What it is:** A Python library for advanced NLP (Natural Language Processing) models. We specifically use its **CrossEncoder** for re-ranking search results.

**Why we use it:** After vector search returns 20 candidate results, we use a CrossEncoder model to score each result again against the query and pick only the top 3 most relevant ones. This dramatically improves the quality of the context given to the AI.

**Model used:** `cross-encoder/ms-marco-MiniLM-L-6-v2`

**Where it is used:** `src/psychtrainer/rag/knowledge.py`:
```python
self.cross_encoder = CrossEncoder(settings.cross_encoder_model)
scores = self.cross_encoder.predict(pairs)  # Score each (query, chunk) pair
```

---

### 15. PyTorch (torch, torchvision, torchaudio)
**What it is:** The most popular deep learning framework in the world, made by Meta. It is the mathematical engine that makes neural networks (AI models) run.

**Why we use it:** `sentence-transformers` and `fastembed` both require PyTorch under the hood to run their models. We don't use PyTorch directly — it is a required dependency.

**Important note:** We use the **CPU-only version** to save 4GB of disk space (since we don't need a GPU for this project). This is configured in `pyproject.toml` with a custom PyTorch index:
```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu/"
```

---

### 16. PyPDF
**What it is:** A Python library for reading PDF files and extracting their text content.

**Why we use it:** Our knowledge base includes real medical PDFs (OSCE exam scripts, depression toolkits). We read these PDFs, extract the text, split it into chunks, and store them in the vector database.

**Where it is used:** `src/psychtrainer/rag/ingest.py`:
```python
from pypdf import PdfReader
reader = PdfReader(pdf_path)
for page in reader.pages:
    page_text = page.extract_text()
```

---

### 17. Supabase (Python Client)
**What it is:** Supabase is a cloud database platform (like Firebase but open source). It provides a hosted PostgreSQL database, user authentication, and a simple API for reading/writing data.

**Why we use it for two purposes:**

1. **Authentication:** Students log in via Supabase Auth (email/password or OAuth). When they make API calls, they send a JWT token. The backend verifies this token with Supabase to confirm who the user is.

2. **UI Data (sessions table):** We keep a fast, lightweight `sessions` table in Supabase that stores session titles and statuses. This is much faster than querying the full LangGraph checkpoint database just to show a sidebar list.

3. **Prompt Registry:** The AI system prompts (the Patient's persona, the Professor's grading instructions) are stored in a Supabase `system_prompts` table. This means we can update the AI's behavior without redeploying the server.

**Where it is used:** `src/psychtrainer/workflow/prompt_registry.py`, `service/api.py`

---

### 18. PyJWT
**What it is:** A Python library for creating and verifying JWT (JSON Web Tokens) — secure tokens used for authentication.

**Why we use it:** When a student logs in, Supabase gives them a JWT. Every API request includes this token. Our backend uses PyJWT to verify the token's signature and extract the user's ID.

**Where it is used:** `src/psychtrainer/service/api.py`:
```python
import jwt
# Validates the Supabase JWT
user_resp = supabase.auth.get_user(credentials.credentials)
```

---

### 19. Redis (redis-py)
**What it is:** Redis is an extremely fast in-memory database, commonly used as a **cache** (temporary storage) and **message queue**.

**Why we use it for two purposes:**

1. **Prompt Cache:** System prompts are fetched from Supabase and cached in Redis for 12 hours. So instead of hitting the database on every single AI call (thousands of times per session), we read from Redis (which is instant).

2. **Background Job Queue:** When a new session starts, we need to generate a title for it using the AI. We don't want to make the user wait — so we put this task into a Redis queue and a background worker picks it up later.

**Where it is used:** `src/psychtrainer/workflow/prompt_registry.py` (caching), `service/api.py` (ARQ queue), `docker-compose.yml` (runs Redis 7.2 as a Docker service).

---

### 20. ARQ
**What it is:** An async background job queue for Python that uses Redis as its message broker. "ARQ" stands for Async Redis Queue.

**Why we use it:** Some tasks should not block the main API response. The best example is generating a session title — it requires an LLM call (which takes 1-2 seconds). We enqueue this task to ARQ, immediately return the chat response to the user, and the title gets generated in the background by a separate worker process.

**Where it is used:**
- `src/psychtrainer/service/api.py` — enqueues jobs:
  ```python
  await app.state.arq_pool.enqueue_job("generate_title_task", session_id, ...)
  ```
- `src/psychtrainer/service/worker.py` — defines and runs the job:
  ```python
  class WorkerSettings:
      functions = [generate_title_task]
      max_tries = 3  # Retries 3 times if it fails
  ```

---

### 21. SlowAPI
**What it is:** A rate-limiting library for FastAPI. It lets you set rules like "this endpoint can only be called 20 times per minute from one IP address."

**Why we use it:** Prevents abuse. Without rate limiting, one person could send thousands of messages per second and crash the server or rack up huge AI API bills.

**Where it is used:** `src/psychtrainer/service/api.py`:
```python
limiter = Limiter(key_func=get_remote_address)

@app.post("/api/session/stream_chat")
@limiter.limit("20/minute")
async def stream_chat(...):
```

---

### 22. Tenacity
**What it is:** A retry library. You add a decorator to any function, and if it fails (raises an exception), Tenacity automatically retries it with configurable delays.

**Why we use it:** AI APIs (like Groq) can occasionally fail or be temporarily overloaded. Instead of showing the user an error, we retry the call up to 3 times with exponentially increasing delays (2s, 4s, 8s).

**Where it is used:** `src/psychtrainer/agents/patient.py`:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
async def _invoke_llm_with_retry(llm, lc_messages, config):
    return await llm.ainvoke(lc_messages, config)
```

---

### 23. Structlog
**What it is:** A structured logging library. Instead of printing simple text like `"Error occurred"`, it outputs organized, machine-readable log data with timestamps, levels, and context.

**Why we use it:** In production, all logs are output as JSON so they can be ingested by logging platforms. In development, logs are colorized and readable in the terminal. All log calls look like:
```python
logger.info("title_generated", session_id=session_id, title=title)
```
This is far easier to search and filter than plain text logs.

**Where it is used:** Every Python module — `api.py`, `worker.py`, `knowledge.py`, all agents. The setup is in `src/psychtrainer/logger_setup.py`.

---

### 24. HTTPX
**What it is:** A modern async HTTP client for Python (like the `requests` library but supports async).

**Why we use it:** Used to make HTTP calls to the Cohere Reranking API (`/v1/rerank`). The standard `requests` library is synchronous (blocking), but our app is async, so we need `httpx` with `async with httpx.AsyncClient()`.

**Where it is used:** `src/psychtrainer/rag/cloud_inference.py`:
```python
async with httpx.AsyncClient() as client:
    res = await client.post("https://api.cohere.com/v1/rerank", ...)
```

---

### 25. Python-Dotenv
**What it is:** Reads key=value pairs from a `.env` file and makes them available as environment variables in Python.

**Why we use it:** We load the `.env` file at startup so that external libraries (LiteLLM, LangSmith) that read environment variables directly can find the API keys they need.

**Where it is used:** `src/psychtrainer/config.py`:
```python
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
```

---

## ⚛️ FRONTEND TECHNOLOGIES (React)

---

### 26. React 19
**What it is:** The most popular JavaScript library for building user interfaces. Made by Meta. You build the UI as small reusable pieces called **components**.

**Why we use it:** The chat interface has multiple complex parts (sidebar, chat window, grade report, login screen) that need to update dynamically as data changes. React makes managing this complexity much easier.

**Where it is used:** `frontend-react/src/` — The entire frontend is a React app. `App.tsx` is the root component.

---

### 27. TypeScript
**What it is:** A superset of JavaScript that adds **type safety** — you declare what type of data each variable holds, and TypeScript catches mistakes before the code runs.

**Why we use it:** Prevents bugs. For example, if a function expects a `string` but you accidentally pass a `number`, TypeScript gives you an error immediately in the editor rather than silently breaking at runtime.

**Where it is used:** All frontend files use `.tsx` (TypeScript + React JSX) extension.

---

### 28. Vite
**What it is:** A modern frontend build tool that compiles TypeScript/React code into optimized JavaScript files that browsers can run.

**Why we use it:** It is extremely fast — the development server starts in under a second and hot-reloads (updates the browser instantly) when you change a file. It is the replacement for older tools like Webpack.

**Where it is used:** `frontend-react/vite.config.js`. Development runs with `npm run dev`. Production build with `npm run build` (used in Docker).

---

### 29. Zustand
**What it is:** A tiny, simple state management library for React. "State" means data that the app needs to remember and share between components (e.g., the current session ID, the list of messages, whether the user is logged in).

**Why we use it:** React's built-in state (`useState`) only works within one component. Zustand creates a **global store** that any component can read from or write to. It is much simpler than alternatives like Redux.

**Where it is used:** `frontend-react/src/store/useStore.ts` — The entire app state (messages, sessions, auth, phase, grading report) is managed in one Zustand store.

---

### 30. Supabase JS Client (`@supabase/supabase-js`)
**What it is:** The official JavaScript SDK for Supabase — handles login, logout, token management, and database queries from the browser.

**Why we use it:** The frontend needs to log the student in and get a JWT token to send with every API request. Supabase JS handles the entire auth flow (login forms, session persistence in local storage, token refresh).

**Where it is used:** `frontend-react/src/lib/supabase.ts` and `App.tsx`.

---

### 31. `@microsoft/fetch-event-source`
**What it is:** A JavaScript library for consuming **Server-Sent Events (SSE)** — a protocol where the server pushes data to the browser in real-time as a stream.

**Why we use it:** When the AI patient is generating a response, we want to show the text appear word by word (like ChatGPT typing). The browser's built-in `EventSource` API doesn't support sending custom headers (like our auth token). This library fixes that problem by supporting headers with SSE.

**Where it is used:** `frontend-react/src/App.tsx` — the streaming chat logic:
```javascript
fetchEventSource("/api/session/stream_chat", {
  headers: { Authorization: `Bearer ${token}` },
  onmessage(event) { /* append token to UI */ }
})
```

---

### 32. Lucide React
**What it is:** A beautiful, consistent icon library for React — provides hundreds of clean SVG icons as React components.

**Why we use it:** Used throughout the UI for icons like send buttons, user avatars, loading spinners, and navigation elements.

**Where it is used:** `frontend-react/src/App.tsx` and component files.

---

### 33. ESLint
**What it is:** A code quality tool that analyzes JavaScript/TypeScript code and flags mistakes, bad patterns, and style inconsistencies.

**Why we use it:** Catches bugs during development (e.g., a React hook used in the wrong place). Configured in `frontend-react/eslint.config.js`.

---

## 🐳 INFRASTRUCTURE & DEVOPS

---

### 34. Docker
**What it is:** A tool that packages an application and all its dependencies into a **container** — a standardized, isolated box that runs the same on any computer.

**Why we use it:** "It works on my machine" is a real problem. With Docker, the app runs identically on your laptop, a teammate's laptop, and a production server. The `Dockerfile` is a recipe that builds our app image.

**How our Dockerfile works (Multi-Stage Build):**
1. **Stage 1 (Node.js):** Builds the React app into optimized static files
2. **Stage 2 (Python):** Sets up the Python backend and copies the built React files into it

This produces one single container that serves both the frontend and backend.

---

### 35. Docker Compose
**What it is:** A tool for running multiple Docker containers together as one system.

**Why we use it:** Our app needs multiple services running simultaneously:
- `web` — the FastAPI Python backend
- `worker` — the ARQ background job worker
- `redis` — the Redis cache/queue server
- `postgres` — the PostgreSQL database with PGVector

With `docker-compose up`, all four start together automatically, pre-connected to each other.

---

### 36. UV (Package Manager)
**What it is:** An extremely fast Python package manager made by Astral. It replaces `pip` and `virtualenv`. It reads `pyproject.toml` and installs all dependencies.

**Why we use it:** It is 10-100x faster than `pip` at resolving and installing packages. The exact versions of all packages are locked in `uv.lock` so every developer gets identical dependencies.

**How it is used:**
```bash
uv sync          # Install all dependencies
uv run uvicorn   # Run commands inside the virtual environment
```

---

### 37. Hatchling (Build Backend)
**What it is:** A Python package build tool that knows how to package the `psychtrainer` source code into a distributable Python package.

**Why we use it:** Required by `pyproject.toml` to define how the `src/psychtrainer` package is structured and built.

---

## 🧪 TESTING TOOLS

---

### 38. Pytest
**What it is:** The most popular Python testing framework. You write functions that start with `test_`, and pytest runs them all and reports which pass or fail.

**Why we use it:** To automatically verify that the app's components work correctly. Tests live in the `tests/` folder.

---

### 39. Pytest-Asyncio
**What it is:** A plugin for pytest that allows testing `async` Python functions (since most of our code is async, the regular pytest can't run it).

**Why we use it:** Almost all our agents, retrieval functions, and API handlers are `async def`. This plugin makes them testable.

**Configuration in `pyproject.toml`:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

### 40. Pytest-Mock
**What it is:** A pytest plugin for **mocking** — replacing real dependencies (like an actual database or API call) with fake ones during testing.

**Why we use it:** When testing the Patient agent, we don't want it to actually call the Groq API (costs money, slow). We mock the LLM to return a fake response and just test our logic.

---

## 🏗️ ARCHITECTURE SUMMARY

Here is how all the pieces connect when a student sends a message:

```
[Student types message in React UI]
        ↓
[Zustand store + fetch-event-source sends to FastAPI]
        ↓
[FastAPI verifies Supabase JWT token]
        ↓
[LangGraph runs the workflow graph:]
    1. Summarizer Node → compress old messages if too long (LiteLLM)
    2. Patient Node    → fetch context from PGVector/Qdrant, call Groq LLM (LangChain + LiteLLM)
    3. Professor Node  → evaluate student, write observation note (LiteLLM)
    4. Router Node     → decide next phase (LiteLLM)
        ↓
[State saved to PostgreSQL via LangGraph Checkpoint]
        ↓
[Tokens stream back to browser via SSE (fetch-event-source)]
        ↓
[React UI displays response word by word]
        ↓ (turn 1 only)
[ARQ enqueues title generation job to Redis]
        ↓
[Background ARQ Worker generates title, saves to Supabase + LangGraph]
```

---

## 📋 QUICK REFERENCE TABLE

| Library | Category | Purpose |
|---|---|---|
| FastAPI | Backend Framework | REST API server |
| Uvicorn | Web Server | ASGI server to run FastAPI |
| LangGraph | AI Orchestration | Multi-agent workflow state machine |
| LiteLLM | LLM Gateway | Call any AI model with one API |
| LangChain | AI Utilities | Message types, LLM wrappers |
| LangSmith | Observability | Track and debug LLM calls |
| Pydantic | Data Validation | Type-safe data models |
| Pydantic-Settings | Config | Load .env into typed settings |
| Psycopg v3 | Database Driver | Connect Python to PostgreSQL |
| Psycopg-Pool | Connection Pooling | Reuse DB connections for speed |
| PGVector | Vector Search | Semantic search in PostgreSQL |
| Qdrant | Vector Database | Alternative dedicated vector DB |
| FastEmbed | Local Embeddings | Convert text to vectors (offline) |
| Sentence-Transformers | NLP | CrossEncoder reranking |
| PyTorch | Deep Learning Engine | Powers sentence-transformers |
| PyPDF | PDF Processing | Read medical PDF documents |
| Supabase (Python) | Auth + Cloud DB | JWT auth + prompt registry + sessions |
| PyJWT | Auth | Verify JWT tokens |
| Redis | Cache + Queue | Cache prompts, queue background jobs |
| ARQ | Background Jobs | Async Redis job queue |
| SlowAPI | Rate Limiting | Prevent API abuse |
| Tenacity | Retry Logic | Auto-retry failed LLM calls |
| Structlog | Structured Logging | JSON logs for production |
| HTTPX | HTTP Client | Async HTTP requests to Cohere |
| Python-Dotenv | Config | Load .env file |
| React 19 | Frontend Framework | Build the chat UI |
| TypeScript | Type Safety | Type-checked JavaScript |
| Vite | Build Tool | Fast frontend development & build |
| Zustand | State Management | Global app state for React |
| Supabase JS | Auth (Frontend) | Login, JWT tokens in browser |
| fetch-event-source | SSE Streaming | Stream AI tokens to browser |
| Lucide React | Icons | UI icons |
| ESLint | Code Quality | Catch JavaScript bugs |
| Docker | Containerization | Package app for any environment |
| Docker Compose | Multi-container | Run all services together |
| UV | Package Manager | Fast Python dependency management |
| Pytest | Testing | Automated backend tests |
| Pytest-Asyncio | Testing | Test async Python code |
| Pytest-Mock | Testing | Mock external dependencies in tests |
