# Сервис аренды пауэрбанков

Микросервисная система аренды пауэрбанков с модулями биллинга и основной логики аренды.

## Архитектура

- **rental-core**: FastAPI сервис для операций аренды
- **billing-worker**: Фоновый воркер для обработки платежей
- **shared**: Общие утилиты и модели базы данных
- **external-stubs**: Заглушки внешних сервисов для тестирования

## Требования

- Python 3.11
- Docker & Docker Compose
- Менеджер пакетов uv

## Установка и запуск

Установка uv по [инструкции](https://docs.astral.sh/uv/getting-started/installation/)

Установка Python 3.11:
```bash
uv python install 3.11 --default
```

Установка зависимостей:
```bash
uv sync
```

Запуск сервисов:
```bash
docker compose up -d
```

Применение миграций:
```bash
docker compose up -d db
uv run alembic upgrade head
```

## Разработка

### Сервисы

- **rental-core**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **External stubs**: localhost:3629

### Тестирование

```bash
pytest tests/                    # Все тесты
pytest tests/ -m integration     # Интеграционные тесты
pytest tests/ -m billing         # Тесты биллинга
pytest tests/ --cov=services     # Тесты с покрытием
```

### Управление сервисами

```bash
docker compose up -d                              # Запуск всех сервисов
docker compose down                               # Остановка сервисов
docker compose logs -f                            # Просмотр логов
docker compose restart rental-core billing-worker # Перезапуск основных сервисов
```

