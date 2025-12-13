-- 01_raw.sql
-- RAW layer: copy of source data (minimal transformations).
-- IMPORTANT: If your source tables have different columns, adjust this DDL to match your migrations.
-- (We keep a minimal set of fields that are usually present in this domain.)

CREATE TABLE IF NOT EXISTS raw_rental.quotes (
  id              bigint PRIMARY KEY,
  user_id         bigint,
  station_id      bigint,
  powerbank_id    bigint,
  price_amount    numeric(12,2),
  currency        text,
  created_at      timestamptz,
  updated_at      timestamptz,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_rental.rentals (
  id              bigint PRIMARY KEY,
  quote_id        bigint,
  user_id         bigint,
  station_id      bigint,
  powerbank_id    bigint,
  status          text,
  started_at      timestamptz,
  ended_at        timestamptz,
  created_at      timestamptz,
  updated_at      timestamptz,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_rental.idempotency_keys (
  id              bigint PRIMARY KEY,
  idem_key        text,
  scope           text,
  created_at      timestamptz,
  request_hash    text,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_billing.debts (
  id              bigint PRIMARY KEY,
  rental_id       bigint,
  user_id         bigint,
  amount          numeric(12,2),
  currency        text,
  status          text,
  due_at          timestamptz,
  created_at      timestamptz,
  updated_at      timestamptz,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_billing.payment_attempts (
  id              bigint PRIMARY KEY,
  debt_id         bigint,
  amount          numeric(12,2),
  currency        text,
  status          text,
  provider        text,
  created_at      timestamptz,
  updated_at      timestamptz,
  _ingested_at    timestamptz NOT NULL DEFAULT now()
);

-- Helpful indexes for incremental checks / debugging
CREATE INDEX IF NOT EXISTS ix_raw_rental_rentals_created_at ON raw_rental.rentals(created_at);
CREATE INDEX IF NOT EXISTS ix_raw_billing_payments_created_at ON raw_billing.payment_attempts(created_at);
