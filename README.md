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
make test              # Все тесты
make test-fast         # Быстрые тесты
make test-integration  # Интеграционные тесты
make test-billing      # Тесты биллинга
make test-coverage     # Тесты с покрытием
```

### Управление сервисами

```bash
make up              # Запуск всех сервисов
make down            # Остановка сервисов
make logs            # Просмотр логов
make restart         # Перезапуск основных сервисов
make test-all        # Запуск тестов с подъемом сервисов
```

