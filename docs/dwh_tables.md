# Documentation of DWH tables (Powerbank Rental)

## RAW layer

### raw_rental.quotes
Copy of `db-rental.public.quotes` (as-is). Used to count quote creation and join rental -> quote.
- `id` (PK) – quote id
- `user_id` – customer
- `station_id` – where quote was requested
- `powerbank_id` – powerbank model/slot (if present)
- `price_amount`, `currency` – price proposal
- `created_at`, `updated_at`
- `_ingested_at` – DWH load timestamp

### raw_rental.rentals
Copy of `db-rental.public.rentals` (as-is). Main business entity.
- `id` (PK) – rental id
- `quote_id` – link to quote
- `user_id`, `station_id`, `powerbank_id`
- `status` – rental status
- `started_at`, `ended_at`
- `created_at`, `updated_at`
- `_ingested_at`

### raw_rental.idempotency_keys
Technical table for idempotent requests.
- `id` (PK)
- `idem_key`, `scope`, `created_at`, `request_hash`
- `_ingested_at`

### raw_billing.debts
Copy of `db-billing.public.debts` (SoT for finance).
- `id` (PK) – debt id
- `rental_id`, `user_id`
- `amount`, `currency`
- `status` – OPEN/PAID/OVERDUE/...
- `due_at`, `created_at`, `updated_at`
- `_ingested_at`

### raw_billing.payment_attempts
Copy of `db-billing.public.payment_attempts` (SoT for payments).
- `id` (PK) – attempt id
- `debt_id`
- `amount`, `currency`
- `status` – SUCCESS/FAILED/PENDING/...
- `provider`
- `created_at`, `updated_at`
- `_ingested_at`

## CORE layer (canonical)

CORE tables are built strictly from RAW with Source of Truth rule:
- rental domain: from `raw_rental.*`
- finance domain: from `raw_billing.*`

Tables:
- `core.quotes`
- `core.rentals`
- `core.idempotency_keys`
- `core.debts`
- `core.payment_attempts`

## MART layer

### mart.fct_rentals
Rental fact table for BI: one row per rental (joined with quote info).
- `rental_id` (PK)
- `user_id`, `station_id`, `powerbank_id`
- `status`, `started_at`, `ended_at`, `duration_min`
- `quote_id`, `quote_created_at`

### mart.fct_payments
Payment attempts fact table (joined with debt info).
- `payment_attempt_id` (PK)
- `debt_id`, `rental_id`, `user_id`
- `amount`, `currency`, `status`, `provider`, `created_at`

### mart.kpi_daily
Main dashboard table (daily).
**6 KPI columns**:
- `quotes_cnt`
- `rentals_started_cnt`
- `rentals_completed_cnt`
- `revenue_paid_amount`
- `payment_success_rate`
- `avg_rental_duration_min`

## META layer

### meta.etl_watermark
Storage for incremental loads (we keep it even if we use full loads in HW).

### meta.etl_run_audit
Audit of ETL runs (start/finish/status/details).
