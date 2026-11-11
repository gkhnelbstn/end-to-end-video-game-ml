# syntax=docker/dockerfile:1
# One Dockerfile, two images:
#   --target app       FastAPI backend, Celery worker, Flower, seed/backfill scripts
#   --target frontend  Streamlit dashboard

ARG PYTHON_VERSION=3.12

# ---- builder: resolve dependencies from the lockfile with uv ----
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM builder AS app-deps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups

FROM builder AS frontend-deps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --only-group frontend

FROM builder AS mlflow-deps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --only-group mlflow-server

# ---- runtime base: slim image, non-root user, no build tooling ----
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 1000 app
WORKDIR /app
USER app

# ---- app: API, worker, Flower ----
FROM runtime AS app
COPY --from=app-deps /app/.venv /app/.venv
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- frontend: Streamlit dashboard ----
FROM runtime AS frontend
COPY --from=frontend-deps /app/.venv /app/.venv
COPY src/frontend ./src/frontend
EXPOSE 8501
CMD ["streamlit", "run", "src/frontend/app.py", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]

# ---- mlflow: tracking server + model registry (command set in compose.yaml) ----
FROM runtime AS mlflow
COPY --from=mlflow-deps /app/.venv /app/.venv
COPY src/__init__.py ./src/__init__.py
COPY src/scripts ./src/scripts
USER root
RUN mkdir -p /mlflow/artifacts && chown -R app /mlflow
USER app
EXPOSE 5000
