#!/bin/bash
# Скрипт создания тестовых данных
# Использование: ./scripts/create_test_data.sh

set -e

echo "========================================"
echo "  Создание тестовых данных"
echo "========================================"
echo ""

# Проверяем, что rental-core доступен
if ! curl -s http://localhost:8000/api/v1/health | grep -q "ok"; then
    echo "ОШИБКА: rental-core не доступен на localhost:8000"
    echo "Убедитесь, что контейнеры запущены:"
    echo "  docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d"
    exit 1
fi

echo "rental-core доступен ✓"
echo ""

# Создаём несколько аренд
echo "Создание аренд..."
for i in {1..5}; do
    echo -n "  Аренда $i: "
    
    # Создаём квоту
    QJSON=$(curl -s -X POST http://localhost:8000/api/v1/rentals/quote \
        -H "Content-Type: application/json" \
        -d "{\"station_id\":\"station-$i\",\"user_id\":\"user-$i\"}")
    
    # Проверяем ответ
    if echo "$QJSON" | grep -q "quote_id"; then
        QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
        
        # Создаём аренду
        IDEMP=$(python3 -c 'import uuid; print(uuid.uuid4())')
        SJSON=$(curl -s -X POST http://localhost:8000/api/v1/rentals/start \
            -H "Content-Type: application/json" \
            -H "Idempotency-Key: $IDEMP" \
            -d "{\"quote_id\":\"$QID\"}")
        
        if echo "$SJSON" | grep -q "order_id"; then
            OID=$(echo "$SJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')
            echo "OK (order_id: ${OID:0:8}...)"
        else
            echo "ОШИБКА при создании аренды"
        fi
    else
        echo "ОШИБКА при создании квоты"
    fi
    
    sleep 1
done

echo ""
echo "Ожидание обработки платежей (30 сек)..."
sleep 30

# Проверяем результат
echo ""
echo "========================================"
echo "  Проверка данных"
echo "========================================"
echo ""

echo "Rental DB:"
docker exec system-design-db-rental-1 psql -U app -d rental -t -c \
    "SELECT '  rentals: ' || count(*) FROM rentals;"
docker exec system-design-db-rental-1 psql -U app -d rental -t -c \
    "SELECT '  quotes: ' || count(*) FROM quotes;"

echo ""
echo "Billing DB:"
docker exec system-design-db-billing-1 psql -U app -d billing -t -c \
    "SELECT '  payment_attempts: ' || count(*) FROM payment_attempts;"

echo ""
echo "========================================"
echo "  Готово!"
echo "========================================"
echo ""
echo "Теперь запустите ETL:"
echo "  docker exec airflow-webserver airflow dags trigger dwh_powerbank_etl"
echo ""

