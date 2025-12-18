-- 02_core.sql
-- CORE layer: clean copy of RAW (same structure), used as a stable base for marts.
-- For this homework we do a full-refresh (truncate + reload).
-- SoT: debts и payment_attempts берутся ТОЛЬКО из billing!

BEGIN;

-- Создаём таблицы если не существуют (DROP + CREATE для обновления структуры)
DROP TABLE IF EXISTS core.quotes CASCADE;
DROP TABLE IF EXISTS core.rentals CASCADE;
DROP TABLE IF EXISTS core.idempotency_keys CASCADE;
DROP TABLE IF EXISTS core.debts CASCADE;
DROP TABLE IF EXISTS core.payment_attempts CASCADE;

CREATE TABLE core.quotes (LIKE raw_rental.quotes INCLUDING ALL);
CREATE TABLE core.rentals (LIKE raw_rental.rentals INCLUDING ALL);
CREATE TABLE core.idempotency_keys (LIKE raw_rental.idempotency_keys INCLUDING ALL);

-- SoT = billing
CREATE TABLE core.debts (LIKE raw_billing.debts INCLUDING ALL);
CREATE TABLE core.payment_attempts (LIKE raw_billing.payment_attempts INCLUDING ALL);

-- Загружаем данные из RAW
INSERT INTO core.quotes SELECT * FROM raw_rental.quotes;
INSERT INTO core.rentals SELECT * FROM raw_rental.rentals;
INSERT INTO core.idempotency_keys SELECT * FROM raw_rental.idempotency_keys;

-- SoT = billing (долги и платежи только из billing!)
INSERT INTO core.debts SELECT * FROM raw_billing.debts;
INSERT INTO core.payment_attempts SELECT * FROM raw_billing.payment_attempts;

COMMIT;
