# DWH — Инструкция к защите

## Глоссарий терминов

| Термин | Определение |
|--------|-------------|
| **DWH (Data Warehouse)** | Хранилище данных — централизованная база для аналитики, куда собираются данные из разных источников |
| **ETL (Extract-Transform-Load)** | Процесс извлечения данных из источников, их преобразования и загрузки в хранилище |
| **RAW слой** | "Сырой" слой — копия данных из источников 1:1, без преобразований |
| **CORE слой** | Ядро — очищенные и нормализованные данные, готовые для построения витрин |
| **MART слой** | Витрины — денормализованные таблицы для аналитики и отчётов |
| **META слой** | Метаданные — информация об ETL-процессах (аудит, watermarks) |
| **SoT (Source of Truth)** | Источник истины — единственный авторитетный источник данных для сущности |
| **DAG (Directed Acyclic Graph)** | Направленный ациклический граф — описание ETL-пайплайна в Airflow |
| **Airflow** | Платформа для оркестрации ETL-процессов (планирование, мониторинг, retry) |
| **Full Load** | Полная загрузка — стратегия ETL, когда данные полностью перезаписываются |
| **Incremental Load** | Инкрементальная загрузка — загружаются только новые/изменённые данные |
| **Watermark** | Метка времени последней успешной загрузки (для incremental) |
| **KPI (Key Performance Indicator)** | Ключевые показатели эффективности — метрики для бизнес-анализа |

---

## Что сделано

### 1. Структура репозитория

```
dwh/
├── sql/                          # DDL и SQL-трансформации
│   ├── 00_schemas.sql           # Создание схем
│   ├── 01_raw.sql               # RAW таблицы
│   ├── 02_core.sql              # CORE трансформации
│   ├── 03_mart.sql              # MART витрины
│   └── 04_meta.sql              # META таблицы
├── dags/                         # Airflow DAG-и
│   ├── dwh_master.py            # Мастер-DAG (оркестратор)
│   ├── dwh_raw_extract_rental.py    # DAG A
│   ├── dwh_raw_extract_billing.py   # DAG B
│   ├── dwh_core_build.py            # DAG C
│   ├── dwh_mart_build.py            # DAG D
│   └── dwh_etl_powerbank.py         # Legacy монолитный DAG
└── artifacts/                    # Статические артефакты
    ├── dwh_dump.sql             # Полный дамп DWH
    ├── dwh_schema_only.sql      # Только схема
    ├── mart_kpi_daily.csv       # CSV витрины KPI
    └── README.md                # Инструкция по восстановлению
```

### 2. Инфраструктура (docker-compose.dwh.yml)

| Сервис | Назначение | Порт |
|--------|------------|------|
| `db-dwh` | PostgreSQL для DWH | 5444 |
| `airflow-db` | PostgreSQL для метаданных Airflow | — |
| `airflow-webserver` | Web UI Airflow | 8080 |
| `airflow-scheduler` | Планировщик DAG-ов | — |

### 3. Слои DWH

#### RAW (сырые данные)
- `raw_rental.quotes` — котировки
- `raw_rental.rentals` — аренды
- `raw_rental.idempotency_keys` — ключи идемпотентности
- `raw_billing.debts` — долги
- `raw_billing.payment_attempts` — попытки оплаты

#### CORE (очищенные данные)
- `core.quotes`, `core.rentals`, `core.idempotency_keys` ← из rental
- `core.debts`, `core.payment_attempts` ← из billing (**SoT!**)

#### MART (витрины)
- `mart.fct_rentals` — факты по арендам
- `mart.fct_payments` — факты по платежам
- `mart.kpi_daily` — ежедневные KPI (6 метрик)

#### META (метаданные)
- `meta.etl_run_audit` — аудит запусков ETL
- `meta.etl_watermark` — watermarks для incremental

### 4. DAG-и ETL

```
dwh_master (оркестратор, @daily)
├── dwh_raw_extract_rental (DAG A)  ─┐
├── dwh_raw_extract_billing (DAG B) ─┼─ параллельно
│                                    │
├── dwh_core_build (DAG C)          ─┘ после RAW
│
└── dwh_mart_build (DAG D)          ─  после CORE
```

**Важно:** SoT для платежей и долгов — только billing!

### 5. KPI в mart.kpi_daily

| Метрика | Описание |
|---------|----------|
| `quotes_cnt` | Количество созданных квот за день |
| `rentals_started_cnt` | Количество начатых аренд |
| `rentals_finished_cnt` | Количество завершённых аренд |
| `payments_attempts_cnt` | Количество попыток оплаты |
| `payments_success_cnt` | Количество успешных оплат |
| `revenue_amount` | Выручка (сумма успешных платежей) |
| `avg_rental_duration_min` | Средняя длительность аренды (мин) |

---

## Что говорить на защите

### Архитектура DWH

> "DWH построен по классической многослойной архитектуре:
> - **RAW** — сырые данные 1:1 из источников
> - **CORE** — очищенные данные, здесь соблюдается SoT
> - **MART** — денормализованные витрины для аналитики
> - **META** — метаданные ETL-процессов"

### Source of Truth

> "Для платежей и долгов единственный источник истины — billing-сервис. 
> В CORE слое `core.debts` и `core.payment_attempts` загружаются только из `raw_billing`, 
> даже если в rental есть похожие данные."

### ETL-процесс

> "ETL реализован в Airflow как набор DAG-ов:
> - Мастер-DAG оркестрирует весь процесс
> - RAW DAG-и загружают данные параллельно из rental и billing
> - CORE DAG строит очищенный слой
> - MART DAG вычисляет витрины и KPI
> 
> Используется стратегия full-load (truncate + insert) — подходит для небольших объёмов данных."

### Почему Airflow

> "Airflow выбран потому что:
> - Визуализация ETL-процессов в UI
> - Автоматические retry при ошибках
> - Планирование по расписанию
> - Мониторинг и алерты
> - Dependency management между задачами"

---

## Что показывать

### 1. Airflow UI

Открыть: http://localhost:8080 (admin/admin)

Показать:
- Список DAG-ов (dwh_master, dwh_raw_extract_*, dwh_core_build, dwh_mart_build)
- Граф зависимостей dwh_master
- Успешный прогон (зелёные задачи)

### 2. Данные в DWH

```bash
# Подключиться к DWH
docker exec -it db-dwh psql -U dwh -d dwh
```

```sql
-- Проверить количество записей
SELECT count(*) FROM raw_rental.rentals;
SELECT count(*) FROM raw_billing.payment_attempts;
SELECT count(*) FROM core.rentals;
SELECT count(*) FROM mart.kpi_daily;

-- Показать KPI
SELECT * FROM mart.kpi_daily ORDER BY day DESC LIMIT 5;

-- Показать структуру таблиц
\dt raw_rental.*;
\dt core.*;
\dt mart.*;
```

### 3. DDL файлы

Показать структуру SQL файлов:
- `dwh/sql/00_schemas.sql` — создание схем
- `dwh/sql/01_raw.sql` — RAW таблицы
- `dwh/sql/03_mart.sql` — витрины и KPI

### 4. Артефакты

```bash
# Показать дамп
ls -la dwh/artifacts/

# Показать CSV
cat dwh/artifacts/mart_kpi_daily.csv
```

---

## Как запускать

### 1. Поднять инфраструктуру

```bash
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d --build
```

### 2. Проверить контейнеры

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Должны быть запущены:
- db-dwh
- airflow-webserver
- airflow-scheduler
- airflow-db

### 3. Создать Airflow connections (если нужно)

```bash
docker exec airflow-webserver airflow connections add dwh_db \
  --conn-type postgres --conn-host db-dwh --conn-port 5432 \
  --conn-login dwh --conn-password dwh --conn-schema dwh

docker exec airflow-webserver airflow connections add rental_db \
  --conn-type postgres --conn-host db-rental --conn-port 5432 \
  --conn-login app --conn-password app --conn-schema rental

docker exec airflow-webserver airflow connections add billing_db \
  --conn-type postgres --conn-host db-billing --conn-port 5432 \
  --conn-login app --conn-password app --conn-schema billing
```

### 4. Запустить ETL

**Через Airflow UI:**
1. Открыть http://localhost:8080
2. Включить DAG `dwh_master` (toggle)
3. Нажать "Trigger DAG"

**Через CLI:**
```bash
docker exec airflow-webserver airflow dags trigger dwh_master
```

### 5. Проверить результат

```bash
# Скрипт проверки
./scripts/check_dwh_data.sh

# Или вручную
docker exec db-dwh psql -U dwh -d dwh -c "SELECT * FROM mart.kpi_daily;"
```

### 6. Создать дамп (после успешного прогона)

```bash
./scripts/dump_dwh.sh
```

### 7. Восстановить из дампа

```bash
./scripts/restore_dwh.sh
```

---

## Частые вопросы

### Почему full-load, а не incremental?

> "Для объёмов данных в этом проекте full-load проще и надёжнее. 
> Incremental требует поддержки watermarks, обработки удалений, 
> и усложняет отладку. Для production с большими объёмами — да, нужен incremental."

### Почему отдельные DAG-и, а не один монолитный?

> "Разделение даёт:
> - Параллельное выполнение (RAW rental и billing одновременно)
> - Независимый перезапуск упавших частей
> - Лучшую читаемость и поддержку
> - Возможность разного расписания для разных слоёв"

### Как обеспечивается SoT?

> "В CORE слое данные о платежах и долгах берутся только из billing-источника.
> Даже если в rental есть похожие данные, они игнорируются.
> Это явно прописано в `02_core.sql` и в DAG-ах."

### Что будет при ошибке ETL?

> "Airflow автоматически делает retry (настроено 2 попытки).
> Если всё равно падает — DAG помечается как failed, 
> можно посмотреть логи и перезапустить вручную."

---

## Полезные команды

```bash
# Статус DAG-ов
docker exec airflow-webserver airflow dags list

# Прогоны DAG-а
docker exec airflow-webserver airflow dags list-runs -d dwh_master

# Логи задачи
docker logs airflow-scheduler 2>&1 | grep -i error | tail -20

# Подключение к DWH
docker exec -it db-dwh psql -U dwh -d dwh

# Проверка данных
./scripts/check_dwh_data.sh

# Создание дампа
./scripts/dump_dwh.sh

# Восстановление
./scripts/restore_dwh.sh
```

