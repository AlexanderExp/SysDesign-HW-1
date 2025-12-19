-- 01_raw.sql
-- RAW layer: 1:1 copy of source data from Rental and Billing services.
-- IMPORTANT: column names and types are aligned with source DB migrations
-- (so Airflow load_raw can copy data without casts).

-- Quotes: котировки на аренду
CREATE TABLE IF NOT EXISTS raw_rental.quotes (
  id              varchar(64) PRIMARY KEY,
  user_id         varchar(64) NOT NULL,
  station_id      varchar(128) NOT NULL,
  price_per_hour  integer     NOT NULL,
  free_period_min integer     NOT NULL,
  deposit         integer     NOT NULL,
  expires_at      timestamptz NOT NULL,
  created_at      timestamptz NOT NULL,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Rentals: активные и завершённые аренды
CREATE TABLE IF NOT EXISTS raw_rental.rentals (
  id              varchar(64) PRIMARY KEY,
  user_id         varchar(64) NOT NULL,
  powerbank_id    varchar(64) NOT NULL,
  price_per_hour  integer     NOT NULL,
  free_period_min integer     NOT NULL,
  deposit         integer     NOT NULL,
  status          varchar(16) NOT NULL,
  total_amount    integer     NOT NULL,
  started_at      timestamptz NOT NULL,
  finished_at     timestamptz,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Idempotency keys: ключи идемпотентности
CREATE TABLE IF NOT EXISTS raw_rental.idempotency_keys (
  key             varchar(64) PRIMARY KEY,
  scope           varchar(32) NOT NULL,
  user_id         varchar(64) NOT NULL,
  response_json   text        NOT NULL,
  created_at      timestamptz NOT NULL,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Debts: долги пользователей (структура из billing)
CREATE TABLE IF NOT EXISTS raw_billing.debts (
  rental_id       varchar(64) PRIMARY KEY,
  amount_total    integer     NOT NULL,
  updated_at      timestamptz NOT NULL,
  attempts        integer     NOT NULL,
  last_attempt_at timestamptz,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Payment attempts: попытки списания
CREATE TABLE IF NOT EXISTS raw_billing.payment_attempts (
  id              integer PRIMARY KEY,
  rental_id       varchar(64) NOT NULL,
  amount          integer     NOT NULL,
  success         boolean     NOT NULL,
  error           text,
  created_at      timestamptz NOT NULL,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Helpful indexes for incremental checks / debugging
CREATE INDEX IF NOT EXISTS ix_raw_rental_quotes_created_at ON raw_rental.quotes(created_at);
CREATE INDEX IF NOT EXISTS ix_raw_rental_rentals_started_at ON raw_rental.rentals(started_at);
CREATE INDEX IF NOT EXISTS ix_raw_rental_rentals_finished_at ON raw_rental.rentals(finished_at);
CREATE INDEX IF NOT EXISTS ix_raw_billing_debts_updated_at ON raw_billing.debts(updated_at);
CREATE INDEX IF NOT EXISTS ix_raw_billing_payments_created_at ON raw_billing.payment_attempts(created_at);
