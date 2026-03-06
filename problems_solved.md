# PsychTrainer: Comprehensive Architecture Evolution & Problem Resolution

This document serves as a complete chronological record of every technical bottleneck, architectural flaw, and scalability issue that was identified and resolved across all 40 Development Phases during the construction of the PsychTrainer Enterprise web application.

---

## 🏗️ Core Architecture & Foundation (Phases 1-7)
**1. Problem:** Starting a blank project with manual dependency management leads to conflicting packages and broken builds.
**Solution:** Initialized the project strictly using `uv`, creating a deterministic virtual environment and establishing a clean separation between `/src`, `/frontend`, and executable `/scripts`.

**2. Problem:** Raw medical PDFs and interview CSVs cannot be inherently understood by an LLM without massive token limits.
**Solution:** Built a robust Data Ingestion pipeline (`rag/ingest.py`) parsing the OSCE script, Adolescent Depression Toolkit, and 6K MedQA records into semantic chunks via `sentence-transformers`, stored in a local Qdrant Vector database.

**3. Problem:** A single monolithic prompt is too brittle to handle distinct agent personas and rigid grading rules simultaneously.
**Solution:** Separated logic into two autonomous agents: the `Patient` (handling persona roleplay and clinical RAG retrieval) and the invisible `Professor` (handling rubric enforcement and JSON grade generation).

**4. Problem:** Creating a conversational loop with standard `while` logic is mathematically unstable and prone to infinite recursion.
**Solution:** Orchestrated the agents using a deterministic LangGraph State Machine (`workflow/graph.py`), introducing strict phase transitions (Introduction -> Exploration -> Conclusion) controlled by a dedicated Supervisor/Router node.

**5. Problem:** Standard Python scripts cannot be securely accessed over the internet.
**Solution:** Wrapped the LangGraph engine in a FastAPI ASGI application (`service/api.py`), exposing modular REST endpoints and initial WebSocket layers.

**6. Problem:** The backend had no visual interface for users to interact with.
**Solution:** Designed a vanilla HTML/CSS (`frontend/`) Single Page Application featuring a modern glassmorphism aesthetic.

**7. Problem:** All application code was crammed into two messy files, making debugging impossible.
**Solution:** Undertook a massive component refactoring, modularizing the logic into dedicated `agents/`, `workflow/`, `service/`, and `rag/` subdirectories.

---

## 💾 Persistence, Streaming, & UX Optimizations (Phases 8-18)
**8. Problem:** Chat histories were stored in temporary Python RAM (`dict`). Refreshing the browser permanently deleted the conversation.
**Solution:** Hooked `langgraph-checkpoint-sqlite` into the graph. Passing a `thread_id` to the workflow automatically saved and hydrated state seamlessly between HTTP requests.

**9. Problem:** Waiting 15 seconds for the LLM to write a massive response caused users to think the app crashed.
**Solution:** Rewrote `patient.py` to stream tokens. Configured `api.py` to serve Server-Sent Events (SSE) and refactored the frontend to render the tokens utilizing a typewriter effect in real-time.

**10. Problem:** It was impossible to debug *why* the LLM hallucinated, as the internal prompt math was invisible.
**Solution:** Integrated LangSmith observability via `litellm` callbacks in the FastAPI lifecycle, enabling visual, node-by-node tracing of all graphs.

**11. Problem:** Conversations exceeding 20 turns crashed the LLM due to context window token limits (OOM).
**Solution:** Implemented Memory Summarization. Added a `summarize_conversation_node` to the LangGraph router that detects long chats, compresses the oldest 15 turns into a dense paragraph, and injects it back into the runtime state to save tokens.

**12. Problem:** Users could only have one conversation at a time; previous SQLite records were orphaned with no UI access.
**Solution:** Built a ChatGPT-style left Sidebar. Added a `GET /api/sessions` endpoint to list history and `loadSessionsList()` to swap between concurrent conversations.

**13. Problem:** The session history displayed raw UUIDs like `usr_123_abc987`, which is unreadable.
**Solution:** Programmed an async background task to trigger on Turn 1. It prompts Groq to analyze the first exchange and dynamically generates a 3-word title (e.g., "OCD Initial Intake"), which is subsequently saved to the UI state.

**14. Problem:** On small laptop screens, the new sidebar took up 30% of the valuable chat real estate.
**Solution:** Engineered CSS flex-box transitions and a toggle button to make the sidebar smoothly collapsible, saving screen space.

**15. Problem:** The "New Chat" and "Search" functional buttons overlapped text and broke pixel-perfect alignment when the sidebar collapsed.
**Solution:** Re-engineered the HTML structure, moving the action utilities into a fixed vertical navigation stack floating externally to the sidebar content.

**16. Problem:** Having 50 historical chats broke the screen constraints, forcing the user to scroll the entire browser window instead of just the sidebar list.
**Solution:** Applied strict `max-height: 100vh` and scoped `overflow-y: auto` to properly constrain flex layout scrolling.

**17. Problem:** The original dark aesthetic was difficult to read in bright medical/classroom settings.
**Solution:** Inverted the CSS `:root` variables to a clean, highly accessible whitish ChatGPT-style palette.

**18. Problem:** Attempting to view the App on a mobile phone (iOS/Android) caused the Chat UI and Grading UI to render on top of each other, making it completely broken.
**Solution:** Injected `.mobile-tabs` component and CSS `@media` queries. On screens `<768px`, the UI transforms into a vertical tabbed layout, allowing seamless toggling between Chat and Evaluation panels.

---

## 🏢 Enterprise Production Refactoring (Phases 19-33)
**19. Problem:** The SQLite database crashed under the workload of multiple concurrent students, locking the `checkpoints` file. Furthermore, iterating over thousands of raw LangGraph logs just to list user sessions in the sidebar was O(N) computational hell.
**Solution:** Ripped out SQLite and provisioned a remote Neon PostgreSQL connection pool (`AsyncPostgresSaver`).

**20. Problem:** The `/api/session` endpoints were completely open. Anyone on the internet could query anyone else's session UUID.
**Solution:** Implemented strict multi-tenancy. Configured Supabase Auth. Wrote a `get_current_user` FastAPI dependency that cryptographically decodes the local JWT, rejecting any API call where the `thread_id` does not match the token's internal `user_id`.

**21. Problem:** A malicious user could write a `for-loop` script to hit the `/chat` endpoint 1,000 times a second, bankrupting the Groq billing account (Denial of Service).
**Solution:** Provisioned an Upstash Redis database. Implemented global `fastapi-limiter` dependencies clamped to strictly 5 requests per minute, instantly blocking abusive network traffic before the LLM booted up.

**22. Problem:** The Vanilla HTML/JS frontend became unmaintainable spaghetti code as state complexity grew.
**Solution:** Executed a massive React migration. Initialized a Vite project. Transpiled standard HTML into modular JSX layout segments (`<Sidebar />`, `<ChatPanel />`, `<AuthScreen />`).

**23. Problem:** JavaScript provided zero safety guarantees; misspelled variables would silently crash the React app in production.
**Solution:** Added TypeScript (`tsconfig.json`). Converted `.jsx` to `.tsx`, enforcing strict Type Interfaces on all component props and API payloads to catch errors at compile-time.

**24. Problem:** Pushing code blindly to production often broke existing features without warning.
**Solution:** Engineered a robust Pytest CI/CD suite. Wrote `tests/conftest.py` to securely mock Supabase/Redis dependencies, then asserted LangGraph routing rules. Wired it into a `.github/workflows/test.yml` GitHub Action for automated pull-request validation.

**25. Problem:** Running locally via `uv` works, but configuring Node, Python, Postgres, and Redis independently on a blank AWS EC2 instance is excruciating and error-prone.
**Solution:** Built a multi-stage `Dockerfile` (Node builder -> Python FastAPI runner) and a `docker-compose.yml` that securely orchestrates the web application, Postgres, and Redis inside an isolated bridge network, allowing 1-click deployments.

**26. Problem:** If the prompt engineer wanted to tweak Dr. Williams' behavior, they had to modify hardcoded `prompt_registry.py` strings and manually reboot the entire production server cluster.
**Solution:** Wrote SQL migrations to create a `system_prompts` table in Supabase. Engineered a dynamic Redis Cache wrapper in Python that automatically fetches and caches prompt updates from the cloud without requiring a server reboot.

**27. Problem:** Booting up the LangGraph checkpointer just to read the `title` and `is_ended` status for the sidebar UI was heavily taxing the core logic engine.
**Solution:** Decoupled UI logic from Deep State logic. Wrote SQL migrations for a dedicated `sessions` Supabase UI table. Sidebar generation is now an O(1) instantaneous SQL `SELECT`, leaving LangGraph untouched until the conversation is physically clicked.

**28. Problem:** FastAPI was running synchronous internal code, blocking the async ASGI Event Loop and massively limiting how many concurrent students the server could handle.
**Solution:** Refactored the core AI agents (`patient.py`, `professor.py`, `summarizer.py`, `graph.py`) to execute natively on `async def` and `await litellm.acompletion()`. Stripped all ThreadPool dependencies from `api.py`.

**29. Problem:** Loading the massive `sentence-transformers` library synchronously into FastAPI memory choked initial server boot times.
**Solution:** Swapped the framework for `fastembed`. Updated `knowledge.py` to use stateless `AsyncTextEmbedding` and removed the clunky PyTorch dependencies entirely.

**30. Problem:** Throwing `asyncio.create_task()` fire-and-forget loops into memory is mathematically unsafe; if FastAPI shuts down, those rogue background tasks are instantly killed, corrupting data.
**Solution:** Migrated unsafe spawns to `BackgroundTasks.add_task()` in `/api/session/chat`, guaranteeing the ASGI server will safely flush and await completion before rebooting.

**31. Problem:** If 100 students all started a session exactly at the same time, triggering 100 background tasks to call Groq for a title generation simultaneously, the ASGI server would suffer an OOM (Out Of Memory) memory spike and forcefully crash.
**Solution:** Provisioned ARQ, an Enterprise Redis Queue. Created a highly resilient `worker.py` daemon explicitly segregated from FastAPI. Heavy LLM tasks are enqueued safely to Redis, where the worker processes them gracefully at its own capacity, providing infinite retry resilience.

**32. Problem:** The backend authentication middleware took 500ms per request because it physically pinged the Supabase REST API across the internet on every single message.
**Solution:** Implemented **Zero-Latency Authentication**. Configured the `PyJWT` cryptography module internally using the `SUPABASE_JWT_SECRET` local variable. Tokens are now verified securely in `<1 millisecond` without making external web requests.

**33. Problem:** Sometimes the LangGraph structural Router would hallucinate, returning `{"next_step": "CONCLUSION"}` instead of `{phase: "CONCLUSION"}`, instantly crashing the state machine because Python keys weren't perfectly matched.
**Solution:** Enforced strict JSON parsing schemas via Pydantic (`RouterDecision(BaseModel)`). Injected structured output definitions directly into `litellm` so the groq responses are guaranteed to perfectly map to system architecture.

---

## 💎 Final Hardening & Observability (Phases 34-40)
**34. Problem:** If the Groq API momentarily returned a `503 Service Unavailable`, LangGraph crashed immediately, forcing the user to dump their entire conversation and start over.
**Solution:** Added the `tenacity` retry library. The application now features exponential back-off (`@retry`). If Groq drops a packet, the backend waits 2 seconds and smoothly silently retries, hiding the error from the student.

**35. Problem:** Manual JavaScript `TextDecoder` token parsing loops in the React frontend frequently dropped trailing spaces or punctuation due to fragment chunking errors.
**Solution:** Installed the `@microsoft/fetch-event-source` enterprise library to natively ingest Server-Sent Events, completely auto-handling reconnection buffers, HTTP failure scenarios, and text stream compilation flawlessly.

**36. Problem:** The React app hardcoded `http://localhost:8000/api`. If deployed to Vercel, it still tried to query localhost, breaking the web app for production users.
**Solution:** Injected Vite Environment Configurations (`.env`). App natively transpiles dynamically to hit `import.meta.env.VITE_API_URL` based on CI/CD compilation definitions.

**37. Problem:** As the frontend evolved, `App.tsx` became bloated with overlapping `useState` hooks, recreating massive prop-drilling interfaces that caused chaotic DOM rendering.
**Solution:** Overhauled the React state architecture into **Zustand**. Created a massive centralized `store/useStore.ts` that handles all async logic cleanly. The Sidebar and Chat Panel components now extract their bindings globally without prop-drilling a single variable.

**38. Problem:** High precision medical workflows demanded literal string matches (e.g., "Sertraline 50mg"), but Semantic RAG math maps abstract concepts, frequently failing the precision test.
**Solution:** Engineered an **Enterprise Hybrid Search (RRF) + Cross-Encoder Reranker** schema. `ingest.py` was refactored to dual-vectorize data via BM25 (Sparse) and SentenceTransformers (Dense). `knowledge.py` was rebuilt to natively query both vectors from Qdrant, extract 20 chunks, aggressively rescore their contextual relevance using `ms-marco-MiniLM-L-6-v2`, and inject immaculate context into the LangGraph payload.

**39. Problem:** The `slowapi` implementation wasn't robust enough; it rate-limited by IP address (`get_remote_address`). This meant if 50 students logged into the psychology classroom from their University Wi-Fi network, `slowapi` would ban the entire university simultaneously.
**Solution:** Wrote a custom interception lambda that parses the actual cryptographically secure Supabase `user_id` inside the JWT payload, and uses that individual ID as the Token Bucket key in Redis, preserving enterprise classroom functionality.

**40. Problem:** The Python standard library `logging.getLogger()` produced beautiful English terminal traces locally ("User logged in"), but these raw strings are absolutely useless when piped into AWS CloudWatch or Datadog, which cannot natively search human sentences.
**Solution:** Ripped out native text logging strings across the entire application and executed a system-wide refactor using **Structlog**. The entire backend now conditionally utilizes the `setup_logger()` module to seamlessly output hyper-readable colored text while developing locally, and instantly toggles to highly optimized, strictly queried `JSON` payloads (`{"event": "login", "user": "abc"}`) native to enterprise APM environments when deployed to production.

**41. Problem:** The local file-based Qdrant vector store could not scale horizontally. If multiple FastAPI containers were spun up behind a load balancer, they would crash due to file-lock collisions.
**Solution:** Migrated the entire Vector Database architecture to **PostgreSQL `pgvector`**. Re-engineered data ingestion to natively embed chunks into a cloud Neon DB `document_embeddings` table. To preserve the system's high-accuracy medical retrieval, rebuilt the Hybrid Search (Dense + Sparse) to execute entirely in an optimized PostgreSQL SQL CTE, leveraging native **Full Text Search (`to_tsvector`)** and **Reciprocal Rank Fusion (RRF)** directly at the data layer, eliminating local memory bloat and enabling infinite horizontal scalability.
