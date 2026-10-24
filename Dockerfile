# syntax=docker/dockerfile:1
# Based on LiveKit's recommended pip template (docs.livekit.io/deploy/agents/builds).
# Built by LiveKit Cloud on `lk agent create` / `lk agent deploy`.

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Keep downloaded model files inside /app so they're copied to the final image
    HF_HOME=/app/.cache/huggingface

# --- Build stage: install dependencies -----------------------------------------
FROM base AS build

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ python3-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, for layer caching
COPY requirements.txt ./
RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download any model files the agent needs, so cold starts are fast
RUN python -m livekit.agents download-files

# --- Production stage: no build tools, non-root user ----------------------------
FROM base

ARG UID=10001
RUN adduser --disabled-password --gecos "" --home "/app" --shell "/sbin/nologin" \
    --uid "${UID}" appuser

WORKDIR /app
COPY --from=build --chown=appuser:appuser /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

# LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET are injected by LiveKit Cloud.
# Everything else (Groq, Deepgram, ElevenLabs, Google) comes from `lk agent` secrets.
CMD ["python", "main.py", "start"]
