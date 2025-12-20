#!/bin/bash
# Скрипт для восстановления DWH из дампа
# Использование: ./scripts/restore_dwh.sh [путь_к_дампу]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ARTIFACTS_DIR="$PROJECT_DIR/dwh/artifacts"

# Путь к дампу (по умолчанию dwh_dump.sql)
DUMP_FILE="${1:-$ARTIFACTS_DIR/dwh_dump.sql}"

echo "=== Восстановление DWH из дампа ==="
echo "Файл дампа: $DUMP_FILE"

# Проверяем существование файла
if [ ! -f "$DUMP_FILE" ]; then
    echo "ОШИБКА: Файл дампа не найден: $DUMP_FILE"
    exit 1
fi

# Проверяем, что контейнер db-dwh запущен
if ! docker ps --format '{{.Names}}' | grep -q '^db-dwh$'; then
    echo "ОШИБКА: Контейнер db-dwh не запущен!"
    echo "Запустите: docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d"
    exit 1
fi

echo "Восстановление базы данных..."
cat "$DUMP_FILE" | docker exec -i db-dwh psql -U dwh -d dwh

echo ""
echo "=== Проверка восстановления ==="
docker exec db-dwh psql -U dwh -d dwh -c "
SELECT 
    schemaname || '.' || relname as table_name,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname IN ('raw_rental', 'raw_billing', 'core', 'mart', 'meta')
ORDER BY schemaname, relname;
"

echo ""
echo "=== Готово! ==="


