# DWH Artifacts

Эта директория содержит артефакты DWH — дампы базы данных и CSV-снимки витрин.

## Файлы

### Дампы базы данных

- **`dwh_dump.sql`** — полный дамп DWH (схема + данные)
- **`dwh_schema_only.sql`** — только DDL (схема без данных)

### CSV снимки витрин

Генерируются автоматически при запуске ETL:
- `mart_kpi_daily_*.csv` — ежедневные KPI
- `mart_fct_rentals_*.csv` — факты по арендам
- `mart_fct_payments_*.csv` — факты по платежам

## Восстановление DWH из дампа

### Вариант 1: Скрипт (рекомендуется)

```bash
# Из корня проекта
./scripts/restore_dwh.sh
```

### Вариант 2: Вручную

1. Запустите инфраструктуру:
```bash
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d
```

2. Дождитесь готовности контейнеров:
```bash
docker compose -f docker-compose.yml -f docker-compose.dwh.yml ps
```

3. Восстановите дамп:
```bash
cat dwh/artifacts/dwh_dump.sql | docker exec -i db-dwh psql -U dwh -d dwh
```

4. Проверьте данные:
```bash
docker exec db-dwh psql -U dwh -d dwh -c "SELECT count(*) FROM mart.kpi_daily;"
```

## Создание нового дампа

После успешного прогона ETL:

```bash
./scripts/dump_dwh.sh
```

## Проверка данных (для защиты)

```bash
./scripts/check_dwh_data.sh
```

Минимальный набор SQL для проверки:
```sql
-- Подключиться к DWH
docker exec -it db-dwh psql -U dwh -d dwh

-- RAW слой
SELECT count(*) FROM raw_rental.rentals;
SELECT count(*) FROM raw_billing.payment_attempts;

-- CORE слой
SELECT count(*) FROM core.rentals;

-- MART слой
SELECT count(*) FROM mart.kpi_daily;

-- Данные KPI
SELECT * FROM mart.kpi_daily ORDER BY day DESC LIMIT 5;
```

## Структура DWH

```
DWH (db-dwh)
├── raw_rental.*    ← данные из db-rental
├── raw_billing.*   ← данные из db-billing (SoT для платежей/долгов)
├── core.*          ← очищенные данные
├── mart.*          ← витрины и KPI
└── meta.*          ← аудит ETL
```


