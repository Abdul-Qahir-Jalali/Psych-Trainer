# ==========================================
# STAGE 1: React Vite Builder
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend-react

# Install dependencies first (caching layer)
COPY frontend-react/package*.json ./
RUN npm install

# Copy source and build strictly typed TSX into minified JS
COPY frontend-react/ .
# Using `tsc` to verify types before Vite compiles the payload
RUN npm run build


# ==========================================
# STAGE 2: Python FastAPI Runner
# ==========================================
FROM python:3.12-slim

# Install system dependencies (needed for psycopg2 compilation if required)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Astral's blazing-fast `uv` package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /bin/uv

# Copy Python dependencies first (caching layer)
COPY pyproject.toml .
# Sync dependencies (--no-dev prevents downloading pytest/mocking tools in production)
RUN uv sync --no-dev --no-install-project

# Copy entire Python backend logic
COPY src/ ./src/

# IMPORTANT: Copy the perfectly built, minified React app from Stage 1!
# FastAPI points `StaticFiles` directly to this directory.
COPY --from=frontend-builder /app/frontend-react/dist /app/frontend-react/dist

# Expose FastAPI Port
EXPOSE 8000

# Set production environment variables
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Run the Uvicorn ASGI server via UV
CMD ["uv", "run", "uvicorn", "src.psychtrainer.service.api:app", "--host", "0.0.0.0", "--port", "8000"]
