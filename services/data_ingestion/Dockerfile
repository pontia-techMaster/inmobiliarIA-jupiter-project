FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared ./shared
COPY services/data_ingestion ./services/data_ingestion

RUN uv sync --package data_ingestion --frozen --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--package", "data_ingestion", "python", "-m", "data_ingestion.worker"]
