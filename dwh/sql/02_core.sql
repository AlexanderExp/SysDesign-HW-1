-- 02_core.sql
-- CORE layer: canonical entities with "Source of Truth" rules.
-- SoT(rental)  = raw_rental.*
-- SoT(finance) = raw_billing.*

CREATE TABLE IF NOT EXISTS core.quotes (LIKE raw_rental.quotes INCLUDING ALL);
ALTER TABLE core.quotes DROP COLUMN IF EXISTS _ingested_at;

CREATE TABLE IF NOT EXISTS core.rentals (LIKE raw_rental.rentals INCLUDING ALL);
ALTER TABLE core.rentals DROP COLUMN IF EXISTS _ingested_at;

CREATE TABLE IF NOT EXISTS core.idempotency_keys (LIKE raw_rental.idempotency_keys INCLUDING ALL);
ALTER TABLE core.idempotency_keys DROP COLUMN IF EXISTS _ingested_at;

CREATE TABLE IF NOT EXISTS core.debts (LIKE raw_billing.debts INCLUDING ALL);
ALTER TABLE core.debts DROP COLUMN IF EXISTS _ingested_at;

CREATE TABLE IF NOT EXISTS core.payment_attempts (LIKE raw_billing.payment_attempts INCLUDING ALL);
ALTER TABLE core.payment_attempts DROP COLUMN IF EXISTS _ingested_at;

-- Upsert RAW -> CORE (deterministic, safe for reruns)

INSERT INTO core.quotes
SELECT id, user_id, station_id, powerbank_id, price_amount, currency, created_at, updated_at
FROM raw_rental.quotes
ON CONFLICT (id) DO UPDATE SET
  user_id      = EXCLUDED.user_id,
  station_id   = EXCLUDED.station_id,
  powerbank_id = EXCLUDED.powerbank_id,
  price_amount = EXCLUDED.price_amount,
  currency     = EXCLUDED.currency,
  created_at   = EXCLUDED.created_at,
  updated_at   = EXCLUDED.updated_at;

INSERT INTO core.rentals
SELECT id, quote_id, user_id, station_id, powerbank_id, status, started_at, ended_at, created_at, updated_at
FROM raw_rental.rentals
ON CONFLICT (id) DO UPDATE SET
  quote_id     = EXCLUDED.quote_id,
  user_id      = EXCLUDED.user_id,
  station_id   = EXCLUDED.station_id,
  powerbank_id = EXCLUDED.powerbank_id,
  status       = EXCLUDED.status,
  started_at   = EXCLUDED.started_at,
  ended_at     = EXCLUDED.ended_at,
  created_at   = EXCLUDED.created_at,
  updated_at   = EXCLUDED.updated_at;

INSERT INTO core.idempotency_keys
SELECT id, idem_key, scope, created_at, request_hash
FROM raw_rental.idempotency_keys
ON CONFLICT (id) DO UPDATE SET
  idem_key     = EXCLUDED.idem_key,
  scope        = EXCLUDED.scope,
  created_at   = EXCLUDED.created_at,
  request_hash = EXCLUDED.request_hash;

INSERT INTO core.debts
SELECT id, rental_id, user_id, amount, currency, status, due_at, created_at, updated_at
FROM raw_billing.debts
ON CONFLICT (id) DO UPDATE SET
  rental_id  = EXCLUDED.rental_id,
  user_id    = EXCLUDED.user_id,
  amount     = EXCLUDED.amount,
  currency   = EXCLUDED.currency,
  status     = EXCLUDED.status,
  due_at     = EXCLUDED.due_at,
  created_at = EXCLUDED.created_at,
  updated_at = EXCLUDED.updated_at;

INSERT INTO core.payment_attempts
SELECT id, debt_id, amount, currency, status, provider, created_at, updated_at
FROM raw_billing.payment_attempts
ON CONFLICT (id) DO UPDATE SET
  debt_id    = EXCLUDED.debt_id,
  amount     = EXCLUDED.amount,
  currency   = EXCLUDED.currency,
  status     = EXCLUDED.status,
  provider   = EXCLUDED.provider,
  created_at = EXCLUDED.created_at,
  updated_at = EXCLUDED.updated_at;
