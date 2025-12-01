# Rental Core

API сервис для управления арендой powerbank'ов.

## Запуск

```bash
cd services/rental-core
uv sync
uv run python -m rental_core.main
```

Или через Docker:
```bash
docker compose up rental-core
```

Сервис будет доступен на http://localhost:8000

## Тестирование

```bash
cd services/rental-core
uv run pytest tests/ -v
```
## База данных

Сервис использует две PostgreSQL-БД (через общий пакет `shared`):

- `db-rental` — основная БД для офферов, аренд и ключей идемпотентности.
- `db-billing` — read-only доступ к данным биллинга (долги, попытки платежей), чтобы отдавать корректный статус аренды.
