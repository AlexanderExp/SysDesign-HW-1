#!/bin/bash
# Скрипт для создания дампа DWH базы данных
# Использование: ./scripts/dump_dwh.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ARTIFACTS_DIR="$PROJECT_DIR/dwh/artifacts"
TIMESTAMP=$(date +%Y%m%dT%H%M%SZ)

# Создаём директорию если не существует
mkdir -p "$ARTIFACTS_DIR"

echo "=== Создание дампа DWH ==="
echo "Timestamp: $TIMESTAMP"

# Проверяем, что контейнер db-dwh запущен
if ! docker ps --format '{{.Names}}' | grep -q '^db-dwh$'; then
    echo "ОШИБКА: Контейнер db-dwh не запущен!"
    echo "Запустите: docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d"
    exit 1
fi

# Создаём полный дамп DWH (схема + данные)
echo "Создание полного дампа..."
docker exec db-dwh pg_dump -U dwh -d dwh \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    > "$ARTIFACTS_DIR/dwh_dump.sql"

echo "Дамп создан: $ARTIFACTS_DIR/dwh_dump.sql"

# Создаём дамп только схемы (для документации)
echo "Создание дампа схемы..."
docker exec db-dwh pg_dump -U dwh -d dwh \
    --schema-only \
    --no-owner \
    --no-privileges \
    > "$ARTIFACTS_DIR/dwh_schema_only.sql"

echo "Схема создана: $ARTIFACTS_DIR/dwh_schema_only.sql"

# Показываем статистику по таблицам
echo ""
echo "=== Статистика по таблицам ==="
docker exec db-dwh psql -U dwh -d dwh -c "
SELECT 
    schemaname || '.' || relname as table_name,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname IN ('raw_rental', 'raw_billing', 'core', 'mart', 'meta')
ORDER BY schemaname, relname;
"

# Показываем данные из mart.kpi_daily
echo ""
echo "=== Данные из mart.kpi_daily ==="
docker exec db-dwh psql -U dwh -d dwh -c "
SELECT * FROM mart.kpi_daily ORDER BY day DESC LIMIT 10;
"

echo ""
echo "=== Готово! ==="
echo "Файлы дампа:"
echo "  - $ARTIFACTS_DIR/dwh_dump.sql (полный дамп)"
echo "  - $ARTIFACTS_DIR/dwh_schema_only.sql (только схема)"


