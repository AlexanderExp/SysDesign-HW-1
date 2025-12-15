# DWH for Powerbank Rental (HW2)

This folder is a ready-to-copy skeleton: PostgreSQL DWH + Apache Airflow ETL + artifacts export.

## 1) Add it to your repo

Put these into your repo root:

- `docker-compose.dwh.yml`
- `dwh/` (sql, dags, artifacts)
- `docs/` (docs + dashboard template)

## 2) Run infra

From repo root:

```bash
docker compose -f docker-compose.yml -f docker-compose.dwh.yml up -d
```

Airflow UI: http://localhost:8080  
Login: `admin / admin`

DWH Postgres: localhost:5444 (db: `dwh`, user/pass: `dwh/dwh`)

## 3) Check Airflow connections

Connections are injected via env vars in compose:
- `rental_db`  -> `AIRFLOW_CONN_RENTAL_DB`
- `billing_db` -> `AIRFLOW_CONN_BILLING_DB`
- `dwh_db`     -> `AIRFLOW_CONN_DWH_DB`

⚠️ If your service DB users/passwords differ, edit the env vars in `docker-compose.dwh.yml`.

## 4) Run DAG

In Airflow UI enable and trigger DAG `dwh_powerbank_etl`.

Artifacts will appear in `dwh/artifacts/` as CSV snapshots.

## 5) Grafana

Create a Postgres datasource pointing to `db-dwh:5432`, database `dwh`.

Recommended:
- user: `bi_readonly`
- password: `bi_readonly`

Then use `mart.kpi_daily` for panels.

## 6) If your source schema differs

Update:
- `dwh/sql/01_raw.sql` (RAW table columns)
- `dwh/sql/02_core.sql` / `dwh/sql/03_mart.sql` (columns used in transformations)
- `dwh/dags/dwh_etl_powerbank.py` (table names in `RAW_LOAD_CONFIG`, if needed)
