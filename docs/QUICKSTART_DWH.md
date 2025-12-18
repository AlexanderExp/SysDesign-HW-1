# DWH Quick Start — Запуск с нуля

Эта инструкция позволяет запустить весь DWH с нуля на чистой машине.

## Требования

- Docker + Docker Compose
- Git

## Шаг 1: Клонировать репозиторий

```bash
git clone https://github.com/AlexanderExp/SysDesign-HW-1.git
cd SysDesign-HW-1
git checkout feature/dwh-etl-complete
```

## Шаг 2: Создать .env файл

```bash
cat > .env << 'EOF'
DATABASE_URL=postgresql+psycopg2://app:app@db-rental:5432/rental
BILLING_DATABASE_URL=postgresql+psycopg2://app:app@db-billing:5432/billing
EXTERNAL_BASE=http://external-stubs:3629
TARIFF_TTL_SEC=600
CONFIG_REFRESH_SEC=60
BILLING_TICK_SEC=10
R_BUYOUT=5000
DEBT_CHARGE_STEP=100
DEBT_RETRY_BASE_SEC=60
DEBT_RETRY_MAX_SEC=3600
HTTP_TIMEOUT_SEC=1.5
CB_STATION_FAIL_MAX=5
CB_STATION_RESET_TIMEOUT=30
CB_PAYMENT_FAIL_MAX=3
CB_PAYMENT_RESET_TIMEOUT=60
CB_PROFILE_FAIL_MAX=10
CB_PROFILE_RESET_TIMEOUT=15
EOF
```

## Шаг 3: Запустить инфраструктуру

```bash
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d --build
```

Дождаться запуска всех контейнеров (~2-3 минуты):

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Должны быть запущены:
- `db-dwh` (healthy)
- `airflow-webserver`
- `airflow-scheduler`
- `airflow-db` (healthy)
- `sysdesign-hw-1-db-rental-1` (healthy)
- `sysdesign-hw-1-db-billing-1` (healthy)

## Шаг 4: Создать Airflow Connections

```bash
# DWH database
docker exec airflow-webserver airflow connections add dwh_db \
  --conn-type postgres \
  --conn-host db-dwh \
  --conn-port 5432 \
  --conn-login dwh \
  --conn-password dwh \
  --conn-schema dwh

# Rental database
docker exec airflow-webserver airflow connections add rental_db \
  --conn-type postgres \
  --conn-host db-rental \
  --conn-port 5432 \
  --conn-login app \
  --conn-password app \
  --conn-schema rental

# Billing database
docker exec airflow-webserver airflow connections add billing_db \
  --conn-type postgres \
  --conn-host db-billing \
  --conn-port 5432 \
  --conn-login app \
  --conn-password app \
  --conn-schema billing
```

## Шаг 5: Создать тестовые данные

```bash
# Создать несколько аренд через API
for i in {1..3}; do
  QJSON=$(curl -s -X POST http://localhost:8000/api/v1/rentals/quote \
    -H "Content-Type: application/json" \
    -d "{\"station_id\":\"station-$i\",\"user_id\":\"user-$i\"}")
  QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
  
  IDEMP=$(python3 -c 'import uuid; print(uuid.uuid4())')
  curl -s -X POST http://localhost:8000/api/v1/rentals/start \
    -H "Content-Type: application/json" \
    -H "Idempotency-Key: $IDEMP" \
    -d "{\"quote_id\":\"$QID\"}"
  
  sleep 2
done
echo "Тестовые данные созданы"
```

## Шаг 6: Включить и запустить ETL

```bash
# Включить DAG-и
docker exec airflow-webserver airflow dags unpause dwh_powerbank_etl

# Исправить права на директорию артефактов
docker exec -u root airflow-scheduler chmod -R 777 /opt/airflow/artifacts

# Запустить ETL
docker exec airflow-webserver airflow dags trigger dwh_powerbank_etl
```

## Шаг 7: Проверить результат

Подождать ~30 секунд и проверить:

```bash
# Статус DAG-а
docker exec airflow-webserver airflow dags list-runs -d dwh_powerbank_etl

# Данные в DWH
docker exec db-dwh psql -U dwh -d dwh -c "SELECT * FROM mart.kpi_daily;"
```

## Шаг 8: Настроить Grafana дашборд

```bash
# Добавить datasource для DWH
curl -s -u admin:admin -X POST http://localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DWH PostgreSQL",
    "type": "postgres",
    "url": "db-dwh:5432",
    "database": "dwh",
    "user": "dwh",
    "secureJsonData": {"password": "dwh"},
    "jsonData": {"sslmode": "disable"},
    "access": "proxy"
  }'

# Импортировать дашборд
curl -s -u admin:admin -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d "{
    \"dashboard\": $(cat monitoring/grafana/provisioning/dashboards/dwh-kpi-dashboard.json),
    \"overwrite\": true
  }"
```

## Готово!

Открыть в браузере:

| Сервис | URL | Логин/Пароль |
|--------|-----|--------------|
| **Airflow UI** | http://localhost:8080 | admin / admin |
| **Grafana** | http://localhost:3000 | admin / admin |
| **DWH Dashboard** | http://localhost:3000/d/dwh-kpi-dashboard | admin / admin |

---

## Альтернатива: Восстановить из дампа

Если не хочется создавать тестовые данные, можно восстановить DWH из готового дампа:

```bash
# После шага 3 (запуск инфраструктуры)
cat dwh/artifacts/dwh_dump.sql | docker exec -i db-dwh psql -U dwh -d dwh

# Проверить
docker exec db-dwh psql -U dwh -d dwh -c "SELECT * FROM mart.kpi_daily;"
```

---

## Полезные команды

```bash
# Проверить данные
./scripts/check_dwh_data.sh

# Создать дамп
./scripts/dump_dwh.sh

# Восстановить из дампа
./scripts/restore_dwh.sh

# Логи Airflow
docker logs airflow-scheduler --tail 50

# Подключиться к DWH
docker exec -it db-dwh psql -U dwh -d dwh
```

---

## Troubleshooting

### Airflow connections не найдены
```bash
# Проверить
docker exec airflow-webserver airflow connections list

# Пересоздать (см. Шаг 4)
```

### DAG падает на load_raw
Проверить, что таблицы в источниках существуют:
```bash
docker exec sysdesign-hw-1-db-rental-1 psql -U app -d rental -c "\dt"
docker exec sysdesign-hw-1-db-billing-1 psql -U app -d billing -c "\dt"
```

### export_artifacts падает с PermissionError
```bash
docker exec -u root airflow-scheduler chmod -R 777 /opt/airflow/artifacts
```

### Grafana не показывает данные
1. Проверить datasource: Settings → Data Sources → DWH PostgreSQL → Test
2. Проверить, что данные есть: `docker exec db-dwh psql -U dwh -d dwh -c "SELECT * FROM mart.kpi_daily;"`

