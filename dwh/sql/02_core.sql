-- 02_core.sql
-- CORE layer: clean copy of RAW (same structure), used as a stable base for marts.
-- For this homework we do a full-refresh (truncate + reload).

BEGIN;

CREATE TABLE IF NOT EXISTS core.quotes (LIKE raw_rental.quotes INCLUDING ALL);
CREATE TABLE IF NOT EXISTS core.rentals (LIKE raw_rental.rentals INCLUDING ALL);
CREATE TABLE IF NOT EXISTS core.idempotency_keys (LIKE raw_rental.idempotency_keys INCLUDING ALL);

CREATE TABLE IF NOT EXISTS core.debts (LIKE raw_billing.debts INCLUDING ALL);
CREATE TABLE IF NOT EXISTS core.payment_attempts (LIKE raw_billing.payment_attempts INCLUDING ALL);

TRUNCATE TABLE
  core.payment_attempts,
  core.debts,
  core.idempotency_keys,
  core.rentals,
  core.quotes;

INSERT INTO core.quotes SELECT * FROM raw_rental.quotes;
INSERT INTO core.rentals SELECT * FROM raw_rental.rentals;
INSERT INTO core.idempotency_keys SELECT * FROM raw_rental.idempotency_keys;

INSERT INTO core.debts SELECT * FROM raw_billing.debts;
INSERT INTO core.payment_attempts SELECT * FROM raw_billing.payment_attempts;

COMMIT;
