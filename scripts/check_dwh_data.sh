#!/bin/bash
# Скрипт для проверки данных в DWH (для защиты)
# Использование: ./scripts/check_dwh_data.sh

set -e

echo "=== Проверка данных в DWH ==="
echo ""

# Проверяем, что контейнер db-dwh запущен
if ! docker ps --format '{{.Names}}' | grep -q '^db-dwh$'; then
    echo "ОШИБКА: Контейнер db-dwh не запущен!"
    echo "Запустите: docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d"
    exit 1
fi

echo "1. Количество записей в RAW слое:"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'raw_rental.rentals: ' || count(*) FROM raw_rental.rentals;"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'raw_rental.quotes: ' || count(*) FROM raw_rental.quotes;"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'raw_billing.payment_attempts: ' || count(*) FROM raw_billing.payment_attempts;"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'raw_billing.debts: ' || count(*) FROM raw_billing.debts;"

echo ""
echo "2. Количество записей в CORE слое:"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'core.rentals: ' || count(*) FROM core.rentals;"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'core.payment_attempts: ' || count(*) FROM core.payment_attempts;"

echo ""
echo "3. Количество записей в MART слое:"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'mart.fct_rentals: ' || count(*) FROM mart.fct_rentals;"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'mart.fct_payments: ' || count(*) FROM mart.fct_payments;"
docker exec db-dwh psql -U dwh -d dwh -t -c "SELECT 'mart.kpi_daily: ' || count(*) FROM mart.kpi_daily;"

echo ""
echo "4. Данные из mart.kpi_daily (последние 5 дней):"
docker exec db-dwh psql -U dwh -d dwh -c "
SELECT 
    day,
    quotes_cnt,
    rentals_started_cnt,
    rentals_finished_cnt,
    payments_attempts_cnt,
    payments_success_cnt,
    revenue_amount,
    round(avg_rental_duration_min::numeric, 2) as avg_duration_min
FROM mart.kpi_daily 
ORDER BY day DESC 
LIMIT 5;
"

echo ""
echo "=== Проверка завершена ==="


