FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared ./shared
COPY services/ranking_and_rendering ./services/ranking_and_rendering

RUN uv sync --package ranking_and_rendering --frozen --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--package", "ranking_and_rendering", "python", "-m", "ranking_and_rendering.worker"]
