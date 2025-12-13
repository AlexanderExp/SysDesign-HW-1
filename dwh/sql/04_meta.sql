-- 04_meta.sql
CREATE TABLE IF NOT EXISTS meta.etl_watermark (
  entity           text PRIMARY KEY,     -- e.g. 'raw_rental.rentals'
  watermark_value  text NOT NULL,        -- store as text (timestamp or id)
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta.etl_run_audit (
  run_id        uuid PRIMARY KEY,
  dag_id        text NOT NULL,
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz,
  status        text NOT NULL DEFAULT 'RUNNING',
  details       jsonb
);
