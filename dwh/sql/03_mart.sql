-- 03_mart.sql
-- MART layer: denormalized facts + daily KPI snapshot.

BEGIN;

-- Пересоздаём таблицы (full refresh)
DROP TABLE IF EXISTS mart.fct_rentals CASCADE;
DROP TABLE IF EXISTS mart.fct_payments CASCADE;
DROP TABLE IF EXISTS mart.kpi_daily CASCADE;

CREATE TABLE mart.fct_rentals (
  rental_id       varchar(64) PRIMARY KEY,
  user_id         varchar(64) NOT NULL,
  powerbank_id    varchar(64) NOT NULL,
  status          varchar(16) NOT NULL,
  started_at      timestamptz NOT NULL,
  finished_at     timestamptz,
  total_amount    integer     NOT NULL,
  price_per_hour  integer     NOT NULL,
  free_period_min integer     NOT NULL,
  deposit         integer     NOT NULL
);

CREATE TABLE mart.fct_payments (
  payment_attempt_id integer PRIMARY KEY,
  rental_id          varchar(64) NOT NULL,
  amount             integer     NOT NULL,
  success            boolean     NOT NULL,
  error              text,
  created_at         timestamptz NOT NULL
);

CREATE TABLE mart.kpi_daily (
  day                     date PRIMARY KEY,
  quotes_cnt              integer NOT NULL DEFAULT 0,
  rentals_started_cnt     integer NOT NULL DEFAULT 0,
  rentals_finished_cnt    integer NOT NULL DEFAULT 0,
  payments_attempts_cnt   integer NOT NULL DEFAULT 0,
  payments_success_cnt    integer NOT NULL DEFAULT 0,
  revenue_amount          bigint  NOT NULL DEFAULT 0,
  avg_rental_duration_min numeric(12,2)
);

-- Facts
INSERT INTO mart.fct_rentals
SELECT
  id, user_id, powerbank_id, status,
  started_at, finished_at,
  total_amount, price_per_hour, free_period_min, deposit
FROM core.rentals;

INSERT INTO mart.fct_payments
SELECT
  id, rental_id, amount, success, error, created_at
FROM core.payment_attempts;

-- KPI calendar built from ALL event sources (quotes may be empty)
WITH bounds AS (
  SELECT
    LEAST(
      COALESCE((SELECT min(started_at)::date FROM core.rentals), '9999-12-31'),
      COALESCE((SELECT min(created_at)::date FROM core.payment_attempts), '9999-12-31')
    ) AS min_day,
    GREATEST(
      COALESCE((SELECT max(started_at)::date FROM core.rentals), '0001-01-01'),
      COALESCE((SELECT max(created_at)::date FROM core.payment_attempts), '0001-01-01')
    ) AS max_day
),
d AS (
  SELECT generate_series(min_day, max_day, interval '1 day')::date AS day
  FROM bounds
  WHERE min_day <= max_day
),
q AS (
  SELECT created_at::date AS day, count(*) AS quotes_cnt
  FROM core.quotes
  GROUP BY 1
),
r_start AS (
  SELECT started_at::date AS day, count(*) AS rentals_started_cnt
  FROM core.rentals
  GROUP BY 1
),
r_finish AS (
  SELECT finished_at::date AS day,
         count(*) AS rentals_finished_cnt,
         avg(extract(epoch from (finished_at - started_at)) / 60.0) AS avg_rental_duration_min
  FROM core.rentals
  WHERE finished_at IS NOT NULL
  GROUP BY 1
),
p AS (
  SELECT created_at::date AS day,
         count(*) AS payments_attempts_cnt,
         sum((success)::int) AS payments_success_cnt,
         sum(CASE WHEN success THEN amount ELSE 0 END)::bigint AS revenue_amount
  FROM core.payment_attempts
  GROUP BY 1
)
INSERT INTO mart.kpi_daily
SELECT
  d.day,
  COALESCE(q.quotes_cnt, 0),
  COALESCE(r_start.rentals_started_cnt, 0),
  COALESCE(r_finish.rentals_finished_cnt, 0),
  COALESCE(p.payments_attempts_cnt, 0),
  COALESCE(p.payments_success_cnt, 0),
  COALESCE(p.revenue_amount, 0),
  r_finish.avg_rental_duration_min
FROM d
LEFT JOIN q        ON q.day = d.day
LEFT JOIN r_start  ON r_start.day = d.day
LEFT JOIN r_finish ON r_finish.day = d.day
LEFT JOIN p        ON p.day = d.day
ORDER BY d.day;

COMMIT;
