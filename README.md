# Сервис аренды пауэрбанков

Микросервисная система аренды пауэрбанков с модулями биллинга и основной логики аренды.

## Архитектура

- **rental-core**: FastAPI сервис для операций аренды
- **billing-worker**: Фоновый воркер для обработки платежей
- **shared**: Общие утилиты и модели базы данных
- **external-stubs**: Заглушки внешних сервисов для тестирования
- **dwh**: Data Warehouse с ETL-процессами на Apache Airflow

## Требования

- Python 3.11
- Docker & Docker Compose
- Менеджер пакетов uv

## Установка и запуск

Установка uv по [инструкции](https://docs.astral.sh/uv/getting-started/installation/)

## Остановить все контейнеры и перезапустить их без кэша

docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
docker compose build --no-cache
docker compose up -d

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

## Data Warehouse (DWH)

Для запуска DWH с ETL-процессами на Apache Airflow:

```bash
# Запуск основной системы + DWH
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d

# Автоматическая настройка DWH (connections, права, DAG-и)
chmod +x scripts/setup_dwh.sh
./scripts/setup_dwh.sh

# Создание тестовых данных
chmod +x scripts/create_test_data.sh
./scripts/create_test_data.sh

# Запуск ETL
docker exec airflow-webserver airflow dags trigger dwh_master
```

**Подробная инструкция:** [`docs/QUICKSTART_DWH.md`](docs/QUICKSTART_DWH.md)

## Разработка

### Сервисы

- **rental-core**: http://localhost:8000
- **PostgreSQL (rental-db)**: localhost:5433 (service: `db-rental`)
- **PostgreSQL (billing-db)**: localhost:5434 (service: `db-billing`)
- **PostgreSQL (DWH)**: localhost:5444 (service: `db-dwh`)
- **Apache Airflow**: http://localhost:8080 (admin/admin)
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

### Дополнительная документация

#### Основная система
1. **[Диаграммы архитектуры системы аренды пауэрбанков](diagrams/README.md)**
2. **[ADR](docs/ADR.md)**
3. **[Billing Worker](services/billing-worker/README.md)**
4. **[Rental Core](services/rental-core/README.md)**
5. **[Описание автотестов](tests/README.md)**
6. **[Демо UI](ui/README.md)**

#### Data Warehouse (DWH)
7. **[DWH Quick Start — Запуск с нуля](docs/QUICKSTART_DWH.md)**
8. **[DWH README — Общее описание](docs/README_DWH.md)**
9.  **[Архитектура DWH (диаграмма)](docs/dwh_architecture_mermaid.md)**
10. **[Описание таблиц DWH](docs/dwh_tables.md)**
11. **[ER-диаграмма DDS слоя](docs/er_dds_mermaid.md)**

