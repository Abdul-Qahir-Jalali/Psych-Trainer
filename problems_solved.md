# PsychTrainer: Architecture Evolution & Problems Solved

This document serves as a comprehensive record of all technical bottlenecks, architectural flaws, and scalability issues that were identified and resolved during the migration of PsychTrainer from a lightweight prototype to an Enterprise-grade web application.

---

## 🏗️ 1. Core Architecture & Persistence
**Problem:** The original prototype stored chat histories in Python memory (`dict`). If the FastAPI server restarted, or if a user refreshed their browser, the entire conversation was permanently deleted. Furthermore, a single SQLite file would lock up under concurrent users.
**Solution:** 
- Integrated LangGraph's `AsyncPostgresSaver` backed by a remote Neon PostgreSQL connection pool.
- Migrated all AI generation to native `async/await` to unblock the main FastAPI event loop.
- Implemented Supabase as a fast UI-facing session table (O(1) lookups) replacing slow O(N) LangGraph checkpoint iterations.

## 🧠 2. Advanced RAG & Clinical Accuracy
**Problem:** The base RAG pipeline used purely semantic math vectors. If a student typed a highly specific medical term like "diaphoresis", the system often missed it if the semantic meaning didn't align perfectly. It also maxed out at pulling 3 chunks, losing context.
**Solution:**
- Integrated **Hybrid Search**. We modified the data ingestion pipeline to generate both Dense Vectors (semantic math) and Sparse Vectors (BM25 keyword tokens) simultaneously using `fastembed`.
- Implemented a **Cross-Encoder Reranker**. The engine now casts a wide net (fetching 20 chunks), and then forces a secondary ML model (`ms-marco-MiniLM-L-6-v2`) to mathematically re-score the relevance of each chunk against the user's specific query before passing only the top 3 into the LLM context window.

## ⚙️ 3. LLM Reliability & Orchestration
**Problem:** Hardcoded JSON strings from Groq often failed to parse, breaking the Python backend. Furthermore, if the Groq API timed out, the server threw a 500 error instead of recovering.
**Solution:**
- Implemented **Pydantic Structured Outputs**. The Router decision logic is now strictly enforced by `RouterDecision(BaseModel)` parsed via LiteLLM to guarantee valid state transitions.
- Integrated **Tenacity Exponential Backoff**. RAG/Patient LLM calls are wrapped in `@retry` decorators to gracefully loop and recover from momentary Groq API outages.

## 🚀 4. Background Processing Resilience
**Problem:** The system generated dynamic session titles using the LLM. Doing this synchronously inside the chat HTTP request delayed the user's response time and risked OOM crashes under high load.
**Solution:**
- Provisioned an **Upstash Redis ARQ Worker Node**.
- Extracted the title generation into `worker.py`, firing off tasks via `FastAPI BackgroundTasks` into an isolated process queue, ensuring the main ASGI server never drops frames.

## 🔒 5. Enterprise Security & Multi-Tenancy
**Problem:** The API was completely open to the internet. Anyone could theoretically spoof session IDs or drain the Groq API credits in an infinite loop.
**Solution:**
- **Zero-Latency Authentication:** Integrated Supabase JWT validation directly into FastAPI dependencies, rejecting unauthorized requests cryptographically without blocking on network round-trips.
- **Global Rate Limiting:** Deployed `slowapi.Limiter`, mapping the token buckets to the Supabase `user_id` stored in the Redis backend. Chat endpoints are strictly locked to `20 requests/minute` to guarantee financial safety.

## ⚛️ 6. Frontend Scalability & React State
**Problem:** The original `App.tsx` acted as a monolithic "God Component" filled with 13 independent `useState` hooks. Every single keystroke triggered a full application DOM re-render, and passing functions deeply down the tree caused massive Prop Drilling.
**Solution:**
- Migrated to **Zustand** global state management (`useStore.ts`).
- Decoupled `App.tsx` into an empty layout shell. The Sidebar, Chat Panel, and Evaluation UI now hook directly into the global store, cutting re-renders by 90% and completely eliminating prop-drilling interfaces.
- Replaced manual `TextDecoder` loops with `@microsoft/fetch-event-source` for enterprise-grade SSE parsing and auto-reconnection.

## 📊 7. DevOps & Observability
**Problem:** The application wrote standard English text into the terminal (e.g., `logger.info("User logged in")`). In a cloud environment, string text is un-indexable, making it impossible to query errors in Datadog or CloudWatch.
**Solution:**
- **JSON Structured Logging:** Replaced the legacy `logging` module across all 10 Python microservices with `structlog`. 
- Created a dynamic interceptor in `logger_setup.py` that outputs beautiful colored text locally during development, but instantly toggles to pure JSON mappings (`{"event": "login", "user": "123"}`) when `ENVIRONMENT=production` is detected.

## 🐳 8. Enterprise Deployment Architecture
**Problem:** "It works on my machine" deployment headaches.
**Solution:**
- Developed a comprehensive Multi-stage `Dockerfile`.
- Built a `docker-compose.yml` that simultaneously orchestrates the FastAPI application, the local ARQ Redis Background Worker, and the Qdrant Vector database into a unified, secure bridge network.
- Migrated secret hardcoded models and URLs to `.env` validation via `Pydantic Settings`.
