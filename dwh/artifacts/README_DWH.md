# SysDesign HW-1 — DWH + Airflow ETL

## Структура репозитория

```
dwh/
  sql/
    00_schemas.sql
    00_billing_init.sql
    01_raw.sql
    02_core.sql
    03_mart.sql
    04_meta.sql
  dags/
    dwh_etl_powerbank.py
  artifacts/
    (CSV "снимки", генерируются Airflow)
docs/
  dwh_schema.md
  tables.md
```

* **dwh/sql/** — DDL и SQL-трансформации по слоям RAW / CORE / MART + META
* **dwh/dags/** — Airflow DAG `dwh_powerbank_etl`
* **dwh/artifacts/** — статические “снимки” (CSV), генерируются задачей `export_artifacts`
* **docs/** — документация по таблицам и схема DWH

---

## Инфраструктура

В docker-compose добавлены:

* **db-dwh** — Postgres для DWH
* **airflow-db** — Postgres для метаданных Airflow
* **airflow-init** — инициализация Airflow (миграции + admin user)
* **airflow-webserver** — Airflow UI
* **airflow-scheduler** — планировщик DAG-ов

Airflow connections:

* `rental_db` → Postgres `db-rental` (база `rental`)
* `billing_db` → Postgres `db-billing` (база `billing`)
* `dwh_db` → Postgres `db-dwh` (база `dwh`)

ETL **не выполняется вручную** — весь процесс запускается и контролируется через Airflow.

---

## Запуск проекта

### Требования

* Docker + Docker Compose
* (macOS) Colima или Docker Desktop

### 1. Поднять инфраструктуру

```bash
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d --build
```

Проверка:

```bash
docker ps
```

### 2. Airflow UI

Открыть в браузере:

```
http://localhost:8080
```

Логин / пароль:

```
admin / admin
```

---

## Запуск ETL

### Через Airflow UI

1. Открыть DAG **dwh_powerbank_etl**
2. Включить DAG (toggle)
3. Нажать **Trigger DAG**

### Через CLI

```bash
docker exec -it airflow-webserver airflow dags trigger dwh_powerbank_etl
```

Посмотреть прогоны:

```bash
docker exec -it airflow-webserver airflow dags list-runs -d dwh_powerbank_etl
```

Статусы задач конкретного run:

```bash
docker exec -it airflow-webserver airflow tasks states-for-dag-run \
  dwh_powerbank_etl 'manual__YYYY-MM-DDTHH:MM:SS+00:00'
```

Ожидаемый результат — **все задачи в состоянии `success`**.

---

## Логика DAG

DAG `dwh_powerbank_etl` состоит из следующих шагов:

1. **dwh_bootstrap** — создание схем и DDL в DWH
2. **init_billing_source** — инициализация таблиц в источнике billing (если отсутствуют)
3. **load_raw** — full-load загрузка данных из источников в RAW слой
4. **build_core** — построение CORE слоя
5. **build_mart** — построение витрин и KPI
6. **export_artifacts** — экспорт витрин в CSV

---

## Проверка данных в DWH

Подключиться к DWH:

```bash
docker exec -it db-dwh psql -U dwh -d dwh
```

Проверить витрины:

```sql
\dt mart.*;
select count(*) from mart.fct_rentals;
select count(*) from mart.fct_payments;
select * from mart.kpi_daily order by day desc limit 10;
```

---

## Artifacts (CSV)

CSV-файлы создаются задачей `export_artifacts` и хранятся внутри Airflow в:

```
/opt/airflow/artifacts
```

Скопировать файлы в репозиторий:

```bash
mkdir -p dwh/artifacts
docker cp airflow-webserver:/opt/airflow/artifacts/. dwh/artifacts/
```

---

## Статус задания

* Структура репозитория зафиксирована ✅
* Инфраструктура DWH и Airflow поднята через docker-compose ✅
* ETL запускается из Airflow UI и завершается зелёным прогоном ✅
