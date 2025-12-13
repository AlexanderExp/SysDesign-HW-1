-- 03_mart.sql
-- MART layer: facts + KPI daily table for dashboard (6+ metrics)

CREATE TABLE IF NOT EXISTS mart.fct_rentals (
  rental_id        bigint PRIMARY KEY,
  user_id          bigint,
  station_id       bigint,
  powerbank_id     bigint,
  status           text,
  started_at       timestamptz,
  ended_at         timestamptz,
  duration_min     numeric(12,2),
  quote_id         bigint,
  quote_created_at timestamptz
);

CREATE TABLE IF NOT EXISTS mart.fct_payments (
  payment_attempt_id bigint PRIMARY KEY,
  debt_id            bigint,
  rental_id          bigint,
  user_id            bigint,
  amount             numeric(12,2),
  currency           text,
  status             text,
  provider           text,
  created_at         timestamptz
);

CREATE TABLE IF NOT EXISTS mart.kpi_daily (
  day                      date PRIMARY KEY,
  quotes_cnt               bigint NOT NULL,
  rentals_started_cnt      bigint NOT NULL,
  rentals_completed_cnt    bigint NOT NULL,
  revenue_paid_amount      numeric(18,2) NOT NULL,
  payment_success_rate     numeric(8,4) NOT NULL,
  avg_rental_duration_min  numeric(12,2) NOT NULL
);

-- Rebuild marts each run (OK for homework scale)
TRUNCATE mart.fct_rentals;
INSERT INTO mart.fct_rentals (rental_id, user_id, station_id, powerbank_id, status, started_at, ended_at, duration_min, quote_id, quote_created_at)
SELECT
  r.id as rental_id,
  r.user_id,
  r.station_id,
  r.powerbank_id,
  r.status,
  r.started_at,
  r.ended_at,
  CASE
    WHEN r.started_at IS NOT NULL AND r.ended_at IS NOT NULL THEN EXTRACT(EPOCH FROM (r.ended_at - r.started_at)) / 60.0
    ELSE NULL
  END as duration_min,
  r.quote_id,
  q.created_at as quote_created_at
FROM core.rentals r
LEFT JOIN core.quotes q ON q.id = r.quote_id;

TRUNCATE mart.fct_payments;
INSERT INTO mart.fct_payments (payment_attempt_id, debt_id, rental_id, user_id, amount, currency, status, provider, created_at)
SELECT
  pa.id as payment_attempt_id,
  pa.debt_id,
  d.rental_id,
  d.user_id,
  pa.amount,
  pa.currency,
  pa.status,
  pa.provider,
  COALESCE(pa.created_at, pa.updated_at)
FROM core.payment_attempts pa
LEFT JOIN core.debts d ON d.id = pa.debt_id;

TRUNCATE mart.kpi_daily;
WITH
days AS (
  SELECT generate_series(
    (SELECT COALESCE(min(date_trunc('day', created_at)), now() - interval '30 days') FROM core.quotes),
    (SELECT COALESCE(max(date_trunc('day', now())), now()) FROM core.quotes),
    interval '1 day'
  )::date AS day
),
q AS (
  SELECT date_trunc('day', created_at)::date AS day, count(*) AS quotes_cnt
  FROM core.quotes
  GROUP BY 1
),
r_start AS (
  SELECT date_trunc('day', COALESCE(started_at, created_at))::date AS day, count(*) AS rentals_started_cnt
  FROM core.rentals
  GROUP BY 1
),
r_end AS (
  SELECT date_trunc('day', COALESCE(ended_at, updated_at, created_at))::date AS day, count(*) AS rentals_completed_cnt,
         avg(EXTRACT(EPOCH FROM (ended_at - started_at)) / 60.0) AS avg_rental_duration_min
  FROM core.rentals
  WHERE started_at IS NOT NULL AND ended_at IS NOT NULL
  GROUP BY 1
),
p AS (
  SELECT date_trunc('day', created_at)::date AS day,
         sum(CASE WHEN status ILIKE 'SUCCESS%' OR status ILIKE 'PAID%' THEN amount ELSE 0 END) AS revenue_paid_amount,
         count(*) AS attempts_cnt,
         sum(CASE WHEN status ILIKE 'SUCCESS%' OR status ILIKE 'PAID%' THEN 1 ELSE 0 END) AS success_cnt
  FROM mart.fct_payments
  GROUP BY 1
)
INSERT INTO mart.kpi_daily(day, quotes_cnt, rentals_started_cnt, rentals_completed_cnt, revenue_paid_amount, payment_success_rate, avg_rental_duration_min)
SELECT
  d.day,
  COALESCE(q.quotes_cnt, 0) AS quotes_cnt,
  COALESCE(r_start.rentals_started_cnt, 0) AS rentals_started_cnt,
  COALESCE(r_end.rentals_completed_cnt, 0) AS rentals_completed_cnt,
  COALESCE(p.revenue_paid_amount, 0) AS revenue_paid_amount,
  CASE
    WHEN COALESCE(p.attempts_cnt,0) = 0 THEN 0
    ELSE (p.success_cnt::numeric / p.attempts_cnt::numeric)
  END AS payment_success_rate,
  COALESCE(r_end.avg_rental_duration_min, 0) AS avg_rental_duration_min
FROM days d
LEFT JOIN q ON q.day = d.day
LEFT JOIN r_start ON r_start.day = d.day
LEFT JOIN r_end ON r_end.day = d.day
LEFT JOIN p ON p.day = d.day
ORDER BY d.day;
