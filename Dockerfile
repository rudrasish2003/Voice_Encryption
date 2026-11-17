# syntax=docker/dockerfile:1
# Build with local ML models too:  docker compose build --build-arg WITH_LOCAL_ML=true
ARG WITH_LOCAL_ML=false

# ---- builder: resolves + installs deps into /srv/.venv ----
FROM python:3.11-slim AS builder
ARG WITH_LOCAL_ML
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /srv
RUN if [ "$WITH_LOCAL_ML" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends build-essential git \
      && rm -rf /var/lib/apt/lists/*; \
    fi
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$WITH_LOCAL_ML" = "true" ]; then EXTRA="--extra local-ml"; else EXTRA=""; fi; \
    uv sync --frozen --no-install-project $EXTRA

# ---- runtime: no compilers, no uv, no caches ----
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PATH="/srv/.venv/bin:$PATH"
# ffmpeg is required for audio normalization (subprocess), libsndfile1 for soundfile I/O.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY --from=builder /srv/.venv /srv/.venv
COPY app ./app
COPY static ./static
COPY scripts ./scripts

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
