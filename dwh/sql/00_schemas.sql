-- 00_schemas.sql
-- Physical separation by schemas (RAW / CORE / MART / META).

CREATE SCHEMA IF NOT EXISTS raw_rental;
CREATE SCHEMA IF NOT EXISTS raw_billing;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS meta;

-- BI read-only user (Grafana should connect with it)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_readonly') THEN
    CREATE ROLE bi_readonly LOGIN PASSWORD 'bi_readonly';
  END IF;
END $$;

GRANT USAGE ON SCHEMA mart TO bi_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT SELECT ON TABLES TO bi_readonly;
