FROM ghcr.io/astral-sh/uv:python3.11-alpine

WORKDIR /app/services/rental-core

COPY shared ../../shared

COPY services/rental-core/pyproject.toml services/rental-core/uv.lock ./

RUN uv sync --locked

COPY services/rental-core .

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "uvicorn", "rental_core.main:app", "--host", "0.0.0.0", "--port", "8000"]
