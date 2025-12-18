# SysDesign HW-1 — DWH + Airflow ETL

## Структура репозитория

```
dwh/
  sql/
    00_schemas.sql      # Создание схем (raw_rental, raw_billing, core, mart, meta)
    01_raw.sql          # DDL для RAW слоя
    02_core.sql         # Трансформация RAW → CORE
    03_mart.sql         # Построение витрин MART + KPI
    04_meta.sql         # Метаданные ETL (audit, watermarks)
  dags/
    dwh_master.py              # Мастер-DAG (оркестрация)
    dwh_raw_extract_rental.py  # DAG A: загрузка из rental
    dwh_raw_extract_billing.py # DAG B: загрузка из billing
    dwh_core_build.py          # DAG C: построение CORE
    dwh_mart_build.py          # DAG D: построение MART + экспорт
    dwh_etl_powerbank.py       # Legacy монолитный DAG
  artifacts/
    dwh_dump.sql               # Полный дамп DWH
    dwh_schema_only.sql        # Только схема
    mart_*.csv                 # CSV снимки витрин
    README.md                  # Инструкция по восстановлению
scripts/
  dump_dwh.sh                  # Создание дампа
  restore_dwh.sh               # Восстановление из дампа
  check_dwh_data.sh            # Проверка данных
docs/
  dwh_tables.md                # Документация по таблицам
```

---

## Инфраструктура

В docker-compose добавлены:

* **db-dwh** — Postgres для DWH (порт 5444)
* **airflow-db** — Postgres для метаданных Airflow
* **airflow-init** — инициализация Airflow (миграции + admin user)
* **airflow-webserver** — Airflow UI (порт 8080)
* **airflow-scheduler** — планировщик DAG-ов

Airflow connections (настроены автоматически):

* `rental_db` → `db-rental:5432/rental`
* `billing_db` → `db-billing:5432/billing`
* `dwh_db` → `db-dwh:5432/dwh`

---

## Запуск проекта

### Требования

* Docker + Docker Compose

### 1. Поднять инфраструктуру

```bash
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d --build
```

Проверка:

```bash
docker ps
```

### 2. Airflow UI

Открыть в браузере: http://localhost:8080

Логин / пароль: `admin / admin`

---

## DAG-и ETL

### Архитектура DAG-ов

```
dwh_master (оркестратор)
├── dwh_raw_extract_rental (DAG A)  ─┐
├── dwh_raw_extract_billing (DAG B) ─┼─ параллельно
│                                    │
├── dwh_core_build (DAG C)          ─┘ после RAW
│
└── dwh_mart_build (DAG D)          ─  после CORE
```

### DAG A: dwh_raw_extract_rental
- Загружает данные из `db-rental` в `raw_rental.*`
- Таблицы: `quotes`, `rentals`, `idempotency_keys`
- Стратегия: truncate + insert (full load)

### DAG B: dwh_raw_extract_billing
- Загружает данные из `db-billing` в `raw_billing.*`
- Таблицы: `debts`, `payment_attempts`
- **SoT (Source of Truth)** для платежей и долгов!

### DAG C: dwh_core_build
- Строит CORE слой из RAW данных
- Соблюдает SoT: `core.debts` и `core.payment_attempts` только из billing

### DAG D: dwh_mart_build
- Строит витрины: `mart.fct_rentals`, `mart.fct_payments`
- Вычисляет KPI: `mart.kpi_daily` (6 метрик)
- Экспортирует CSV артефакты

---

## Запуск ETL

### Рекомендуемый способ: Мастер-DAG

```bash
# Через Airflow UI
1. Открыть DAG "dwh_master"
2. Включить DAG (toggle)
3. Нажать "Trigger DAG"

# Через CLI
docker exec -it airflow-webserver airflow dags trigger dwh_master
```

### Альтернатива: Legacy DAG

```bash
docker exec -it airflow-webserver airflow dags trigger dwh_powerbank_etl
```

### Проверка статуса

```bash
docker exec -it airflow-webserver airflow dags list-runs -d dwh_master
```

---

## Проверка данных в DWH

### Скрипт проверки (рекомендуется)

```bash
./scripts/check_dwh_data.sh
```

### Вручную

```bash
docker exec -it db-dwh psql -U dwh -d dwh
```

```sql
-- RAW слой
SELECT count(*) FROM raw_rental.rentals;
SELECT count(*) FROM raw_billing.payment_attempts;

-- CORE слой
SELECT count(*) FROM core.rentals;

-- MART слой
SELECT count(*) FROM mart.kpi_daily;

-- KPI данные
SELECT * FROM mart.kpi_daily ORDER BY day DESC LIMIT 5;
```

---

## Дамп и восстановление DWH

### Создание дампа

```bash
./scripts/dump_dwh.sh
```

Создаёт:
- `dwh/artifacts/dwh_dump.sql` — полный дамп
- `dwh/artifacts/dwh_schema_only.sql` — только схема

### Восстановление из дампа

```bash
./scripts/restore_dwh.sh
```

Или вручную:
```bash
cat dwh/artifacts/dwh_dump.sql | docker exec -i db-dwh psql -U dwh -d dwh
```

---

## KPI в mart.kpi_daily

| Метрика | Описание |
|---------|----------|
| `quotes_cnt` | Количество созданных квот |
| `rentals_started_cnt` | Количество начатых аренд |
| `rentals_finished_cnt` | Количество завершённых аренд |
| `payments_attempts_cnt` | Количество попыток оплаты |
| `payments_success_cnt` | Количество успешных оплат |
| `revenue_amount` | Выручка (сумма успешных платежей) |
| `avg_rental_duration_min` | Средняя длительность аренды (мин) |

---

## Статус задания

- [x] Структура репозитория зафиксирована
- [x] Инфраструктура DWH и Airflow поднята через docker-compose
- [x] Слои DWH и таблицы созданы (DDL)
- [x] ETL разделён на 4 DAG-а + мастер-DAG
- [x] Скрипты для дампа/восстановления DWH
- [ ] Успешный прогон ETL с данными
- [ ] Дамп DWH с данными
