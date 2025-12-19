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

## Шаг 4: Автоматическая настройка (РЕКОМЕНДУЕТСЯ)

```bash
# Один скрипт делает всё: connections, права, включение DAG-ов, Grafana
chmod +x scripts/setup_dwh.sh
./scripts/setup_dwh.sh
```

Скрипт автоматически:
- ✅ Создаёт Airflow connections (dwh_db, rental_db, billing_db)
- ✅ Исправляет права на `/opt/airflow/artifacts`
- ✅ Включает все DAG-и
- ✅ Настраивает Grafana datasource и импортирует дашборд

**Если хотите вручную** — см. раздел "Ручная настройка" в конце документа.

## Шаг 5: Создать тестовые данные

```bash
# Автоматический скрипт
chmod +x scripts/create_test_data.sh
./scripts/create_test_data.sh
```

Или восстановить из готового дампа (быстрее):
```bash
cat dwh/artifacts/dwh_dump.sql | docker exec -i db-dwh psql -U dwh -d dwh
```

## Шаг 6: Запустить ETL

```bash
# Запустить ETL (DAG-и уже включены скриптом setup_dwh.sh)
docker exec airflow-webserver airflow dags trigger dwh_powerbank_etl
```

Или запустить мастер-DAG (вызовет все 4 под-DAG-а):
```bash
docker exec airflow-webserver airflow dags trigger dwh_master
```

## Шаг 7: Проверить результат

Подождать ~30 секунд и проверить:

```bash
# Статус DAG-а
docker exec airflow-webserver airflow dags list-runs -d dwh_powerbank_etl

# Данные в DWH
docker exec db-dwh psql -U dwh -d dwh -c "SELECT * FROM mart.kpi_daily;"
```

## Шаг 8: Проверить Grafana дашборд

Grafana уже настроена скриптом `setup_dwh.sh`. Просто откройте:

**http://localhost:3000/d/dwh-kpi-dashboard** (admin/admin)

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

## FAQ / Troubleshooting

### ❓ Airflow connections не найдены

**Симптом:** DAG падает с ошибкой "connection not found"

**Решение:**
```bash
# Проверить существующие connections
docker exec airflow-webserver airflow connections list

# Запустить скрипт настройки (создаст connections)
./scripts/setup_dwh.sh
```

### ❓ DAG падает на load_raw с ошибкой "relation does not exist"

**Симптом:** `psycopg2.errors.UndefinedTable: relation "public.rentals" does not exist`

**Причина:** В источниках (rental/billing) нет таблиц — нужно запустить миграции или создать данные.

**Решение:**
```bash
# Проверить таблицы в источниках
docker exec sysdesign-hw-1-db-rental-1 psql -U app -d rental -c "\dt"
docker exec sysdesign-hw-1-db-billing-1 psql -U app -d billing -c "\dt"

# Если таблиц нет — создать тестовые данные
./scripts/create_test_data.sh
```

### ❓ export_artifacts падает с PermissionError

**Симптом:** `PermissionError: [Errno 13] Permission denied: '/opt/airflow/artifacts/...'`

**Причина:** Директория `/opt/airflow/artifacts` принадлежит root, а Airflow работает под пользователем airflow.

**Решение:**
```bash
docker exec -u root airflow-scheduler chmod -R 777 /opt/airflow/artifacts
```

Или запустите `./scripts/setup_dwh.sh` — он исправляет права автоматически.

### ❓ Grafana не показывает данные

**Симптомы:** 
- Панели показывают "No data"
- Ошибка "datasource not found"

**Решение:**
```bash
# 1. Проверить, что datasource создан
curl -s -u admin:admin http://localhost:3000/api/datasources | python3 -m json.tool

# 2. Если нет — создать
./scripts/setup_dwh.sh

# 3. Проверить, что данные есть в DWH
docker exec db-dwh psql -U dwh -d dwh -c "SELECT * FROM mart.kpi_daily;"
```

### ❓ Контейнеры не стартуют / падают

**Решение:**
```bash
# Посмотреть логи
docker logs airflow-webserver --tail 50
docker logs airflow-scheduler --tail 50
docker logs db-dwh --tail 50

# Перезапустить всё
docker compose -f docker-compose.yml -f docker-compose.dwh.yml down
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d --build
```

### ❓ "Connection refused" при создании тестовых данных

**Симптом:** `curl: (7) Failed to connect to localhost port 8000`

**Причина:** rental-core ещё не запустился или упал.

**Решение:**
```bash
# Проверить статус
docker ps | grep rental-core

# Посмотреть логи
docker logs sysdesign-hw-1-rental-core-1 --tail 30

# Подождать и попробовать снова
sleep 10
curl http://localhost:8000/api/v1/health
```

### ❓ DAG-и не появляются в Airflow UI

**Причина:** Airflow scheduler ещё не прочитал файлы DAG-ов.

**Решение:**
```bash
# Подождать 30-60 секунд или перезапустить scheduler
docker restart airflow-scheduler

# Проверить, что DAG-и загружены
docker exec airflow-webserver airflow dags list | grep dwh
```

---

## Ручная настройка (если скрипт не работает)

### Создание Airflow Connections вручную

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

### Включение DAG-ов вручную

```bash
docker exec airflow-webserver airflow dags unpause dwh_powerbank_etl
docker exec airflow-webserver airflow dags unpause dwh_master
docker exec airflow-webserver airflow dags unpause dwh_raw_extract_rental
docker exec airflow-webserver airflow dags unpause dwh_raw_extract_billing
docker exec airflow-webserver airflow dags unpause dwh_core_build
docker exec airflow-webserver airflow dags unpause dwh_mart_build
```

### Настройка Grafana вручную

```bash
# Добавить datasource
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

