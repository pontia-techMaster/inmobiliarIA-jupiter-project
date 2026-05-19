FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared ./shared
COPY services/api_gateway ./services/api_gateway

RUN uv sync --package api_gateway --frozen --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--package", "api_gateway", "uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
