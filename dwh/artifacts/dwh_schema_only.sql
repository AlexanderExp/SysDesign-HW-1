--
-- PostgreSQL database dump
--

\restrict MhK8KavPNyTX8w1Yr1kmHIWqWtJ1goO70LA36Ko74dexQ0OACatec2n4H2b75dF

-- Dumped from database version 15.15 (Debian 15.15-1.pgdg13+1)
-- Dumped by pg_dump version 15.15 (Debian 15.15-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA core;


--
-- Name: mart; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA mart;


--
-- Name: meta; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA meta;


--
-- Name: raw_billing; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw_billing;


--
-- Name: raw_rental; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw_rental;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: debts; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.debts (
    rental_id character varying(64) NOT NULL,
    amount_total integer NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    attempts integer NOT NULL,
    last_attempt_at timestamp with time zone,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: idempotency_keys; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.idempotency_keys (
    key character varying(64) NOT NULL,
    scope character varying(32) NOT NULL,
    user_id character varying(64) NOT NULL,
    response_json text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_attempts; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.payment_attempts (
    id integer NOT NULL,
    rental_id character varying(64) NOT NULL,
    amount integer NOT NULL,
    success boolean NOT NULL,
    error text,
    created_at timestamp with time zone NOT NULL,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: quotes; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.quotes (
    id character varying(64) NOT NULL,
    user_id character varying(64) NOT NULL,
    station_id character varying(128) NOT NULL,
    price_per_hour integer NOT NULL,
    free_period_min integer NOT NULL,
    deposit integer NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rentals; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.rentals (
    id character varying(64) NOT NULL,
    user_id character varying(64) NOT NULL,
    powerbank_id character varying(64) NOT NULL,
    price_per_hour integer NOT NULL,
    free_period_min integer NOT NULL,
    deposit integer NOT NULL,
    status character varying(16) NOT NULL,
    total_amount integer NOT NULL,
    started_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: fct_payments; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.fct_payments (
    payment_attempt_id integer NOT NULL,
    rental_id character varying(64) NOT NULL,
    amount integer NOT NULL,
    success boolean NOT NULL,
    error text,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: fct_rentals; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.fct_rentals (
    rental_id character varying(64) NOT NULL,
    user_id character varying(64) NOT NULL,
    powerbank_id character varying(64) NOT NULL,
    status character varying(16) NOT NULL,
    started_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    total_amount integer NOT NULL,
    price_per_hour integer NOT NULL,
    free_period_min integer NOT NULL,
    deposit integer NOT NULL
);


--
-- Name: kpi_daily; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.kpi_daily (
    day date NOT NULL,
    quotes_cnt integer DEFAULT 0 NOT NULL,
    rentals_started_cnt integer DEFAULT 0 NOT NULL,
    rentals_finished_cnt integer DEFAULT 0 NOT NULL,
    payments_attempts_cnt integer DEFAULT 0 NOT NULL,
    payments_success_cnt integer DEFAULT 0 NOT NULL,
    revenue_amount bigint DEFAULT 0 NOT NULL,
    avg_rental_duration_min numeric(12,2)
);


--
-- Name: etl_run_audit; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.etl_run_audit (
    run_id uuid NOT NULL,
    dag_id text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status text DEFAULT 'RUNNING'::text NOT NULL,
    details jsonb
);


--
-- Name: etl_watermark; Type: TABLE; Schema: meta; Owner: -
--

CREATE TABLE meta.etl_watermark (
    entity text NOT NULL,
    watermark_value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: debts; Type: TABLE; Schema: raw_billing; Owner: -
--

CREATE TABLE raw_billing.debts (
    rental_id character varying(64) NOT NULL,
    amount_total integer NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    attempts integer NOT NULL,
    last_attempt_at timestamp with time zone,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: payment_attempts; Type: TABLE; Schema: raw_billing; Owner: -
--

CREATE TABLE raw_billing.payment_attempts (
    id integer NOT NULL,
    rental_id character varying(64) NOT NULL,
    amount integer NOT NULL,
    success boolean NOT NULL,
    error text,
    created_at timestamp with time zone NOT NULL,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: idempotency_keys; Type: TABLE; Schema: raw_rental; Owner: -
--

CREATE TABLE raw_rental.idempotency_keys (
    key character varying(64) NOT NULL,
    scope character varying(32) NOT NULL,
    user_id character varying(64) NOT NULL,
    response_json text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: quotes; Type: TABLE; Schema: raw_rental; Owner: -
--

CREATE TABLE raw_rental.quotes (
    id character varying(64) NOT NULL,
    user_id character varying(64) NOT NULL,
    station_id character varying(128) NOT NULL,
    price_per_hour integer NOT NULL,
    free_period_min integer NOT NULL,
    deposit integer NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone NOT NULL,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rentals; Type: TABLE; Schema: raw_rental; Owner: -
--

CREATE TABLE raw_rental.rentals (
    id character varying(64) NOT NULL,
    user_id character varying(64) NOT NULL,
    powerbank_id character varying(64) NOT NULL,
    price_per_hour integer NOT NULL,
    free_period_min integer NOT NULL,
    deposit integer NOT NULL,
    status character varying(16) NOT NULL,
    total_amount integer NOT NULL,
    started_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    _ingested_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: debts debts_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.debts
    ADD CONSTRAINT debts_pkey PRIMARY KEY (rental_id);


--
-- Name: idempotency_keys idempotency_keys_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.idempotency_keys
    ADD CONSTRAINT idempotency_keys_pkey PRIMARY KEY (key);


--
-- Name: payment_attempts payment_attempts_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.payment_attempts
    ADD CONSTRAINT payment_attempts_pkey PRIMARY KEY (id);


--
-- Name: quotes quotes_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.quotes
    ADD CONSTRAINT quotes_pkey PRIMARY KEY (id);


--
-- Name: rentals rentals_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.rentals
    ADD CONSTRAINT rentals_pkey PRIMARY KEY (id);


--
-- Name: fct_payments fct_payments_pkey; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.fct_payments
    ADD CONSTRAINT fct_payments_pkey PRIMARY KEY (payment_attempt_id);


--
-- Name: fct_rentals fct_rentals_pkey; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.fct_rentals
    ADD CONSTRAINT fct_rentals_pkey PRIMARY KEY (rental_id);


--
-- Name: kpi_daily kpi_daily_pkey; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.kpi_daily
    ADD CONSTRAINT kpi_daily_pkey PRIMARY KEY (day);


--
-- Name: etl_run_audit etl_run_audit_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.etl_run_audit
    ADD CONSTRAINT etl_run_audit_pkey PRIMARY KEY (run_id);


--
-- Name: etl_watermark etl_watermark_pkey; Type: CONSTRAINT; Schema: meta; Owner: -
--

ALTER TABLE ONLY meta.etl_watermark
    ADD CONSTRAINT etl_watermark_pkey PRIMARY KEY (entity);


--
-- Name: debts debts_pkey; Type: CONSTRAINT; Schema: raw_billing; Owner: -
--

ALTER TABLE ONLY raw_billing.debts
    ADD CONSTRAINT debts_pkey PRIMARY KEY (rental_id);


--
-- Name: payment_attempts payment_attempts_pkey; Type: CONSTRAINT; Schema: raw_billing; Owner: -
--

ALTER TABLE ONLY raw_billing.payment_attempts
    ADD CONSTRAINT payment_attempts_pkey PRIMARY KEY (id);


--
-- Name: idempotency_keys idempotency_keys_pkey; Type: CONSTRAINT; Schema: raw_rental; Owner: -
--

ALTER TABLE ONLY raw_rental.idempotency_keys
    ADD CONSTRAINT idempotency_keys_pkey PRIMARY KEY (key);


--
-- Name: quotes quotes_pkey; Type: CONSTRAINT; Schema: raw_rental; Owner: -
--

ALTER TABLE ONLY raw_rental.quotes
    ADD CONSTRAINT quotes_pkey PRIMARY KEY (id);


--
-- Name: rentals rentals_pkey; Type: CONSTRAINT; Schema: raw_rental; Owner: -
--

ALTER TABLE ONLY raw_rental.rentals
    ADD CONSTRAINT rentals_pkey PRIMARY KEY (id);


--
-- Name: debts_updated_at_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX debts_updated_at_idx ON core.debts USING btree (updated_at);


--
-- Name: payment_attempts_created_at_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX payment_attempts_created_at_idx ON core.payment_attempts USING btree (created_at);


--
-- Name: quotes_created_at_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX quotes_created_at_idx ON core.quotes USING btree (created_at);


--
-- Name: rentals_finished_at_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX rentals_finished_at_idx ON core.rentals USING btree (finished_at);


--
-- Name: rentals_started_at_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX rentals_started_at_idx ON core.rentals USING btree (started_at);


--
-- Name: ix_raw_billing_debts_updated_at; Type: INDEX; Schema: raw_billing; Owner: -
--

CREATE INDEX ix_raw_billing_debts_updated_at ON raw_billing.debts USING btree (updated_at);


--
-- Name: ix_raw_billing_payments_created_at; Type: INDEX; Schema: raw_billing; Owner: -
--

CREATE INDEX ix_raw_billing_payments_created_at ON raw_billing.payment_attempts USING btree (created_at);


--
-- Name: ix_raw_rental_quotes_created_at; Type: INDEX; Schema: raw_rental; Owner: -
--

CREATE INDEX ix_raw_rental_quotes_created_at ON raw_rental.quotes USING btree (created_at);


--
-- Name: ix_raw_rental_rentals_finished_at; Type: INDEX; Schema: raw_rental; Owner: -
--

CREATE INDEX ix_raw_rental_rentals_finished_at ON raw_rental.rentals USING btree (finished_at);


--
-- Name: ix_raw_rental_rentals_started_at; Type: INDEX; Schema: raw_rental; Owner: -
--

CREATE INDEX ix_raw_rental_rentals_started_at ON raw_rental.rentals USING btree (started_at);


--
-- PostgreSQL database dump complete
--

\unrestrict MhK8KavPNyTX8w1Yr1kmHIWqWtJ1goO70LA36Ko74dexQ0OACatec2n4H2b75dF

