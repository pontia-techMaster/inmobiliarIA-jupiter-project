FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared ./shared
COPY services/tracer ./services/tracer

RUN uv sync --package tracer --frozen --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--package", "tracer", "uvicorn", "tracer.main:app", "--host", "0.0.0.0", "--port", "9000"]
