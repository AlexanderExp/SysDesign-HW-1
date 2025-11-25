FROM ghcr.io/astral-sh/uv:python3.11-alpine

WORKDIR /app/services/billing-worker

COPY shared ../../shared

COPY services/billing-worker/pyproject.toml services/billing-worker/uv.lock ./

RUN uv sync --locked

COPY services/billing-worker .

ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "python", "-m", "billing_worker.main"]
