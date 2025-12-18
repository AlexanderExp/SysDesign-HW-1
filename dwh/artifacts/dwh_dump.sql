--
-- PostgreSQL database dump
--

\restrict jw47xYn7odhOS06jZLgc3TpeqwbIU8vIoBJtsF8fJi2NkU1AgHEvpTD16rgAcSF

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

DROP INDEX IF EXISTS raw_rental.ix_raw_rental_rentals_started_at;
DROP INDEX IF EXISTS raw_rental.ix_raw_rental_rentals_finished_at;
DROP INDEX IF EXISTS raw_rental.ix_raw_rental_quotes_created_at;
DROP INDEX IF EXISTS raw_billing.ix_raw_billing_payments_created_at;
DROP INDEX IF EXISTS raw_billing.ix_raw_billing_debts_updated_at;
DROP INDEX IF EXISTS core.rentals_started_at_idx;
DROP INDEX IF EXISTS core.rentals_finished_at_idx;
DROP INDEX IF EXISTS core.quotes_created_at_idx;
DROP INDEX IF EXISTS core.payment_attempts_created_at_idx;
DROP INDEX IF EXISTS core.debts_updated_at_idx;
ALTER TABLE IF EXISTS ONLY raw_rental.rentals DROP CONSTRAINT IF EXISTS rentals_pkey;
ALTER TABLE IF EXISTS ONLY raw_rental.quotes DROP CONSTRAINT IF EXISTS quotes_pkey;
ALTER TABLE IF EXISTS ONLY raw_rental.idempotency_keys DROP CONSTRAINT IF EXISTS idempotency_keys_pkey;
ALTER TABLE IF EXISTS ONLY raw_billing.payment_attempts DROP CONSTRAINT IF EXISTS payment_attempts_pkey;
ALTER TABLE IF EXISTS ONLY raw_billing.debts DROP CONSTRAINT IF EXISTS debts_pkey;
ALTER TABLE IF EXISTS ONLY meta.etl_watermark DROP CONSTRAINT IF EXISTS etl_watermark_pkey;
ALTER TABLE IF EXISTS ONLY meta.etl_run_audit DROP CONSTRAINT IF EXISTS etl_run_audit_pkey;
ALTER TABLE IF EXISTS ONLY mart.kpi_daily DROP CONSTRAINT IF EXISTS kpi_daily_pkey;
ALTER TABLE IF EXISTS ONLY mart.fct_rentals DROP CONSTRAINT IF EXISTS fct_rentals_pkey;
ALTER TABLE IF EXISTS ONLY mart.fct_payments DROP CONSTRAINT IF EXISTS fct_payments_pkey;
ALTER TABLE IF EXISTS ONLY core.rentals DROP CONSTRAINT IF EXISTS rentals_pkey;
ALTER TABLE IF EXISTS ONLY core.quotes DROP CONSTRAINT IF EXISTS quotes_pkey;
ALTER TABLE IF EXISTS ONLY core.payment_attempts DROP CONSTRAINT IF EXISTS payment_attempts_pkey;
ALTER TABLE IF EXISTS ONLY core.idempotency_keys DROP CONSTRAINT IF EXISTS idempotency_keys_pkey;
ALTER TABLE IF EXISTS ONLY core.debts DROP CONSTRAINT IF EXISTS debts_pkey;
DROP TABLE IF EXISTS raw_rental.rentals;
DROP TABLE IF EXISTS raw_rental.quotes;
DROP TABLE IF EXISTS raw_rental.idempotency_keys;
DROP TABLE IF EXISTS raw_billing.payment_attempts;
DROP TABLE IF EXISTS raw_billing.debts;
DROP TABLE IF EXISTS meta.etl_watermark;
DROP TABLE IF EXISTS meta.etl_run_audit;
DROP TABLE IF EXISTS mart.kpi_daily;
DROP TABLE IF EXISTS mart.fct_rentals;
DROP TABLE IF EXISTS mart.fct_payments;
DROP TABLE IF EXISTS core.rentals;
DROP TABLE IF EXISTS core.quotes;
DROP TABLE IF EXISTS core.payment_attempts;
DROP TABLE IF EXISTS core.idempotency_keys;
DROP TABLE IF EXISTS core.debts;
DROP SCHEMA IF EXISTS raw_rental;
DROP SCHEMA IF EXISTS raw_billing;
DROP SCHEMA IF EXISTS meta;
DROP SCHEMA IF EXISTS mart;
DROP SCHEMA IF EXISTS core;
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
-- Data for Name: debts; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.debts (rental_id, amount_total, updated_at, attempts, last_attempt_at, _ingested_at) FROM stdin;
\.


--
-- Data for Name: idempotency_keys; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.idempotency_keys (key, scope, user_id, response_json, created_at, _ingested_at) FROM stdin;
bf7fa1b1-6acf-41be-a1ba-f66f739eaeb8	start	u1	{"order_id": "618734dc-5ac8-44ad-8b76-c3a5be379cc5", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:29:54.465788+00	2025-12-18 22:40:15.855958+00
7f8daa18-6a74-412e-ba8c-19fadf15952e	start	user-1	{"order_id": "8fb77e6c-4526-4395-921c-b8701264e602", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:30:48.360585+00	2025-12-18 22:40:15.855958+00
ce020279-25eb-4018-b8d5-49edc4767952	start	user-2	{"order_id": "87261863-8d4d-4cbb-afed-89ef2dc571f7", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:30:50.553056+00	2025-12-18 22:40:15.855958+00
cd899a28-9881-4bd9-bef1-f9a8f0a92f5f	start	user-3	{"order_id": "8b699903-1b8a-4aa7-b1ba-5372e0413c6b", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:30:52.723054+00	2025-12-18 22:40:15.855958+00
\.


--
-- Data for Name: payment_attempts; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.payment_attempts (id, rental_id, amount, success, error, created_at, _ingested_at) FROM stdin;
1	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:29:56.735935+00	2025-12-18 22:40:16.000762+00
2	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:30:56.961378+00	2025-12-18 22:40:16.000762+00
3	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:30:56.966203+00	2025-12-18 22:40:16.000762+00
4	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:30:56.970748+00	2025-12-18 22:40:16.000762+00
5	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:30:56.97508+00	2025-12-18 22:40:16.000762+00
6	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:31:57.280421+00	2025-12-18 22:40:16.000762+00
7	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:31:57.284889+00	2025-12-18 22:40:16.000762+00
8	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:31:57.289354+00	2025-12-18 22:40:16.000762+00
9	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:31:57.293492+00	2025-12-18 22:40:16.000762+00
10	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:32:57.570128+00	2025-12-18 22:40:16.000762+00
11	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:32:57.576705+00	2025-12-18 22:40:16.000762+00
12	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:32:57.581749+00	2025-12-18 22:40:16.000762+00
13	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:32:57.586926+00	2025-12-18 22:40:16.000762+00
14	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:33:57.859141+00	2025-12-18 22:40:16.000762+00
15	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:33:57.867568+00	2025-12-18 22:40:16.000762+00
16	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:33:57.87384+00	2025-12-18 22:40:16.000762+00
17	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:33:57.880768+00	2025-12-18 22:40:16.000762+00
18	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:34:58.141319+00	2025-12-18 22:40:16.000762+00
19	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:34:58.145863+00	2025-12-18 22:40:16.000762+00
20	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:34:58.149843+00	2025-12-18 22:40:16.000762+00
21	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:34:58.153762+00	2025-12-18 22:40:16.000762+00
22	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:35:58.408478+00	2025-12-18 22:40:16.000762+00
23	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:35:58.413876+00	2025-12-18 22:40:16.000762+00
24	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:35:58.418023+00	2025-12-18 22:40:16.000762+00
25	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:35:58.422065+00	2025-12-18 22:40:16.000762+00
26	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:36:58.65907+00	2025-12-18 22:40:16.000762+00
27	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:36:58.66358+00	2025-12-18 22:40:16.000762+00
28	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:36:58.66778+00	2025-12-18 22:40:16.000762+00
29	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:36:58.67204+00	2025-12-18 22:40:16.000762+00
30	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:37:58.900688+00	2025-12-18 22:40:16.000762+00
31	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:37:58.905363+00	2025-12-18 22:40:16.000762+00
32	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:37:58.910843+00	2025-12-18 22:40:16.000762+00
33	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:37:58.916408+00	2025-12-18 22:40:16.000762+00
34	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:38:59.180639+00	2025-12-18 22:40:16.000762+00
35	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:38:59.185156+00	2025-12-18 22:40:16.000762+00
36	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:38:59.189409+00	2025-12-18 22:40:16.000762+00
37	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:38:59.193438+00	2025-12-18 22:40:16.000762+00
38	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:39:49.430094+00	2025-12-18 22:40:16.000762+00
39	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:39:59.470503+00	2025-12-18 22:40:16.000762+00
40	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:39:59.475343+00	2025-12-18 22:40:16.000762+00
41	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:39:59.479994+00	2025-12-18 22:40:16.000762+00
\.


--
-- Data for Name: quotes; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.quotes (id, user_id, station_id, price_per_hour, free_period_min, deposit, expires_at, created_at, _ingested_at) FROM stdin;
28b19de5-7152-45ae-8f34-cef877c41885	u1	some-station-id	60	0	300	2025-12-18 22:30:45+00	2025-12-18 22:29:45.832398+00	2025-12-18 22:40:15.716569+00
\.


--
-- Data for Name: rentals; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.rentals (id, user_id, powerbank_id, price_per_hour, free_period_min, deposit, status, total_amount, started_at, finished_at, _ingested_at) FROM stdin;
8fb77e6c-4526-4395-921c-b8701264e602	user-1	powerbank_638	60	0	300	ACTIVE	10	2025-12-18 22:30:48.342423+00	\N	2025-12-18 22:40:15.778557+00
618734dc-5ac8-44ad-8b76-c3a5be379cc5	u1	powerbank_638	60	0	300	ACTIVE	11	2025-12-18 22:29:54.440494+00	\N	2025-12-18 22:40:15.778557+00
87261863-8d4d-4cbb-afed-89ef2dc571f7	user-2	powerbank_638	60	0	300	ACTIVE	10	2025-12-18 22:30:50.534547+00	\N	2025-12-18 22:40:15.778557+00
8b699903-1b8a-4aa7-b1ba-5372e0413c6b	user-3	powerbank_638	60	0	300	ACTIVE	10	2025-12-18 22:30:52.703792+00	\N	2025-12-18 22:40:15.778557+00
\.


--
-- Data for Name: fct_payments; Type: TABLE DATA; Schema: mart; Owner: -
--

COPY mart.fct_payments (payment_attempt_id, rental_id, amount, success, error, created_at) FROM stdin;
1	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:29:56.735935+00
2	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:30:56.961378+00
3	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:30:56.966203+00
4	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:30:56.970748+00
5	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:30:56.97508+00
6	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:31:57.280421+00
7	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:31:57.284889+00
8	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:31:57.289354+00
9	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:31:57.293492+00
10	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:32:57.570128+00
11	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:32:57.576705+00
12	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:32:57.581749+00
13	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:32:57.586926+00
14	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:33:57.859141+00
15	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:33:57.867568+00
16	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:33:57.87384+00
17	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:33:57.880768+00
18	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:34:58.141319+00
19	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:34:58.145863+00
20	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:34:58.149843+00
21	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:34:58.153762+00
22	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:35:58.408478+00
23	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:35:58.413876+00
24	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:35:58.418023+00
25	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:35:58.422065+00
26	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:36:58.65907+00
27	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:36:58.66358+00
28	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:36:58.66778+00
29	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:36:58.67204+00
30	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:37:58.900688+00
31	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:37:58.905363+00
32	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:37:58.910843+00
33	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:37:58.916408+00
34	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:38:59.180639+00
35	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:38:59.185156+00
36	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:38:59.189409+00
37	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:38:59.193438+00
38	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:39:49.430094+00
39	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:39:59.470503+00
40	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:39:59.475343+00
41	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:39:59.479994+00
\.


--
-- Data for Name: fct_rentals; Type: TABLE DATA; Schema: mart; Owner: -
--

COPY mart.fct_rentals (rental_id, user_id, powerbank_id, status, started_at, finished_at, total_amount, price_per_hour, free_period_min, deposit) FROM stdin;
8fb77e6c-4526-4395-921c-b8701264e602	user-1	powerbank_638	ACTIVE	2025-12-18 22:30:48.342423+00	\N	10	60	0	300
618734dc-5ac8-44ad-8b76-c3a5be379cc5	u1	powerbank_638	ACTIVE	2025-12-18 22:29:54.440494+00	\N	11	60	0	300
87261863-8d4d-4cbb-afed-89ef2dc571f7	user-2	powerbank_638	ACTIVE	2025-12-18 22:30:50.534547+00	\N	10	60	0	300
8b699903-1b8a-4aa7-b1ba-5372e0413c6b	user-3	powerbank_638	ACTIVE	2025-12-18 22:30:52.703792+00	\N	10	60	0	300
\.


--
-- Data for Name: kpi_daily; Type: TABLE DATA; Schema: mart; Owner: -
--

COPY mart.kpi_daily (day, quotes_cnt, rentals_started_cnt, rentals_finished_cnt, payments_attempts_cnt, payments_success_cnt, revenue_amount, avg_rental_duration_min) FROM stdin;
2025-12-18	1	4	0	41	41	41	\N
\.


--
-- Data for Name: etl_run_audit; Type: TABLE DATA; Schema: meta; Owner: -
--

COPY meta.etl_run_audit (run_id, dag_id, started_at, finished_at, status, details) FROM stdin;
\.


--
-- Data for Name: etl_watermark; Type: TABLE DATA; Schema: meta; Owner: -
--

COPY meta.etl_watermark (entity, watermark_value, updated_at) FROM stdin;
\.


--
-- Data for Name: debts; Type: TABLE DATA; Schema: raw_billing; Owner: -
--

COPY raw_billing.debts (rental_id, amount_total, updated_at, attempts, last_attempt_at, _ingested_at) FROM stdin;
\.


--
-- Data for Name: payment_attempts; Type: TABLE DATA; Schema: raw_billing; Owner: -
--

COPY raw_billing.payment_attempts (id, rental_id, amount, success, error, created_at, _ingested_at) FROM stdin;
1	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:29:56.735935+00	2025-12-18 22:40:16.000762+00
2	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:30:56.961378+00	2025-12-18 22:40:16.000762+00
3	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:30:56.966203+00	2025-12-18 22:40:16.000762+00
4	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:30:56.970748+00	2025-12-18 22:40:16.000762+00
5	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:30:56.97508+00	2025-12-18 22:40:16.000762+00
6	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:31:57.280421+00	2025-12-18 22:40:16.000762+00
7	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:31:57.284889+00	2025-12-18 22:40:16.000762+00
8	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:31:57.289354+00	2025-12-18 22:40:16.000762+00
9	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:31:57.293492+00	2025-12-18 22:40:16.000762+00
10	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:32:57.570128+00	2025-12-18 22:40:16.000762+00
11	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:32:57.576705+00	2025-12-18 22:40:16.000762+00
12	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:32:57.581749+00	2025-12-18 22:40:16.000762+00
13	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:32:57.586926+00	2025-12-18 22:40:16.000762+00
14	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:33:57.859141+00	2025-12-18 22:40:16.000762+00
15	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:33:57.867568+00	2025-12-18 22:40:16.000762+00
16	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:33:57.87384+00	2025-12-18 22:40:16.000762+00
17	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:33:57.880768+00	2025-12-18 22:40:16.000762+00
18	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:34:58.141319+00	2025-12-18 22:40:16.000762+00
19	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:34:58.145863+00	2025-12-18 22:40:16.000762+00
20	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:34:58.149843+00	2025-12-18 22:40:16.000762+00
21	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:34:58.153762+00	2025-12-18 22:40:16.000762+00
22	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:35:58.408478+00	2025-12-18 22:40:16.000762+00
23	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:35:58.413876+00	2025-12-18 22:40:16.000762+00
24	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:35:58.418023+00	2025-12-18 22:40:16.000762+00
25	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:35:58.422065+00	2025-12-18 22:40:16.000762+00
26	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:36:58.65907+00	2025-12-18 22:40:16.000762+00
27	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:36:58.66358+00	2025-12-18 22:40:16.000762+00
28	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:36:58.66778+00	2025-12-18 22:40:16.000762+00
29	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:36:58.67204+00	2025-12-18 22:40:16.000762+00
30	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:37:58.900688+00	2025-12-18 22:40:16.000762+00
31	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:37:58.905363+00	2025-12-18 22:40:16.000762+00
32	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:37:58.910843+00	2025-12-18 22:40:16.000762+00
33	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:37:58.916408+00	2025-12-18 22:40:16.000762+00
34	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:38:59.180639+00	2025-12-18 22:40:16.000762+00
35	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:38:59.185156+00	2025-12-18 22:40:16.000762+00
36	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:38:59.189409+00	2025-12-18 22:40:16.000762+00
37	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:38:59.193438+00	2025-12-18 22:40:16.000762+00
38	8fb77e6c-4526-4395-921c-b8701264e602	1	t	\N	2025-12-18 22:39:49.430094+00	2025-12-18 22:40:16.000762+00
39	618734dc-5ac8-44ad-8b76-c3a5be379cc5	1	t	\N	2025-12-18 22:39:59.470503+00	2025-12-18 22:40:16.000762+00
40	87261863-8d4d-4cbb-afed-89ef2dc571f7	1	t	\N	2025-12-18 22:39:59.475343+00	2025-12-18 22:40:16.000762+00
41	8b699903-1b8a-4aa7-b1ba-5372e0413c6b	1	t	\N	2025-12-18 22:39:59.479994+00	2025-12-18 22:40:16.000762+00
\.


--
-- Data for Name: idempotency_keys; Type: TABLE DATA; Schema: raw_rental; Owner: -
--

COPY raw_rental.idempotency_keys (key, scope, user_id, response_json, created_at, _ingested_at) FROM stdin;
bf7fa1b1-6acf-41be-a1ba-f66f739eaeb8	start	u1	{"order_id": "618734dc-5ac8-44ad-8b76-c3a5be379cc5", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:29:54.465788+00	2025-12-18 22:40:15.855958+00
7f8daa18-6a74-412e-ba8c-19fadf15952e	start	user-1	{"order_id": "8fb77e6c-4526-4395-921c-b8701264e602", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:30:48.360585+00	2025-12-18 22:40:15.855958+00
ce020279-25eb-4018-b8d5-49edc4767952	start	user-2	{"order_id": "87261863-8d4d-4cbb-afed-89ef2dc571f7", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:30:50.553056+00	2025-12-18 22:40:15.855958+00
cd899a28-9881-4bd9-bef1-f9a8f0a92f5f	start	user-3	{"order_id": "8b699903-1b8a-4aa7-b1ba-5372e0413c6b", "status": "ACTIVE", "powerbank_id": "powerbank_638", "total_amount": 0, "debt": 0}	2025-12-18 22:30:52.723054+00	2025-12-18 22:40:15.855958+00
\.


--
-- Data for Name: quotes; Type: TABLE DATA; Schema: raw_rental; Owner: -
--

COPY raw_rental.quotes (id, user_id, station_id, price_per_hour, free_period_min, deposit, expires_at, created_at, _ingested_at) FROM stdin;
28b19de5-7152-45ae-8f34-cef877c41885	u1	some-station-id	60	0	300	2025-12-18 22:30:45+00	2025-12-18 22:29:45.832398+00	2025-12-18 22:40:15.716569+00
\.


--
-- Data for Name: rentals; Type: TABLE DATA; Schema: raw_rental; Owner: -
--

COPY raw_rental.rentals (id, user_id, powerbank_id, price_per_hour, free_period_min, deposit, status, total_amount, started_at, finished_at, _ingested_at) FROM stdin;
8fb77e6c-4526-4395-921c-b8701264e602	user-1	powerbank_638	60	0	300	ACTIVE	10	2025-12-18 22:30:48.342423+00	\N	2025-12-18 22:40:15.778557+00
618734dc-5ac8-44ad-8b76-c3a5be379cc5	u1	powerbank_638	60	0	300	ACTIVE	11	2025-12-18 22:29:54.440494+00	\N	2025-12-18 22:40:15.778557+00
87261863-8d4d-4cbb-afed-89ef2dc571f7	user-2	powerbank_638	60	0	300	ACTIVE	10	2025-12-18 22:30:50.534547+00	\N	2025-12-18 22:40:15.778557+00
8b699903-1b8a-4aa7-b1ba-5372e0413c6b	user-3	powerbank_638	60	0	300	ACTIVE	10	2025-12-18 22:30:52.703792+00	\N	2025-12-18 22:40:15.778557+00
\.


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

\unrestrict jw47xYn7odhOS06jZLgc3TpeqwbIU8vIoBJtsF8fJi2NkU1AgHEvpTD16rgAcSF

