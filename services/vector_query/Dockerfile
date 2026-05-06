FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared ./shared
COPY services/vector_query ./services/vector_query

RUN uv sync --package vector_query --frozen --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--package", "vector_query", "python", "-m", "vector_query.worker"]
