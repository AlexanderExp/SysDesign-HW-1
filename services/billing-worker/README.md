# Billing Worker

Фоновый сервис для обработки платежей и управления долгами в системе аренды.

## Запуск

```bash
cd services/billing-worker
uv sync
uv run python -m billing_worker.main
```

Или через Docker:
```bash
docker compose up billing-worker
```

## Тестирование

```bash
cd services/billing-worker
uv run pytest tests/ -v
```
