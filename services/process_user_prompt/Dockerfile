FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared ./shared
COPY services/process_user_prompt ./services/process_user_prompt

RUN uv sync --package process_user_prompt --frozen --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--package", "process_user_prompt", "python", "-m", "process_user_prompt.worker"]
