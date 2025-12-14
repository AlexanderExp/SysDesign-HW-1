-- 00_billing_init.sql
-- Create billing source tables if they don't exist yet.

CREATE TABLE IF NOT EXISTS public.debts (
  id         integer PRIMARY KEY,
  rental_id  varchar(64) NOT NULL,
  user_id    varchar(64) NOT NULL,
  amount     integer     NOT NULL,
  status     varchar(16) NOT NULL,
  created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS public.payment_attempts (
  id         integer PRIMARY KEY,
  rental_id  varchar(64) NOT NULL,
  amount     integer     NOT NULL,
  success    boolean     NOT NULL,
  error      text,
  created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_debts_created_at ON public.debts(created_at);
CREATE INDEX IF NOT EXISTS ix_payment_attempts_created_at ON public.payment_attempts(created_at);
