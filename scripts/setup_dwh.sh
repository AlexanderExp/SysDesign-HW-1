#!/bin/bash
# Скрипт автоматической настройки DWH
# Запускать ПОСЛЕ docker compose up -d
# Использование: ./scripts/setup_dwh.sh

set -e

echo "========================================"
echo "  DWH Setup Script"
echo "========================================"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
GRAFANA_URL="http://localhost:3000"
GRAFANA_AUTH="admin:admin"
DWH_DATASOURCE_UID="dwh-postgres"

# Функция проверки
check_ok() {
    echo -e "${GREEN}✓ $1${NC}"
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# ============================================
# Шаг 1: Проверка контейнеров
# ============================================
echo "Шаг 1: Проверка контейнеров..."

if ! docker ps | grep -q "airflow-webserver"; then
    check_fail "airflow-webserver не запущен!"
    echo "Запустите: docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d"
    exit 1
fi
check_ok "airflow-webserver запущен"

if ! docker ps | grep -q "airflow-scheduler"; then
    check_fail "airflow-scheduler не запущен!"
    exit 1
fi
check_ok "airflow-scheduler запущен"

if ! docker ps | grep -q "db-dwh"; then
    check_fail "db-dwh не запущен!"
    exit 1
fi
check_ok "db-dwh запущен"

# Ждём готовности Airflow
echo ""
echo "Ожидание готовности Airflow (до 60 сек)..."
for i in {1..12}; do
    if docker exec airflow-webserver airflow db check 2>/dev/null; then
        check_ok "Airflow готов"
        break
    fi
    if [ $i -eq 12 ]; then
        check_fail "Airflow не готов за 60 секунд"
        exit 1
    fi
    sleep 5
done

# ============================================
# Шаг 2: Создание Airflow Connections
# ============================================
echo ""
echo "Шаг 2: Создание Airflow Connections..."

# DWH
if docker exec airflow-webserver airflow connections get dwh_db 2>/dev/null | grep -q "dwh_db"; then
    check_warn "dwh_db уже существует, пропускаем"
else
    docker exec airflow-webserver airflow connections add dwh_db \
        --conn-type postgres \
        --conn-host db-dwh \
        --conn-port 5432 \
        --conn-login dwh \
        --conn-password dwh \
        --conn-schema dwh 2>/dev/null
    check_ok "dwh_db создан"
fi

# Rental
if docker exec airflow-webserver airflow connections get rental_db 2>/dev/null | grep -q "rental_db"; then
    check_warn "rental_db уже существует, пропускаем"
else
    docker exec airflow-webserver airflow connections add rental_db \
        --conn-type postgres \
        --conn-host db-rental \
        --conn-port 5432 \
        --conn-login app \
        --conn-password app \
        --conn-schema rental 2>/dev/null
    check_ok "rental_db создан"
fi

# Billing
if docker exec airflow-webserver airflow connections get billing_db 2>/dev/null | grep -q "billing_db"; then
    check_warn "billing_db уже существует, пропускаем"
else
    docker exec airflow-webserver airflow connections add billing_db \
        --conn-type postgres \
        --conn-host db-billing \
        --conn-port 5432 \
        --conn-login app \
        --conn-password app \
        --conn-schema billing 2>/dev/null
    check_ok "billing_db создан"
fi

# ============================================
# Шаг 3: Исправление прав доступа
# ============================================
echo ""
echo "Шаг 3: Исправление прав доступа..."

# Права на директорию артефактов
docker exec -u root airflow-scheduler mkdir -p /opt/airflow/artifacts 2>/dev/null || true
docker exec -u root airflow-scheduler chmod -R 777 /opt/airflow/artifacts 2>/dev/null || true
check_ok "Права на /opt/airflow/artifacts исправлены"

# ============================================
# Шаг 4: Включение DAG-ов
# ============================================
echo ""
echo "Шаг 4: Включение DAG-ов..."

docker exec airflow-webserver airflow dags unpause dwh_powerbank_etl 2>/dev/null || true
check_ok "dwh_powerbank_etl включен"

docker exec airflow-webserver airflow dags unpause dwh_master 2>/dev/null || true
check_ok "dwh_master включен"

docker exec airflow-webserver airflow dags unpause dwh_raw_extract_rental 2>/dev/null || true
docker exec airflow-webserver airflow dags unpause dwh_raw_extract_billing 2>/dev/null || true
docker exec airflow-webserver airflow dags unpause dwh_core_build 2>/dev/null || true
docker exec airflow-webserver airflow dags unpause dwh_mart_build 2>/dev/null || true
check_ok "Все DAG-и включены"

# ============================================
# Шаг 5: Настройка Grafana
# ============================================
echo ""
echo "Шаг 5: Настройка Grafana..."

# Проверяем, есть ли уже datasource
GRAFANA_DS_PAYLOAD=$(cat <<EOF
{
    "name": "DWH PostgreSQL",
    "type": "postgres",
    "uid": "$DWH_DATASOURCE_UID",
    "url": "db-dwh:5432",
    "database": "dwh",
    "user": "dwh",
    "secureJsonData": {"password": "dwh"},
    "jsonData": {"sslmode": "disable"},
    "access": "proxy"
}
EOF
)

DS_INFO=$(curl -s -u "$GRAFANA_AUTH" "$GRAFANA_URL/api/datasources/name/DWH%20PostgreSQL" 2>/dev/null || true)
if echo "$DS_INFO" | grep -q '"id"'; then
    DS_ID=$(echo "$DS_INFO" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
    curl -s -u "$GRAFANA_AUTH" -X PUT "$GRAFANA_URL/api/datasources/$DS_ID" \
        -H "Content-Type: application/json" \
        -d "$GRAFANA_DS_PAYLOAD" >/dev/null 2>&1
    check_ok "Grafana datasource обновлен"
else
    curl -s -u "$GRAFANA_AUTH" -X POST "$GRAFANA_URL/api/datasources" \
        -H "Content-Type: application/json" \
        -d "$GRAFANA_DS_PAYLOAD" >/dev/null 2>&1
    check_ok "Grafana datasource создан"
fi

# Импорт дашборда
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DASHBOARD_FILE="$PROJECT_DIR/monitoring/grafana/provisioning/dashboards/dwh-kpi-dashboard.json"

if [ -f "$DASHBOARD_FILE" ]; then
    curl -s -u admin:admin -X POST http://localhost:3000/api/dashboards/db \
        -H "Content-Type: application/json" \
        -d "{
            \"dashboard\": $(cat "$DASHBOARD_FILE"),
            \"overwrite\": true
        }" >/dev/null 2>&1
    check_ok "Grafana дашборд импортирован"
else
    check_warn "Файл дашборда не найден: $DASHBOARD_FILE"
fi

# ============================================
# Готово!
# ============================================
echo ""
echo "========================================"
echo -e "${GREEN}  Настройка завершена!${NC}"
echo "========================================"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Создать тестовые данные (если нужно):"
echo "   ./scripts/create_test_data.sh"
echo ""
echo "2. Или восстановить из дампа:"
echo "   cat dwh/artifacts/dwh_dump.sql | docker exec -i db-dwh psql -U dwh -d dwh"
echo ""
echo "3. Запустить ETL:"
echo "   docker exec airflow-webserver airflow dags trigger dwh_powerbank_etl"
echo ""
echo "4. Открыть UI:"
echo "   - Airflow: http://localhost:8080 (admin/admin)"
echo "   - Grafana: http://localhost:3000 (admin/admin)"
echo ""
