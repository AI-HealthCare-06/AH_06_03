FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# curl: compose healthcheck / gcc: asyncmy 휠 없을 때 빌드용
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project

ENV PATH="/.venv/bin:$PATH"

COPY app ./app
