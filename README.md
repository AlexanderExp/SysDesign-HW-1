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
Применение миграций (две отдельные БД):

```bash
# 1. Поднять только базы (без сервисов)
docker compose up -d db-rental db-billing

# 2. Миграции основной БД (rental)
uv run alembic -c alembic_rental.ini upgrade head

# 3. Миграции биллинга
uv run alembic -c alembic_billing.ini upgrade head
```

Запуск сервисов:
```bash
docker compose up -d
```

## Разработка

### Сервисы

- **rental-core**: http://localhost:8000
- **PostgreSQL (rental-db)**: localhost:5433 (service: `db-rental`)  
- **PostgreSQL (billing-db)**: localhost:5434 (service: `db-billing`)
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
make migrate-all     # Запуск миграций
```

