--
-- PostgreSQL database dump
--

\restrict AkyXkBgNqJXRJc50KlLrJ2hLeCMSrQeVmitivlt1aysTeXL2fPWRBRwutQnbgHA

-- Dumped from database version 14.22
-- Dumped by pg_dump version 18.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.audit_log (
    id bigint,
    username text,
    action text,
    details text,
    "timestamp" timestamp without time zone,
    company text
);


ALTER TABLE public.audit_log OWNER TO myappuser;

--
-- Name: billing_data; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.billing_data (
    id bigint,
    date text,
    account text,
    service text,
    cost double precision,
    synced_at text
);


ALTER TABLE public.billing_data OWNER TO myappuser;

--
-- Name: cloud_accounts; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.cloud_accounts (
    id bigint,
    username text,
    provider text,
    account_name text,
    account_identifier text,
    details text,
    credentials_encrypted text,
    sync_enabled bigint,
    status text,
    last_synced_at text,
    last_error text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    validation_status text,
    validation_message text,
    health_score bigint,
    last_validation_at text,
    sync_frequency_hours bigint,
    coverage_start text,
    coverage_end text,
    last_sync_duration_seconds double precision,
    last_sync_record_count bigint,
    next_sync_at text,
    company text
);


ALTER TABLE public.cloud_accounts OWNER TO myappuser;

--
-- Name: cloud_sync_runs; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.cloud_sync_runs (
    id bigint,
    cloud_account_id bigint,
    username text,
    provider text,
    status text,
    trigger_type text,
    started_at text,
    finished_at text,
    duration_seconds double precision,
    record_count bigint,
    coverage_start text,
    coverage_end text,
    error_code text,
    error_message text,
    metadata text,
    company text
);


ALTER TABLE public.cloud_sync_runs OWNER TO myappuser;

--
-- Name: companies; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.companies (
    company_name text,
    company_type text,
    plan text,
    created_by text,
    created_at text,
    updated_at text
);


ALTER TABLE public.companies OWNER TO myappuser;

--
-- Name: company_subscriptions; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.company_subscriptions (
    company_name text,
    plan text,
    billing_cycle text,
    subscription_status text,
    trial_started_at text,
    trial_ends_at text,
    cancel_at_period_end bigint,
    stripe_customer_id text,
    stripe_subscription_id text,
    stripe_checkout_session_id text,
    stripe_price_id text,
    current_period_end text,
    source text,
    last_synced_at text,
    updated_at text
);


ALTER TABLE public.company_subscriptions OWNER TO myappuser;

--
-- Name: forecast_notes; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.forecast_notes (
    username text,
    forecast_date text,
    note text
);


ALTER TABLE public.forecast_notes OWNER TO myappuser;

--
-- Name: recommendation_events; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.recommendation_events (
    id bigint,
    recommendation_id bigint,
    username text,
    action text,
    old_value text,
    new_value text,
    notes text,
    created_at text,
    company text
);


ALTER TABLE public.recommendation_events OWNER TO myappuser;

--
-- Name: recommendations; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.recommendations (
    id bigint,
    username text,
    account_identifier text,
    provider text,
    category text,
    title text,
    description text,
    status text,
    owner text,
    priority text,
    estimated_savings double precision,
    realized_savings double precision,
    due_date text,
    dismiss_reason text,
    source text,
    resource text,
    created_at text,
    updated_at text,
    completed_at text,
    confidence_score double precision,
    rationale text,
    effort_level text,
    action_steps text,
    company text
);


ALTER TABLE public.recommendations OWNER TO myappuser;

--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.subscriptions (
    username text,
    plan text,
    updated_at text
);


ALTER TABLE public.subscriptions OWNER TO myappuser;

--
-- Name: users; Type: TABLE; Schema: public; Owner: myappuser
--

CREATE TABLE public.users (
    username text,
    password text,
    role text,
    company text,
    user_type text,
    created_by text,
    created_at text,
    updated_at text,
    onboarding_complete bigint
);


ALTER TABLE public.users OWNER TO myappuser;

--
-- Data for Name: audit_log; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.audit_log (id, username, action, details, "timestamp", company) FROM stdin;
1	admin	login	\N	2026-03-13 18:31:29	Cloud Advisor Internal
2	admin	login	\N	2026-03-13 18:40:02	Cloud Advisor Internal
3	admin	login	\N	2026-03-13 18:42:19	Cloud Advisor Internal
4	admin	login	\N	2026-03-14 03:25:25	Cloud Advisor Internal
5	admin	login	\N	2026-03-14 03:36:38	Cloud Advisor Internal
6	admin	login	\N	2026-03-14 06:33:36	Cloud Advisor Internal
7	admin	login	\N	2026-03-14 09:02:40	Cloud Advisor Internal
8	admin	login	\N	2026-03-14 09:07:50	Cloud Advisor Internal
9	admin	login	\N	2026-03-14 09:15:11	Cloud Advisor Internal
10	admin	login	\N	2026-03-14 09:16:56	Cloud Advisor Internal
11	admin	login	\N	2026-03-14 09:18:39	Cloud Advisor Internal
12	admin	login	\N	2026-03-14 09:21:04	Cloud Advisor Internal
13	admin	login	\N	2026-03-14 09:22:13	Cloud Advisor Internal
14	admin	login	\N	2026-03-14 09:26:11	Cloud Advisor Internal
15	admin	login	\N	2026-03-14 09:33:54	Cloud Advisor Internal
16	admin	login	\N	2026-03-14 09:50:44	Cloud Advisor Internal
17	admin	login	\N	2026-03-14 09:58:37	Cloud Advisor Internal
18	admin	login	\N	2026-03-14 10:00:19	Cloud Advisor Internal
19	admin	login	\N	2026-03-14 10:01:41	Cloud Advisor Internal
20	admin	login	\N	2026-03-14 10:05:12	Cloud Advisor Internal
21	admin	login	\N	2026-03-14 10:07:13	Cloud Advisor Internal
22	admin	login	\N	2026-03-14 10:13:32	Cloud Advisor Internal
23	admin	login	\N	2026-03-14 10:15:06	Cloud Advisor Internal
24	guest	logout	\N	2026-03-14 10:18:35	guest
25	guest	logout	\N	2026-03-14 10:18:37	guest
26	guest	logout	\N	2026-03-14 10:18:39	guest
27	admin	login	\N	2026-03-14 10:20:33	Cloud Advisor Internal
28	admin	login	\N	2026-03-14 10:40:08	Cloud Advisor Internal
29	admin	login	\N	2026-03-14 10:55:01	Cloud Advisor Internal
30	admin	login	\N	2026-03-15 02:48:17	Cloud Advisor Internal
31	admin	login	\N	2026-03-15 02:51:53	Cloud Advisor Internal
32	admin	login	\N	2026-03-15 02:52:52	Cloud Advisor Internal
33	admin	login	\N	2026-03-15 02:58:00	Cloud Advisor Internal
34	admin	login	\N	2026-03-15 02:58:42	Cloud Advisor Internal
35	admin	login	\N	2026-03-15 03:01:21	Cloud Advisor Internal
36	admin	login	\N	2026-03-15 03:04:10	Cloud Advisor Internal
37	admin	login	\N	2026-03-15 03:05:52	Cloud Advisor Internal
38	admin	login	\N	2026-03-15 03:06:18	Cloud Advisor Internal
39	admin	login	\N	2026-03-15 03:07:42	Cloud Advisor Internal
40	admin	login	\N	2026-03-15 03:10:29	Cloud Advisor Internal
41	admin	login	\N	2026-03-15 03:12:11	Cloud Advisor Internal
42	admin	login	\N	2026-03-15 03:15:38	Cloud Advisor Internal
43	admin	login	\N	2026-03-15 03:17:08	Cloud Advisor Internal
44	admin	login	\N	2026-03-15 03:18:49	Cloud Advisor Internal
45	admin	login	\N	2026-03-15 03:19:50	Cloud Advisor Internal
46	admin	login	\N	2026-03-15 03:22:58	Cloud Advisor Internal
47	admin	login	\N	2026-03-15 03:24:01	Cloud Advisor Internal
48	admin	login	\N	2026-03-15 03:24:56	Cloud Advisor Internal
49	admin	login	\N	2026-03-15 05:37:17	Cloud Advisor Internal
50	admin	login	\N	2026-03-15 05:39:09	Cloud Advisor Internal
51	admin	login	\N	2026-03-15 05:40:43	Cloud Advisor Internal
52	admin	login	\N	2026-03-15 05:44:36	Cloud Advisor Internal
53	admin	login	\N	2026-03-15 05:46:23	Cloud Advisor Internal
54	admin	login	\N	2026-03-15 06:21:10	Cloud Advisor Internal
55	admin	login	\N	2026-03-15 06:29:04	Cloud Advisor Internal
56	admin	login	\N	2026-03-15 06:31:15	Cloud Advisor Internal
57	admin	login	\N	2026-03-15 06:35:47	Cloud Advisor Internal
58	admin	login	\N	2026-03-15 06:38:47	Cloud Advisor Internal
59	admin	login	\N	2026-03-15 06:41:24	Cloud Advisor Internal
60	admin	login	\N	2026-03-15 06:43:48	Cloud Advisor Internal
61	admin	login	\N	2026-03-15 06:53:02	Cloud Advisor Internal
62	admin	login	\N	2026-03-15 06:55:38	Cloud Advisor Internal
63	admin	login	\N	2026-03-15 08:38:19	Cloud Advisor Internal
64	admin	login	\N	2026-03-15 08:40:25	Cloud Advisor Internal
65	admin	login	\N	2026-03-15 09:08:42	Cloud Advisor Internal
66	admin	login	\N	2026-03-15 09:16:27	Cloud Advisor Internal
67	admin	login	\N	2026-03-15 09:19:03	Cloud Advisor Internal
68	admin	login	\N	2026-03-15 09:23:51	Cloud Advisor Internal
69	admin	login	\N	2026-03-15 09:28:53	Cloud Advisor Internal
70	admin	login	\N	2026-03-15 09:31:15	Cloud Advisor Internal
71	admin	login	\N	2026-03-15 09:38:33	Cloud Advisor Internal
72	admin	login	\N	2026-03-15 09:42:14	Cloud Advisor Internal
73	admin	login	\N	2026-03-15 09:47:15	Cloud Advisor Internal
74	admin	login	\N	2026-03-15 09:51:45	Cloud Advisor Internal
75	admin	login	\N	2026-03-15 09:57:22	Cloud Advisor Internal
76	admin	login	\N	2026-03-15 10:01:06	Cloud Advisor Internal
77	admin	login	\N	2026-03-15 10:30:19	Cloud Advisor Internal
78	admin	login	\N	2026-03-15 10:43:04	Cloud Advisor Internal
79	admin	demo_environment_seeded	accounts=3, billing_rows=720, recommendations=3	2026-03-15 10:43:47	Cloud Advisor Internal
80	admin	demo_environment_seeded	accounts=3, billing_rows=720, recommendations=3	2026-03-15 10:46:09	Cloud Advisor Internal
81	admin	login	\N	2026-03-15 10:48:47	Cloud Advisor Internal
82	admin	demo_environment_seeded	accounts=3, billing_rows=720, recommendations=3	2026-03-15 10:48:56	Cloud Advisor Internal
83	admin	login	\N	2026-03-15 10:52:37	Cloud Advisor Internal
84	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=9, recommendations=9	2026-03-15 10:53:15	Cloud Advisor Internal
85	admin	demo_environment_seeded	accounts=3, billing_rows=720, recommendations=3	2026-03-15 10:53:21	Cloud Advisor Internal
86	admin	login	\N	2026-03-15 11:02:43	Cloud Advisor Internal
87	admin	login	\N	2026-03-15 11:04:33	Cloud Advisor Internal
88	admin	login	\N	2026-03-15 11:10:03	Cloud Advisor Internal
89	admin	download_forecast_csv	model=Prophet, period=2	2026-03-15 11:14:15	Cloud Advisor Internal
90	admin	login	\N	2026-03-15 11:24:13	Cloud Advisor Internal
91	admin	demo_environment_seeded	accounts=3, billing_rows=720, recommendations=3	2026-03-15 11:24:28	Cloud Advisor Internal
92	admin	login	\N	2026-03-15 11:28:11	Cloud Advisor Internal
93	admin	login	\N	2026-03-15 11:30:22	Cloud Advisor Internal
94	admin	demo_environment_seeded	accounts=3, billing_rows=720, recommendations=3	2026-03-15 11:33:37	Cloud Advisor Internal
95	admin	login	\N	2026-03-15 11:35:13	Cloud Advisor Internal
96	admin	login	\N	2026-03-15 11:38:06	Cloud Advisor Internal
97	admin	login	\N	2026-03-15 11:41:58	Cloud Advisor Internal
98	admin	login	\N	2026-03-15 11:53:53	Cloud Advisor Internal
99	admin	login	\N	2026-03-15 11:55:48	Cloud Advisor Internal
100	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=9, recommendations=6	2026-03-15 11:56:04	Cloud Advisor Internal
101	admin	demo_environment_seeded	scenario=mixed_failures, accounts=3, billing_rows=720, recommendations=4	2026-03-15 11:56:04	Cloud Advisor Internal
102	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 11:56:50	Cloud Advisor Internal
103	admin	demo_environment_seeded	scenario=mixed_failures, accounts=3, billing_rows=720, recommendations=4	2026-03-15 11:56:51	Cloud Advisor Internal
104	admin	create_forecast_recommendation	recommendation_id=27, model=Linear Regression, period=1	2026-03-15 11:58:26	Cloud Advisor Internal
105	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 11:59:04	Cloud Advisor Internal
106	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-15 11:59:05	Cloud Advisor Internal
107	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 12:02:28	Cloud Advisor Internal
108	admin	demo_environment_seeded	scenario=waste_heavy, accounts=3, billing_rows=720, recommendations=3	2026-03-15 12:02:29	Cloud Advisor Internal
109	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=3	2026-03-15 12:02:45	Cloud Advisor Internal
110	admin	demo_environment_seeded	scenario=governance_failure, accounts=3, billing_rows=720, recommendations=4	2026-03-15 12:02:46	Cloud Advisor Internal
111	admin	login	\N	2026-03-15 12:05:37	Cloud Advisor Internal
112	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 12:05:51	Cloud Advisor Internal
113	admin	demo_environment_seeded	scenario=healthy, accounts=3, billing_rows=720, recommendations=1	2026-03-15 12:05:52	Cloud Advisor Internal
114	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=1	2026-03-15 12:06:10	Cloud Advisor Internal
115	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-15 12:06:11	Cloud Advisor Internal
116	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 12:06:27	Cloud Advisor Internal
117	admin	demo_environment_seeded	scenario=waste_heavy, accounts=3, billing_rows=720, recommendations=3	2026-03-15 12:06:28	Cloud Advisor Internal
118	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=3	2026-03-15 12:06:37	Cloud Advisor Internal
119	admin	demo_environment_seeded	scenario=governance_failure, accounts=3, billing_rows=720, recommendations=4	2026-03-15 12:06:38	Cloud Advisor Internal
120	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 12:08:27	Cloud Advisor Internal
121	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-15 12:08:27	Cloud Advisor Internal
122	admin	login	\N	2026-03-15 12:09:00	Cloud Advisor Internal
123	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 12:09:10	Cloud Advisor Internal
124	admin	demo_environment_seeded	scenario=healthy, accounts=3, billing_rows=720, recommendations=1	2026-03-15 12:09:10	Cloud Advisor Internal
125	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=1	2026-03-15 12:09:25	Cloud Advisor Internal
126	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-15 12:09:25	Cloud Advisor Internal
127	admin	login	\N	2026-03-15 12:12:27	Cloud Advisor Internal
128	admin	login	\N	2026-03-15 12:19:42	Cloud Advisor Internal
129	admin	login	\N	2026-03-15 12:23:21	Cloud Advisor Internal
130	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=7	2026-03-15 12:24:42	Cloud Advisor Internal
131	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-15 12:24:43	Cloud Advisor Internal
132	admin	login	\N	2026-03-15 12:26:29	Cloud Advisor Internal
133	admin	login	\N	2026-03-15 12:30:02	Cloud Advisor Internal
134	admin	login	\N	2026-03-15 12:55:57	Cloud Advisor Internal
135	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=7	2026-03-15 12:56:57	Cloud Advisor Internal
136	admin	demo_environment_reset	accounts=0, billing_rows=0, sync_runs=0, recommendations=0	2026-03-15 12:57:11	Cloud Advisor Internal
137	admin	demo_environment_seeded	scenario=mixed_failures, accounts=3, billing_rows=720, recommendations=4	2026-03-15 12:57:11	Cloud Advisor Internal
138	admin	login	\N	2026-03-15 12:59:01	Cloud Advisor Internal
139	admin	login	\N	2026-03-15 13:19:18	Cloud Advisor Internal
140	admin	login	\N	2026-03-15 13:22:46	Cloud Advisor Internal
141	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=10	2026-03-15 13:23:20	Cloud Advisor Internal
142	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-15 13:23:21	Cloud Advisor Internal
143	admin	login	\N	2026-03-15 13:29:37	Cloud Advisor Internal
144	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=4	2026-03-15 13:29:57	Cloud Advisor Internal
145	admin	demo_environment_seeded	scenario=healthy, accounts=3, billing_rows=720, recommendations=1	2026-03-15 13:29:57	Cloud Advisor Internal
146	admin	login	\N	2026-03-15 13:35:04	Cloud Advisor Internal
147	admin	login	\N	2026-03-15 13:37:25	Cloud Advisor Internal
148	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=1	2026-03-15 13:37:34	Cloud Advisor Internal
149	admin	demo_environment_seeded	scenario=waste_heavy, accounts=3, billing_rows=720, recommendations=3	2026-03-15 13:37:34	Cloud Advisor Internal
150	admin	login	\N	2026-03-15 13:41:07	Cloud Advisor Internal
151	admin	login	\N	2026-03-15 13:48:42	Cloud Advisor Internal
152	admin	login	\N	2026-03-15 13:51:11	Cloud Advisor Internal
153	admin	login	\N	2026-03-15 14:09:13	Cloud Advisor Internal
154	admin	login	\N	2026-03-15 14:12:58	Cloud Advisor Internal
155	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=3	2026-03-15 14:13:10	Cloud Advisor Internal
156	admin	demo_environment_seeded	scenario=healthy, accounts=3, billing_rows=720, recommendations=1	2026-03-15 14:13:10	Cloud Advisor Internal
157	admin	login	\N	2026-03-15 14:17:32	Cloud Advisor Internal
158	admin	login	\N	2026-03-15 14:19:25	Cloud Advisor Internal
159	admin	login	\N	2026-03-15 14:21:02	Cloud Advisor Internal
160	admin	login	\N	2026-03-15 14:23:15	Cloud Advisor Internal
161	admin	login	\N	2026-03-15 14:28:02	Cloud Advisor Internal
162	admin	login	\N	2026-03-15 14:29:36	Cloud Advisor Internal
163	admin	demo_environment_reset	accounts=3, billing_rows=720, sync_runs=3, recommendations=1	2026-03-15 14:29:49	Cloud Advisor Internal
164	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-15 14:29:50	Cloud Advisor Internal
165	admin	login	\N	2026-03-15 14:32:14	Cloud Advisor Internal
166	admin	login	\N	2026-03-15 14:34:32	Cloud Advisor Internal
167	admin	login	\N	2026-03-15 14:36:23	Cloud Advisor Internal
168	admin	login	\N	2026-03-15 14:40:51	Cloud Advisor Internal
169	admin	login	\N	2026-03-15 14:43:10	Cloud Advisor Internal
170	admin	login	\N	2026-03-15 14:44:48	Cloud Advisor Internal
171	admin	login	\N	2026-03-15 14:52:04	Cloud Advisor Internal
172	admin	login	\N	2026-03-15 15:00:22	Cloud Advisor Internal
173	admin	login	\N	2026-03-15 15:05:46	Cloud Advisor Internal
174	admin	login	\N	2026-03-15 15:10:08	Cloud Advisor Internal
175	admin	login	\N	2026-03-15 15:18:48	Cloud Advisor Internal
176	admin	login	\N	2026-03-15 15:21:33	Cloud Advisor Internal
177	admin	login	\N	2026-03-15 16:02:00	Cloud Advisor Internal
178	admin	login	\N	2026-03-15 16:15:12	Cloud Advisor Internal
179	admin	login	\N	2026-03-15 16:21:55	Cloud Advisor Internal
180	User1	login	\N	2026-03-15 16:24:50	Test
181	User1	demo_environment_reset	accounts=0, billing_rows=720, sync_runs=0, recommendations=0	2026-03-15 16:25:10	Test
182	User1	login	\N	2026-03-15 16:34:00	Test
183	User1	login	\N	2026-03-15 16:37:13	Test
184	User1	login	\N	2026-03-15 16:39:14	Test
185	User1	login	\N	2026-03-15 16:40:18	Test
186	Finance	login	\N	2026-03-15 16:41:15	Test
187	User1	login	\N	2026-03-15 16:43:22	Test
188	User1	login	\N	2026-03-16 04:40:30	Test
189	User1	login	\N	2026-03-16 04:43:10	Test
190	User1	login	\N	2026-03-16 04:45:36	Test
191	Finance	login	\N	2026-03-16 04:46:14	Test
192	User1	logout	\N	2026-03-16 14:45:38	Test
193	User1	login	\N	2026-03-16 14:45:45	Test
194	User1	logout	\N	2026-03-16 14:59:15	Test
195	admin	login	\N	2026-03-16 14:59:26	Cloud Advisor Internal
196	admin	logout	\N	2026-03-16 15:30:56	Cloud Advisor Internal
197	User1	login	\N	2026-03-16 15:31:09	Test
198	User1	logout	\N	2026-03-16 15:54:23	Test
199	admin	login	\N	2026-03-16 15:54:33	Cloud Advisor Internal
200	admin	demo_environment_reset	accounts=3, billing_rows=0, sync_runs=3, recommendations=7	2026-03-16 15:54:55	Cloud Advisor Internal
201	admin	demo_environment_seeded	scenario=cost_spike, accounts=3, billing_rows=720, recommendations=4	2026-03-16 15:54:56	Cloud Advisor Internal
202	admin	logout	\N	2026-03-16 16:47:05	Cloud Advisor Internal
203	admin	login	\N	2026-03-16 16:47:24	Cloud Advisor Internal
204	admin	logout	\N	2026-03-16 17:01:33	Cloud Advisor Internal
205	admin	login	\N	2026-03-16 17:01:40	Cloud Advisor Internal
206	admin	login	\N	2026-03-16 17:09:22	Cloud Advisor Internal
207	admin	logout	\N	2026-03-17 10:33:59	Cloud Advisor Internal
208	User1	login	\N	2026-03-17 10:34:07	Test
209	admin	login	\N	2026-03-18 17:28:54	Cloud Advisor Internal
210	admin	login	\N	2026-03-19 01:34:53	Cloud Advisor Internal
\.


--
-- Data for Name: billing_data; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.billing_data (id, date, account, service, cost, synced_at) FROM stdin;
1	2025-12-14	aws-prod	Blob Storage	108.39	\N
2	2025-12-14	aws-prod	SQL DB	105.14	\N
3	2025-12-14	aws-prod	S3	103.72	\N
4	2025-12-14	aws-dev	SQL DB	164	\N
5	2025-12-14	aws-dev	Blob Storage	181.22	\N
6	2025-12-14	aws-dev	Lambda	159.68	\N
7	2025-12-14	azure-main	RDS	61.78	\N
8	2025-12-14	azure-main	EC2	29.5	\N
9	2025-12-14	azure-main	Blob Storage	42.71	\N
10	2025-12-14	gcp-analytics	EC2	66.08	\N
11	2025-12-14	gcp-analytics	Blob Storage	129.04	\N
12	2025-12-14	gcp-analytics	S3	108.2	\N
13	2025-12-15	aws-prod	Blob Storage	80.94	\N
14	2025-12-15	aws-prod	VM	199.99	\N
15	2025-12-15	aws-prod	SQL DB	117.03	\N
16	2025-12-15	aws-dev	RDS	117.56	\N
17	2025-12-15	aws-dev	EC2	34.01	\N
18	2025-12-15	aws-dev	Lambda	192.55	\N
19	2025-12-15	azure-main	SQL DB	185.56	\N
20	2025-12-15	azure-main	S3	117.68	\N
21	2025-12-15	azure-main	VM	76.14	\N
22	2025-12-15	gcp-analytics	SQL DB	120.26	\N
23	2025-12-15	gcp-analytics	S3	22.48	\N
24	2025-12-15	gcp-analytics	VM	77.37	\N
25	2025-12-16	aws-prod	SQL DB	186.51	\N
26	2025-12-16	aws-prod	RDS	92.43	\N
27	2025-12-16	aws-prod	Lambda	29.4	\N
28	2025-12-16	aws-dev	RDS	105.2	\N
29	2025-12-16	aws-dev	S3	174.39	\N
30	2025-12-16	aws-dev	VM	12.34	\N
31	2025-12-16	azure-main	SQL DB	140.99	\N
32	2025-12-16	azure-main	RDS	45.5	\N
33	2025-12-16	azure-main	Lambda	87.13	\N
34	2025-12-16	gcp-analytics	Lambda	32.99	\N
35	2025-12-16	gcp-analytics	EC2	110.33	\N
36	2025-12-16	gcp-analytics	BigQuery	120.45	\N
37	2025-12-17	aws-prod	BigQuery	128.52	\N
38	2025-12-17	aws-prod	S3	48.67	\N
39	2025-12-17	aws-prod	Blob Storage	77.54	\N
40	2025-12-17	aws-dev	Blob Storage	167.89	\N
41	2025-12-17	aws-dev	BigQuery	84.75	\N
42	2025-12-17	aws-dev	RDS	96.28	\N
43	2025-12-17	azure-main	RDS	194.55	\N
44	2025-12-17	azure-main	VM	45.4	\N
45	2025-12-17	azure-main	SQL DB	136.53	\N
46	2025-12-17	gcp-analytics	S3	27.12	\N
47	2025-12-17	gcp-analytics	Blob Storage	91.48	\N
48	2025-12-17	gcp-analytics	BigQuery	47.9	\N
49	2025-12-18	aws-prod	Lambda	37.69	\N
50	2025-12-18	aws-prod	RDS	194.79	\N
51	2025-12-18	aws-prod	S3	53.94	\N
52	2025-12-18	aws-dev	SQL DB	22.65	\N
53	2025-12-18	aws-dev	S3	80.14	\N
54	2025-12-18	aws-dev	RDS	137.62	\N
55	2025-12-18	azure-main	BigQuery	161.4	\N
56	2025-12-18	azure-main	Blob Storage	39.31	\N
57	2025-12-18	azure-main	SQL DB	10.02	\N
58	2025-12-18	gcp-analytics	Lambda	17.86	\N
59	2025-12-18	gcp-analytics	SQL DB	81.73	\N
60	2025-12-18	gcp-analytics	EC2	148.49	\N
61	2025-12-19	aws-prod	EC2	166.06	\N
62	2025-12-19	aws-prod	SQL DB	132.49	\N
63	2025-12-19	aws-prod	Blob Storage	110.79	\N
64	2025-12-19	aws-dev	SQL DB	23.19	\N
65	2025-12-19	aws-dev	BigQuery	191.66	\N
66	2025-12-19	aws-dev	VM	88.52	\N
67	2025-12-19	azure-main	VM	114.23	\N
68	2025-12-19	azure-main	SQL DB	63.34	\N
69	2025-12-19	azure-main	Lambda	118.03	\N
70	2025-12-19	gcp-analytics	S3	104.73	\N
71	2025-12-19	gcp-analytics	Lambda	134.62	\N
72	2025-12-19	gcp-analytics	SQL DB	81.54	\N
73	2025-12-20	aws-prod	VM	82.6	\N
74	2025-12-20	aws-prod	Blob Storage	121.25	\N
75	2025-12-20	aws-prod	RDS	163.74	\N
76	2025-12-20	aws-dev	Lambda	29.88	\N
77	2025-12-20	aws-dev	S3	158.41	\N
78	2025-12-20	aws-dev	Blob Storage	188.64	\N
79	2025-12-20	azure-main	Blob Storage	28.24	\N
80	2025-12-20	azure-main	VM	122.39	\N
81	2025-12-20	azure-main	Lambda	121.97	\N
82	2025-12-20	gcp-analytics	Lambda	112	\N
83	2025-12-20	gcp-analytics	BigQuery	135.15	\N
84	2025-12-20	gcp-analytics	RDS	192.82	\N
85	2025-12-21	aws-prod	BigQuery	191.14	\N
86	2025-12-21	aws-prod	Lambda	158.71	\N
87	2025-12-21	aws-prod	S3	156.79	\N
88	2025-12-21	aws-dev	Blob Storage	188.02	\N
89	2025-12-21	aws-dev	EC2	199.92	\N
90	2025-12-21	aws-dev	S3	92.52	\N
91	2025-12-21	azure-main	BigQuery	147.57	\N
92	2025-12-21	azure-main	SQL DB	158.46	\N
93	2025-12-21	azure-main	S3	197.62	\N
94	2025-12-21	gcp-analytics	VM	132.13	\N
95	2025-12-21	gcp-analytics	S3	51.99	\N
96	2025-12-21	gcp-analytics	EC2	192.74	\N
97	2025-12-22	aws-prod	BigQuery	108.16	\N
98	2025-12-22	aws-prod	Blob Storage	163.23	\N
99	2025-12-22	aws-prod	EC2	14.14	\N
100	2025-12-22	aws-dev	Lambda	165.32	\N
101	2025-12-22	aws-dev	Blob Storage	174.9	\N
102	2025-12-22	aws-dev	EC2	163.03	\N
103	2025-12-22	azure-main	SQL DB	48.36	\N
104	2025-12-22	azure-main	EC2	194.67	\N
105	2025-12-22	azure-main	S3	49.78	\N
106	2025-12-22	gcp-analytics	VM	81.61	\N
107	2025-12-22	gcp-analytics	Lambda	15.44	\N
108	2025-12-22	gcp-analytics	EC2	194.06	\N
109	2025-12-23	aws-prod	Blob Storage	46.39	\N
110	2025-12-23	aws-prod	Lambda	93.32	\N
111	2025-12-23	aws-prod	S3	75.65	\N
112	2025-12-23	aws-dev	RDS	59.3	\N
113	2025-12-23	aws-dev	SQL DB	111.55	\N
114	2025-12-23	aws-dev	BigQuery	162.19	\N
115	2025-12-23	azure-main	EC2	102.25	\N
116	2025-12-23	azure-main	BigQuery	175.92	\N
117	2025-12-23	azure-main	Lambda	129.51	\N
118	2025-12-23	gcp-analytics	RDS	132.57	\N
119	2025-12-23	gcp-analytics	SQL DB	68.27	\N
120	2025-12-23	gcp-analytics	BigQuery	65.44	\N
121	2025-12-24	aws-prod	Lambda	28.31	\N
122	2025-12-24	aws-prod	RDS	72.01	\N
123	2025-12-24	aws-prod	VM	119.71	\N
124	2025-12-24	aws-dev	S3	83.15	\N
125	2025-12-24	aws-dev	SQL DB	188.32	\N
126	2025-12-24	aws-dev	Blob Storage	186.26	\N
127	2025-12-24	azure-main	S3	94.37	\N
128	2025-12-24	azure-main	SQL DB	130.03	\N
129	2025-12-24	azure-main	VM	190.47	\N
130	2025-12-24	gcp-analytics	BigQuery	28.76	\N
131	2025-12-24	gcp-analytics	EC2	55.53	\N
132	2025-12-24	gcp-analytics	S3	166.86	\N
133	2025-12-25	aws-prod	BigQuery	43.67	\N
134	2025-12-25	aws-prod	EC2	17.36	\N
135	2025-12-25	aws-prod	SQL DB	189.4	\N
136	2025-12-25	aws-dev	VM	77.81	\N
137	2025-12-25	aws-dev	EC2	142.39	\N
138	2025-12-25	aws-dev	BigQuery	101.88	\N
139	2025-12-25	azure-main	Lambda	69.28	\N
140	2025-12-25	azure-main	RDS	47.91	\N
141	2025-12-25	azure-main	Blob Storage	64.17	\N
142	2025-12-25	gcp-analytics	Blob Storage	71.74	\N
143	2025-12-25	gcp-analytics	Lambda	86.9	\N
144	2025-12-25	gcp-analytics	EC2	174.25	\N
145	2025-12-26	aws-prod	Blob Storage	18.45	\N
146	2025-12-26	aws-prod	BigQuery	121.23	\N
147	2025-12-26	aws-prod	SQL DB	197.26	\N
148	2025-12-26	aws-dev	EC2	60.07	\N
149	2025-12-26	aws-dev	Blob Storage	187.34	\N
150	2025-12-26	aws-dev	Lambda	14.37	\N
151	2025-12-26	azure-main	S3	17.22	\N
152	2025-12-26	azure-main	RDS	152.3	\N
153	2025-12-26	azure-main	BigQuery	21.43	\N
154	2025-12-26	gcp-analytics	VM	11.84	\N
155	2025-12-26	gcp-analytics	EC2	135.13	\N
156	2025-12-26	gcp-analytics	S3	88.17	\N
157	2025-12-27	aws-prod	RDS	14.71	\N
158	2025-12-27	aws-prod	SQL DB	163.32	\N
159	2025-12-27	aws-prod	EC2	194.01	\N
160	2025-12-27	aws-dev	Blob Storage	117.35	\N
161	2025-12-27	aws-dev	EC2	195.12	\N
162	2025-12-27	aws-dev	VM	62.8	\N
163	2025-12-27	azure-main	SQL DB	86.09	\N
164	2025-12-27	azure-main	BigQuery	18.08	\N
165	2025-12-27	azure-main	Blob Storage	66.63	\N
166	2025-12-27	gcp-analytics	Lambda	98.38	\N
167	2025-12-27	gcp-analytics	Blob Storage	73.87	\N
168	2025-12-27	gcp-analytics	S3	40.75	\N
169	2025-12-28	aws-prod	Lambda	35.04	\N
170	2025-12-28	aws-prod	VM	100.23	\N
171	2025-12-28	aws-prod	RDS	182.64	\N
172	2025-12-28	aws-dev	Lambda	86.4	\N
173	2025-12-28	aws-dev	VM	106.73	\N
174	2025-12-28	aws-dev	S3	160.59	\N
175	2025-12-28	azure-main	EC2	180.87	\N
176	2025-12-28	azure-main	RDS	20.62	\N
177	2025-12-28	azure-main	BigQuery	90.94	\N
178	2025-12-28	gcp-analytics	Blob Storage	107.19	\N
179	2025-12-28	gcp-analytics	Lambda	156.88	\N
180	2025-12-28	gcp-analytics	VM	163.66	\N
181	2025-12-29	aws-prod	Blob Storage	13.65	\N
182	2025-12-29	aws-prod	EC2	136.56	\N
183	2025-12-29	aws-prod	RDS	89.21	\N
184	2025-12-29	aws-dev	Lambda	60.86	\N
185	2025-12-29	aws-dev	RDS	118.48	\N
186	2025-12-29	aws-dev	BigQuery	74.7	\N
187	2025-12-29	azure-main	RDS	198.58	\N
188	2025-12-29	azure-main	BigQuery	196.9	\N
189	2025-12-29	azure-main	S3	114.63	\N
190	2025-12-29	gcp-analytics	BigQuery	93.59	\N
191	2025-12-29	gcp-analytics	Blob Storage	11.99	\N
192	2025-12-29	gcp-analytics	S3	142.22	\N
193	2025-12-30	aws-prod	BigQuery	134.47	\N
194	2025-12-30	aws-prod	VM	65.14	\N
195	2025-12-30	aws-prod	SQL DB	67.03	\N
196	2025-12-30	aws-dev	EC2	140.29	\N
197	2025-12-30	aws-dev	Lambda	187.53	\N
198	2025-12-30	aws-dev	S3	172.21	\N
199	2025-12-30	azure-main	BigQuery	68.26	\N
200	2025-12-30	azure-main	RDS	155.27	\N
201	2025-12-30	azure-main	S3	36.2	\N
202	2025-12-30	gcp-analytics	SQL DB	90.13	\N
203	2025-12-30	gcp-analytics	S3	165.24	\N
204	2025-12-30	gcp-analytics	Blob Storage	73.95	\N
205	2025-12-31	aws-prod	VM	159.5	\N
206	2025-12-31	aws-prod	S3	129.65	\N
207	2025-12-31	aws-prod	RDS	149.68	\N
208	2025-12-31	aws-dev	Blob Storage	27.74	\N
209	2025-12-31	aws-dev	EC2	78.56	\N
210	2025-12-31	aws-dev	Lambda	194.67	\N
211	2025-12-31	azure-main	Lambda	189.39	\N
212	2025-12-31	azure-main	BigQuery	40.87	\N
213	2025-12-31	azure-main	S3	144.78	\N
214	2025-12-31	gcp-analytics	SQL DB	37.45	\N
215	2025-12-31	gcp-analytics	S3	120.71	\N
216	2025-12-31	gcp-analytics	Blob Storage	166.23	\N
217	2026-01-01	aws-prod	BigQuery	134.38	\N
218	2026-01-01	aws-prod	VM	50.41	\N
219	2026-01-01	aws-prod	Blob Storage	158.28	\N
220	2026-01-01	aws-dev	S3	134.01	\N
221	2026-01-01	aws-dev	RDS	67.42	\N
222	2026-01-01	aws-dev	SQL DB	109.35	\N
223	2026-01-01	azure-main	EC2	12.31	\N
224	2026-01-01	azure-main	SQL DB	15.29	\N
225	2026-01-01	azure-main	RDS	118.36	\N
226	2026-01-01	gcp-analytics	S3	63.17	\N
227	2026-01-01	gcp-analytics	VM	36.39	\N
228	2026-01-01	gcp-analytics	Lambda	55.46	\N
229	2026-01-02	aws-prod	BigQuery	141.79	\N
230	2026-01-02	aws-prod	EC2	108.33	\N
231	2026-01-02	aws-prod	Blob Storage	191.82	\N
232	2026-01-02	aws-dev	SQL DB	162.81	\N
233	2026-01-02	aws-dev	Lambda	186.53	\N
234	2026-01-02	aws-dev	RDS	60.38	\N
235	2026-01-02	azure-main	RDS	103.98	\N
236	2026-01-02	azure-main	BigQuery	51.2	\N
237	2026-01-02	azure-main	Blob Storage	58.49	\N
238	2026-01-02	gcp-analytics	BigQuery	138.95	\N
239	2026-01-02	gcp-analytics	Lambda	109.31	\N
240	2026-01-02	gcp-analytics	S3	66.38	\N
241	2026-01-03	aws-prod	EC2	158.23	\N
242	2026-01-03	aws-prod	SQL DB	139.99	\N
243	2026-01-03	aws-prod	Lambda	85.05	\N
244	2026-01-03	aws-dev	Lambda	153.57	\N
245	2026-01-03	aws-dev	S3	50.35	\N
246	2026-01-03	aws-dev	EC2	194	\N
247	2026-01-03	azure-main	Lambda	118.52	\N
248	2026-01-03	azure-main	EC2	34.72	\N
249	2026-01-03	azure-main	Blob Storage	91.39	\N
250	2026-01-03	gcp-analytics	EC2	193.72	\N
251	2026-01-03	gcp-analytics	SQL DB	49.92	\N
252	2026-01-03	gcp-analytics	VM	168.25	\N
253	2026-01-04	aws-prod	EC2	102.64	\N
254	2026-01-04	aws-prod	RDS	167.47	\N
255	2026-01-04	aws-prod	VM	117.43	\N
256	2026-01-04	aws-dev	Lambda	178.22	\N
257	2026-01-04	aws-dev	Blob Storage	124.67	\N
258	2026-01-04	aws-dev	RDS	174.53	\N
259	2026-01-04	azure-main	SQL DB	60.93	\N
260	2026-01-04	azure-main	RDS	67.6	\N
261	2026-01-04	azure-main	S3	135.06	\N
262	2026-01-04	gcp-analytics	EC2	152.18	\N
263	2026-01-04	gcp-analytics	Blob Storage	124.75	\N
264	2026-01-04	gcp-analytics	S3	56.92	\N
265	2026-01-05	aws-prod	SQL DB	39.2	\N
266	2026-01-05	aws-prod	EC2	67.6	\N
267	2026-01-05	aws-prod	RDS	65.05	\N
268	2026-01-05	aws-dev	BigQuery	93.41	\N
269	2026-01-05	aws-dev	Lambda	159.46	\N
270	2026-01-05	aws-dev	Blob Storage	103.67	\N
271	2026-01-05	azure-main	Lambda	48.64	\N
272	2026-01-05	azure-main	EC2	166.76	\N
273	2026-01-05	azure-main	BigQuery	50.21	\N
274	2026-01-05	gcp-analytics	Lambda	123.98	\N
275	2026-01-05	gcp-analytics	BigQuery	178.38	\N
276	2026-01-05	gcp-analytics	S3	81.44	\N
277	2026-01-06	aws-prod	RDS	175.08	\N
278	2026-01-06	aws-prod	SQL DB	117.37	\N
279	2026-01-06	aws-prod	VM	190.87	\N
280	2026-01-06	aws-dev	Lambda	170.87	\N
281	2026-01-06	aws-dev	SQL DB	158.02	\N
282	2026-01-06	aws-dev	S3	89.16	\N
283	2026-01-06	azure-main	Blob Storage	103.78	\N
284	2026-01-06	azure-main	BigQuery	119.7	\N
285	2026-01-06	azure-main	SQL DB	90.85	\N
286	2026-01-06	gcp-analytics	VM	76	\N
287	2026-01-06	gcp-analytics	BigQuery	148.97	\N
288	2026-01-06	gcp-analytics	Blob Storage	82.3	\N
289	2026-01-07	aws-prod	S3	152.65	\N
290	2026-01-07	aws-prod	EC2	42.34	\N
291	2026-01-07	aws-prod	RDS	52.49	\N
292	2026-01-07	aws-dev	EC2	57.46	\N
293	2026-01-07	aws-dev	BigQuery	52.47	\N
294	2026-01-07	aws-dev	RDS	37.34	\N
295	2026-01-07	azure-main	BigQuery	122.3	\N
296	2026-01-07	azure-main	RDS	184.87	\N
297	2026-01-07	azure-main	S3	24.04	\N
298	2026-01-07	gcp-analytics	BigQuery	143.08	\N
299	2026-01-07	gcp-analytics	S3	128.41	\N
300	2026-01-07	gcp-analytics	VM	146.5	\N
301	2026-01-08	aws-prod	RDS	141.61	\N
302	2026-01-08	aws-prod	Lambda	141.42	\N
303	2026-01-08	aws-prod	Blob Storage	113.67	\N
304	2026-01-08	aws-dev	S3	119.77	\N
305	2026-01-08	aws-dev	EC2	114.33	\N
306	2026-01-08	aws-dev	SQL DB	196.83	\N
307	2026-01-08	azure-main	SQL DB	171.32	\N
308	2026-01-08	azure-main	S3	30.92	\N
309	2026-01-08	azure-main	BigQuery	28.7	\N
310	2026-01-08	gcp-analytics	S3	182.45	\N
311	2026-01-08	gcp-analytics	Lambda	23.95	\N
312	2026-01-08	gcp-analytics	BigQuery	16.26	\N
313	2026-01-09	aws-prod	EC2	192.08	\N
314	2026-01-09	aws-prod	Blob Storage	65.92	\N
315	2026-01-09	aws-prod	RDS	123.61	\N
316	2026-01-09	aws-dev	VM	112.17	\N
317	2026-01-09	aws-dev	SQL DB	147.23	\N
318	2026-01-09	aws-dev	S3	65.83	\N
319	2026-01-09	azure-main	Lambda	197.89	\N
320	2026-01-09	azure-main	Blob Storage	63.56	\N
321	2026-01-09	azure-main	EC2	105.81	\N
322	2026-01-09	gcp-analytics	SQL DB	12.56	\N
323	2026-01-09	gcp-analytics	S3	87.75	\N
324	2026-01-09	gcp-analytics	Blob Storage	164.85	\N
325	2026-01-10	aws-prod	SQL DB	114.76	\N
326	2026-01-10	aws-prod	S3	70.02	\N
327	2026-01-10	aws-prod	VM	72.82	\N
328	2026-01-10	aws-dev	S3	104.89	\N
329	2026-01-10	aws-dev	SQL DB	170.95	\N
330	2026-01-10	aws-dev	Lambda	67.56	\N
331	2026-01-10	azure-main	BigQuery	13.9	\N
332	2026-01-10	azure-main	EC2	48.12	\N
333	2026-01-10	azure-main	VM	87.14	\N
334	2026-01-10	gcp-analytics	EC2	83.98	\N
335	2026-01-10	gcp-analytics	RDS	170.96	\N
336	2026-01-10	gcp-analytics	VM	122.68	\N
337	2026-01-11	aws-prod	Lambda	180.43	\N
338	2026-01-11	aws-prod	EC2	80.47	\N
339	2026-01-11	aws-prod	RDS	129.74	\N
340	2026-01-11	aws-dev	BigQuery	24.09	\N
341	2026-01-11	aws-dev	EC2	35.91	\N
342	2026-01-11	aws-dev	VM	79.72	\N
343	2026-01-11	azure-main	BigQuery	107.79	\N
344	2026-01-11	azure-main	VM	119.33	\N
345	2026-01-11	azure-main	EC2	150.19	\N
346	2026-01-11	gcp-analytics	SQL DB	44.99	\N
347	2026-01-11	gcp-analytics	Blob Storage	50.1	\N
348	2026-01-11	gcp-analytics	RDS	165.69	\N
349	2026-01-12	aws-prod	VM	36.87	\N
350	2026-01-12	aws-prod	SQL DB	91.68	\N
351	2026-01-12	aws-prod	EC2	44.1	\N
352	2026-01-12	aws-dev	Blob Storage	23.01	\N
353	2026-01-12	aws-dev	BigQuery	157.42	\N
354	2026-01-12	aws-dev	SQL DB	91.76	\N
355	2026-01-12	azure-main	SQL DB	97.56	\N
356	2026-01-12	azure-main	BigQuery	10.96	\N
357	2026-01-12	azure-main	Blob Storage	78.44	\N
358	2026-01-12	gcp-analytics	BigQuery	63.87	\N
359	2026-01-12	gcp-analytics	RDS	179.66	\N
360	2026-01-12	gcp-analytics	SQL DB	149.39	\N
361	2026-01-13	aws-prod	BigQuery	164.25	\N
362	2026-01-13	aws-prod	RDS	52.78	\N
363	2026-01-13	aws-prod	EC2	61.09	\N
364	2026-01-13	aws-dev	Lambda	58.89	\N
365	2026-01-13	aws-dev	S3	168.58	\N
366	2026-01-13	aws-dev	Blob Storage	118.45	\N
367	2026-01-13	azure-main	RDS	109.87	\N
368	2026-01-13	azure-main	BigQuery	27.69	\N
369	2026-01-13	azure-main	VM	141.07	\N
370	2026-01-13	gcp-analytics	Blob Storage	41.99	\N
371	2026-01-13	gcp-analytics	BigQuery	15.08	\N
372	2026-01-13	gcp-analytics	SQL DB	64.73	\N
373	2026-01-14	aws-prod	BigQuery	84.67	\N
374	2026-01-14	aws-prod	SQL DB	198.21	\N
375	2026-01-14	aws-prod	S3	160.62	\N
376	2026-01-14	aws-dev	S3	100.65	\N
377	2026-01-14	aws-dev	SQL DB	136.46	\N
378	2026-01-14	aws-dev	RDS	105.65	\N
379	2026-01-14	azure-main	Lambda	43.14	\N
380	2026-01-14	azure-main	EC2	172.51	\N
381	2026-01-14	azure-main	Blob Storage	51.3	\N
382	2026-01-14	gcp-analytics	BigQuery	186.47	\N
383	2026-01-14	gcp-analytics	RDS	147.39	\N
384	2026-01-14	gcp-analytics	S3	133.1	\N
385	2026-01-15	aws-prod	S3	104.5	\N
386	2026-01-15	aws-prod	VM	142.91	\N
387	2026-01-15	aws-prod	RDS	80.15	\N
388	2026-01-15	aws-dev	Lambda	171.12	\N
389	2026-01-15	aws-dev	S3	136.59	\N
390	2026-01-15	aws-dev	Blob Storage	28.65	\N
391	2026-01-15	azure-main	S3	75.03	\N
392	2026-01-15	azure-main	BigQuery	176.59	\N
393	2026-01-15	azure-main	RDS	120.21	\N
394	2026-01-15	gcp-analytics	S3	167.91	\N
395	2026-01-15	gcp-analytics	EC2	120.28	\N
396	2026-01-15	gcp-analytics	Blob Storage	196.61	\N
397	2026-01-16	aws-prod	EC2	178.15	\N
398	2026-01-16	aws-prod	RDS	116.94	\N
399	2026-01-16	aws-prod	VM	105.97	\N
400	2026-01-16	aws-dev	RDS	93.5	\N
401	2026-01-16	aws-dev	S3	116.02	\N
402	2026-01-16	aws-dev	EC2	11.43	\N
403	2026-01-16	azure-main	SQL DB	136.55	\N
404	2026-01-16	azure-main	RDS	10.02	\N
405	2026-01-16	azure-main	EC2	125.4	\N
406	2026-01-16	gcp-analytics	Blob Storage	173.89	\N
407	2026-01-16	gcp-analytics	BigQuery	97.89	\N
408	2026-01-16	gcp-analytics	EC2	119.48	\N
409	2026-01-17	aws-prod	S3	118.21	\N
410	2026-01-17	aws-prod	BigQuery	172.23	\N
411	2026-01-17	aws-prod	VM	183.9	\N
412	2026-01-17	aws-dev	Blob Storage	150.68	\N
413	2026-01-17	aws-dev	RDS	76.19	\N
414	2026-01-17	aws-dev	SQL DB	182.12	\N
415	2026-01-17	azure-main	S3	28.19	\N
416	2026-01-17	azure-main	EC2	65.33	\N
417	2026-01-17	azure-main	Lambda	107.22	\N
418	2026-01-17	gcp-analytics	Blob Storage	159.84	\N
419	2026-01-17	gcp-analytics	RDS	63.34	\N
420	2026-01-17	gcp-analytics	Lambda	35.33	\N
421	2026-01-18	aws-prod	VM	191.58	\N
422	2026-01-18	aws-prod	BigQuery	66.66	\N
423	2026-01-18	aws-prod	Lambda	23.12	\N
424	2026-01-18	aws-dev	RDS	96.55	\N
425	2026-01-18	aws-dev	SQL DB	84.16	\N
426	2026-01-18	aws-dev	BigQuery	192.95	\N
427	2026-01-18	azure-main	EC2	101.72	\N
428	2026-01-18	azure-main	RDS	137.83	\N
429	2026-01-18	azure-main	SQL DB	116.92	\N
430	2026-01-18	gcp-analytics	S3	131.68	\N
431	2026-01-18	gcp-analytics	RDS	53.84	\N
432	2026-01-18	gcp-analytics	VM	153.01	\N
433	2026-01-19	aws-prod	Blob Storage	28.2	\N
434	2026-01-19	aws-prod	RDS	87.67	\N
435	2026-01-19	aws-prod	BigQuery	95.34	\N
436	2026-01-19	aws-dev	BigQuery	20.41	\N
437	2026-01-19	aws-dev	SQL DB	86.16	\N
438	2026-01-19	aws-dev	VM	160.88	\N
439	2026-01-19	azure-main	BigQuery	122.4	\N
440	2026-01-19	azure-main	SQL DB	79.01	\N
441	2026-01-19	azure-main	EC2	101.65	\N
442	2026-01-19	gcp-analytics	EC2	90.9	\N
443	2026-01-19	gcp-analytics	BigQuery	32.63	\N
444	2026-01-19	gcp-analytics	S3	169.41	\N
445	2026-01-20	aws-prod	BigQuery	44.24	\N
446	2026-01-20	aws-prod	EC2	76.07	\N
447	2026-01-20	aws-prod	Lambda	18.18	\N
448	2026-01-20	aws-dev	BigQuery	131.26	\N
449	2026-01-20	aws-dev	SQL DB	178.42	\N
450	2026-01-20	aws-dev	Lambda	143.09	\N
451	2026-01-20	azure-main	RDS	71.49	\N
452	2026-01-20	azure-main	EC2	131.64	\N
453	2026-01-20	azure-main	VM	104.72	\N
454	2026-01-20	gcp-analytics	SQL DB	32.48	\N
455	2026-01-20	gcp-analytics	BigQuery	95.93	\N
456	2026-01-20	gcp-analytics	VM	53.75	\N
457	2026-01-21	aws-prod	BigQuery	152.62	\N
458	2026-01-21	aws-prod	VM	44.17	\N
459	2026-01-21	aws-prod	Lambda	191.86	\N
460	2026-01-21	aws-dev	RDS	74.44	\N
461	2026-01-21	aws-dev	Blob Storage	63.04	\N
462	2026-01-21	aws-dev	EC2	30.17	\N
463	2026-01-21	azure-main	BigQuery	197.87	\N
464	2026-01-21	azure-main	RDS	69.56	\N
465	2026-01-21	azure-main	S3	29.98	\N
466	2026-01-21	gcp-analytics	S3	164.99	\N
467	2026-01-21	gcp-analytics	Blob Storage	188.65	\N
468	2026-01-21	gcp-analytics	EC2	35.57	\N
469	2026-01-22	aws-prod	EC2	163.61	\N
470	2026-01-22	aws-prod	RDS	169.4	\N
471	2026-01-22	aws-prod	BigQuery	20.88	\N
472	2026-01-22	aws-dev	Blob Storage	70.93	\N
473	2026-01-22	aws-dev	EC2	91.55	\N
474	2026-01-22	aws-dev	S3	101.2	\N
475	2026-01-22	azure-main	BigQuery	98.21	\N
476	2026-01-22	azure-main	Lambda	109.96	\N
477	2026-01-22	azure-main	RDS	137.88	\N
478	2026-01-22	gcp-analytics	SQL DB	105.76	\N
479	2026-01-22	gcp-analytics	VM	78.9	\N
480	2026-01-22	gcp-analytics	RDS	178.14	\N
481	2026-01-23	aws-prod	BigQuery	113	\N
482	2026-01-23	aws-prod	EC2	129.69	\N
483	2026-01-23	aws-prod	RDS	64.07	\N
484	2026-01-23	aws-dev	VM	94.77	\N
485	2026-01-23	aws-dev	EC2	115.57	\N
486	2026-01-23	aws-dev	Blob Storage	44.03	\N
487	2026-01-23	azure-main	Blob Storage	38.13	\N
488	2026-01-23	azure-main	RDS	187.2	\N
489	2026-01-23	azure-main	S3	135.82	\N
490	2026-01-23	gcp-analytics	RDS	120.82	\N
491	2026-01-23	gcp-analytics	Blob Storage	112.62	\N
492	2026-01-23	gcp-analytics	S3	177.98	\N
493	2026-01-24	aws-prod	SQL DB	102.41	\N
494	2026-01-24	aws-prod	BigQuery	119.33	\N
495	2026-01-24	aws-prod	Lambda	36.37	\N
496	2026-01-24	aws-dev	VM	55.5	\N
497	2026-01-24	aws-dev	Blob Storage	175.2	\N
498	2026-01-24	aws-dev	BigQuery	35.36	\N
499	2026-01-24	azure-main	Blob Storage	27.62	\N
500	2026-01-24	azure-main	VM	136.68	\N
501	2026-01-24	azure-main	Lambda	186.37	\N
502	2026-01-24	gcp-analytics	EC2	44.89	\N
503	2026-01-24	gcp-analytics	BigQuery	138.78	\N
504	2026-01-24	gcp-analytics	Lambda	103.86	\N
505	2026-01-25	aws-prod	S3	145.72	\N
506	2026-01-25	aws-prod	RDS	34.66	\N
507	2026-01-25	aws-prod	SQL DB	13.58	\N
508	2026-01-25	aws-dev	SQL DB	136.4	\N
509	2026-01-25	aws-dev	VM	16.99	\N
510	2026-01-25	aws-dev	EC2	49.71	\N
511	2026-01-25	azure-main	RDS	189.34	\N
512	2026-01-25	azure-main	S3	149	\N
513	2026-01-25	azure-main	BigQuery	173.99	\N
514	2026-01-25	gcp-analytics	SQL DB	151.69	\N
515	2026-01-25	gcp-analytics	BigQuery	83.53	\N
516	2026-01-25	gcp-analytics	S3	138.4	\N
517	2026-01-26	aws-prod	S3	83.9	\N
518	2026-01-26	aws-prod	VM	118.69	\N
519	2026-01-26	aws-prod	Blob Storage	100.01	\N
520	2026-01-26	aws-dev	SQL DB	63.71	\N
521	2026-01-26	aws-dev	Lambda	167.46	\N
522	2026-01-26	aws-dev	Blob Storage	45.37	\N
523	2026-01-26	azure-main	VM	159.73	\N
524	2026-01-26	azure-main	BigQuery	89.89	\N
525	2026-01-26	azure-main	SQL DB	23.5	\N
526	2026-01-26	gcp-analytics	RDS	95.12	\N
527	2026-01-26	gcp-analytics	EC2	76.21	\N
528	2026-01-26	gcp-analytics	Blob Storage	151.14	\N
529	2026-01-27	aws-prod	BigQuery	66.03	\N
530	2026-01-27	aws-prod	Blob Storage	110.66	\N
531	2026-01-27	aws-prod	VM	185.25	\N
532	2026-01-27	aws-dev	VM	51.84	\N
533	2026-01-27	aws-dev	BigQuery	102.98	\N
534	2026-01-27	aws-dev	Lambda	114.28	\N
535	2026-01-27	azure-main	RDS	158.99	\N
536	2026-01-27	azure-main	Lambda	125.63	\N
537	2026-01-27	azure-main	VM	121.39	\N
538	2026-01-27	gcp-analytics	VM	28.22	\N
539	2026-01-27	gcp-analytics	BigQuery	156.26	\N
540	2026-01-27	gcp-analytics	Blob Storage	46.05	\N
541	2026-01-28	aws-prod	VM	117.54	\N
542	2026-01-28	aws-prod	Blob Storage	190.13	\N
543	2026-01-28	aws-prod	S3	146.61	\N
544	2026-01-28	aws-dev	RDS	153.68	\N
545	2026-01-28	aws-dev	VM	22.94	\N
546	2026-01-28	aws-dev	EC2	104.37	\N
547	2026-01-28	azure-main	VM	76.22	\N
548	2026-01-28	azure-main	SQL DB	44.23	\N
549	2026-01-28	azure-main	EC2	178.44	\N
550	2026-01-28	gcp-analytics	BigQuery	112	\N
551	2026-01-28	gcp-analytics	S3	110.02	\N
552	2026-01-28	gcp-analytics	RDS	29.09	\N
553	2026-01-29	aws-prod	EC2	199.35	\N
554	2026-01-29	aws-prod	VM	149.68	\N
555	2026-01-29	aws-prod	BigQuery	183.94	\N
556	2026-01-29	aws-dev	S3	19.71	\N
557	2026-01-29	aws-dev	Blob Storage	106.4	\N
558	2026-01-29	aws-dev	RDS	46.44	\N
559	2026-01-29	azure-main	SQL DB	176.7	\N
560	2026-01-29	azure-main	Blob Storage	180.6	\N
561	2026-01-29	azure-main	Lambda	166.94	\N
562	2026-01-29	gcp-analytics	Lambda	41.85	\N
563	2026-01-29	gcp-analytics	SQL DB	15.78	\N
564	2026-01-29	gcp-analytics	VM	130.39	\N
565	2026-01-30	aws-prod	VM	142.16	\N
566	2026-01-30	aws-prod	RDS	36.43	\N
567	2026-01-30	aws-prod	SQL DB	136.44	\N
568	2026-01-30	aws-dev	Blob Storage	102.6	\N
569	2026-01-30	aws-dev	RDS	10.48	\N
570	2026-01-30	aws-dev	S3	125.55	\N
571	2026-01-30	azure-main	EC2	146.93	\N
572	2026-01-30	azure-main	BigQuery	62.44	\N
573	2026-01-30	azure-main	Blob Storage	191.38	\N
574	2026-01-30	gcp-analytics	SQL DB	24.72	\N
575	2026-01-30	gcp-analytics	BigQuery	114.73	\N
576	2026-01-30	gcp-analytics	EC2	142.44	\N
577	2026-01-31	aws-prod	SQL DB	143.75	\N
578	2026-01-31	aws-prod	EC2	10.47	\N
579	2026-01-31	aws-prod	RDS	55.68	\N
580	2026-01-31	aws-dev	RDS	119.19	\N
581	2026-01-31	aws-dev	BigQuery	117.24	\N
582	2026-01-31	aws-dev	S3	161.87	\N
583	2026-01-31	azure-main	VM	60.74	\N
584	2026-01-31	azure-main	S3	130.82	\N
585	2026-01-31	azure-main	Blob Storage	138.34	\N
586	2026-01-31	gcp-analytics	S3	176.09	\N
587	2026-01-31	gcp-analytics	EC2	122.33	\N
588	2026-01-31	gcp-analytics	SQL DB	102.45	\N
589	2026-02-01	aws-prod	BigQuery	133.69	\N
590	2026-02-01	aws-prod	VM	164.84	\N
591	2026-02-01	aws-prod	SQL DB	145.72	\N
592	2026-02-01	aws-dev	RDS	85.58	\N
593	2026-02-01	aws-dev	Lambda	13.39	\N
594	2026-02-01	aws-dev	BigQuery	133.84	\N
595	2026-02-01	azure-main	BigQuery	24.48	\N
596	2026-02-01	azure-main	Blob Storage	119.65	\N
597	2026-02-01	azure-main	VM	125.47	\N
598	2026-02-01	gcp-analytics	EC2	161.65	\N
599	2026-02-01	gcp-analytics	RDS	37.94	\N
600	2026-02-01	gcp-analytics	VM	113.9	\N
601	2026-02-02	aws-prod	EC2	50.4	\N
602	2026-02-02	aws-prod	BigQuery	120.09	\N
603	2026-02-02	aws-prod	VM	71.8	\N
604	2026-02-02	aws-dev	SQL DB	52.46	\N
605	2026-02-02	aws-dev	Lambda	67.1	\N
606	2026-02-02	aws-dev	VM	111.97	\N
607	2026-02-02	azure-main	SQL DB	140.67	\N
608	2026-02-02	azure-main	VM	115.82	\N
609	2026-02-02	azure-main	Blob Storage	22.28	\N
610	2026-02-02	gcp-analytics	VM	79.76	\N
611	2026-02-02	gcp-analytics	RDS	169.93	\N
612	2026-02-02	gcp-analytics	EC2	127.86	\N
613	2026-02-03	aws-prod	VM	111.71	\N
614	2026-02-03	aws-prod	Lambda	124.52	\N
615	2026-02-03	aws-prod	S3	157.02	\N
616	2026-02-03	aws-dev	BigQuery	134.36	\N
617	2026-02-03	aws-dev	Lambda	133.44	\N
618	2026-02-03	aws-dev	S3	95.82	\N
619	2026-02-03	azure-main	RDS	199.97	\N
620	2026-02-03	azure-main	VM	58.74	\N
621	2026-02-03	azure-main	S3	36.88	\N
622	2026-02-03	gcp-analytics	S3	117.55	\N
623	2026-02-03	gcp-analytics	BigQuery	76.13	\N
624	2026-02-03	gcp-analytics	EC2	40.63	\N
625	2026-02-04	aws-prod	S3	13.34	\N
626	2026-02-04	aws-prod	SQL DB	185.91	\N
627	2026-02-04	aws-prod	Blob Storage	12.02	\N
628	2026-02-04	aws-dev	SQL DB	124.1	\N
629	2026-02-04	aws-dev	EC2	104.57	\N
630	2026-02-04	aws-dev	Blob Storage	151	\N
631	2026-02-04	azure-main	SQL DB	199.33	\N
632	2026-02-04	azure-main	Lambda	89.43	\N
633	2026-02-04	azure-main	Blob Storage	62.48	\N
634	2026-02-04	gcp-analytics	Blob Storage	47.7	\N
635	2026-02-04	gcp-analytics	Lambda	189.44	\N
636	2026-02-04	gcp-analytics	BigQuery	158.84	\N
637	2026-02-05	aws-prod	BigQuery	92.08	\N
638	2026-02-05	aws-prod	Lambda	102.34	\N
639	2026-02-05	aws-prod	S3	117.32	\N
640	2026-02-05	aws-dev	EC2	95.63	\N
641	2026-02-05	aws-dev	S3	57.13	\N
642	2026-02-05	aws-dev	SQL DB	195.13	\N
643	2026-02-05	azure-main	EC2	81.61	\N
644	2026-02-05	azure-main	Blob Storage	92.28	\N
645	2026-02-05	azure-main	S3	22.83	\N
646	2026-02-05	gcp-analytics	EC2	45.56	\N
647	2026-02-05	gcp-analytics	VM	163.93	\N
648	2026-02-05	gcp-analytics	Lambda	183.93	\N
649	2026-02-06	aws-prod	BigQuery	60.31	\N
976	2026-03-05	aws-dev	S3	89.23	\N
650	2026-02-06	aws-prod	Blob Storage	183.84	\N
651	2026-02-06	aws-prod	S3	164.23	\N
652	2026-02-06	aws-dev	VM	197.61	\N
653	2026-02-06	aws-dev	S3	158.6	\N
654	2026-02-06	aws-dev	SQL DB	70.3	\N
655	2026-02-06	azure-main	BigQuery	13.96	\N
656	2026-02-06	azure-main	Blob Storage	47.87	\N
657	2026-02-06	azure-main	S3	170.77	\N
658	2026-02-06	gcp-analytics	SQL DB	30.26	\N
659	2026-02-06	gcp-analytics	Lambda	57.41	\N
660	2026-02-06	gcp-analytics	Blob Storage	177.08	\N
661	2026-02-07	aws-prod	Lambda	103.61	\N
662	2026-02-07	aws-prod	S3	67.86	\N
663	2026-02-07	aws-prod	RDS	186.34	\N
664	2026-02-07	aws-dev	RDS	110.77	\N
665	2026-02-07	aws-dev	Blob Storage	171.38	\N
666	2026-02-07	aws-dev	BigQuery	186.57	\N
667	2026-02-07	azure-main	S3	148.52	\N
668	2026-02-07	azure-main	Lambda	112.2	\N
669	2026-02-07	azure-main	BigQuery	25	\N
670	2026-02-07	gcp-analytics	BigQuery	48.44	\N
671	2026-02-07	gcp-analytics	RDS	79.11	\N
672	2026-02-07	gcp-analytics	S3	119.89	\N
673	2026-02-08	aws-prod	BigQuery	190.8	\N
674	2026-02-08	aws-prod	EC2	80.49	\N
675	2026-02-08	aws-prod	RDS	85.1	\N
676	2026-02-08	aws-dev	VM	114.9	\N
677	2026-02-08	aws-dev	Lambda	116.57	\N
678	2026-02-08	aws-dev	S3	66.84	\N
679	2026-02-08	azure-main	BigQuery	23.51	\N
680	2026-02-08	azure-main	VM	49.98	\N
681	2026-02-08	azure-main	Blob Storage	55.37	\N
682	2026-02-08	gcp-analytics	Blob Storage	51.83	\N
683	2026-02-08	gcp-analytics	RDS	42.22	\N
684	2026-02-08	gcp-analytics	SQL DB	174.21	\N
685	2026-02-09	aws-prod	VM	25.95	\N
686	2026-02-09	aws-prod	Blob Storage	40.26	\N
687	2026-02-09	aws-prod	RDS	31.19	\N
688	2026-02-09	aws-dev	SQL DB	188.35	\N
689	2026-02-09	aws-dev	Lambda	24.77	\N
690	2026-02-09	aws-dev	VM	114.38	\N
691	2026-02-09	azure-main	BigQuery	45.31	\N
692	2026-02-09	azure-main	RDS	185.03	\N
693	2026-02-09	azure-main	S3	152.62	\N
694	2026-02-09	gcp-analytics	Blob Storage	78.47	\N
695	2026-02-09	gcp-analytics	EC2	24.17	\N
696	2026-02-09	gcp-analytics	VM	131.23	\N
697	2026-02-10	aws-prod	RDS	170.9	\N
698	2026-02-10	aws-prod	EC2	41.17	\N
699	2026-02-10	aws-prod	Blob Storage	120.17	\N
700	2026-02-10	aws-dev	SQL DB	80.83	\N
701	2026-02-10	aws-dev	EC2	75.26	\N
702	2026-02-10	aws-dev	Blob Storage	87.34	\N
703	2026-02-10	azure-main	EC2	149.15	\N
704	2026-02-10	azure-main	SQL DB	38.87	\N
705	2026-02-10	azure-main	S3	61.72	\N
706	2026-02-10	gcp-analytics	RDS	51.03	\N
707	2026-02-10	gcp-analytics	Blob Storage	35.63	\N
708	2026-02-10	gcp-analytics	Lambda	138.49	\N
709	2026-02-11	aws-prod	EC2	141.05	\N
710	2026-02-11	aws-prod	VM	88.71	\N
711	2026-02-11	aws-prod	RDS	63.32	\N
712	2026-02-11	aws-dev	Lambda	93.07	\N
713	2026-02-11	aws-dev	S3	193.03	\N
714	2026-02-11	aws-dev	Blob Storage	31.37	\N
715	2026-02-11	azure-main	SQL DB	193.19	\N
716	2026-02-11	azure-main	RDS	184.58	\N
717	2026-02-11	azure-main	VM	99.59	\N
718	2026-02-11	gcp-analytics	RDS	32.41	\N
719	2026-02-11	gcp-analytics	BigQuery	63.37	\N
720	2026-02-11	gcp-analytics	VM	104.11	\N
721	2026-02-12	aws-prod	Blob Storage	179.61	\N
722	2026-02-12	aws-prod	VM	174.23	\N
723	2026-02-12	aws-prod	S3	166.33	\N
724	2026-02-12	aws-dev	BigQuery	82.96	\N
725	2026-02-12	aws-dev	SQL DB	176.56	\N
726	2026-02-12	aws-dev	Blob Storage	106.03	\N
727	2026-02-12	azure-main	RDS	35.62	\N
728	2026-02-12	azure-main	S3	98.3	\N
729	2026-02-12	azure-main	EC2	43.23	\N
730	2026-02-12	gcp-analytics	Blob Storage	37.88	\N
731	2026-02-12	gcp-analytics	VM	141.76	\N
732	2026-02-12	gcp-analytics	EC2	29.27	\N
733	2026-02-13	aws-prod	EC2	77.83	\N
734	2026-02-13	aws-prod	SQL DB	107.52	\N
735	2026-02-13	aws-prod	VM	159.79	\N
736	2026-02-13	aws-dev	S3	177.87	\N
737	2026-02-13	aws-dev	BigQuery	153.13	\N
738	2026-02-13	aws-dev	EC2	25.45	\N
739	2026-02-13	azure-main	Blob Storage	106.47	\N
740	2026-02-13	azure-main	S3	69.05	\N
741	2026-02-13	azure-main	VM	33.1	\N
742	2026-02-13	gcp-analytics	S3	168.25	\N
743	2026-02-13	gcp-analytics	Lambda	183.93	\N
744	2026-02-13	gcp-analytics	VM	88.14	\N
745	2026-02-14	aws-prod	EC2	70.08	\N
746	2026-02-14	aws-prod	S3	40.67	\N
747	2026-02-14	aws-prod	VM	197.98	\N
748	2026-02-14	aws-dev	Lambda	21.1	\N
749	2026-02-14	aws-dev	VM	161.36	\N
750	2026-02-14	aws-dev	BigQuery	144.73	\N
751	2026-02-14	azure-main	EC2	177.01	\N
752	2026-02-14	azure-main	Blob Storage	145.89	\N
753	2026-02-14	azure-main	VM	118.66	\N
754	2026-02-14	gcp-analytics	VM	188.46	\N
755	2026-02-14	gcp-analytics	S3	61.64	\N
756	2026-02-14	gcp-analytics	Lambda	122.72	\N
757	2026-02-15	aws-prod	Blob Storage	131.83	\N
758	2026-02-15	aws-prod	EC2	149.91	\N
759	2026-02-15	aws-prod	BigQuery	165.23	\N
760	2026-02-15	aws-dev	SQL DB	146.82	\N
761	2026-02-15	aws-dev	Lambda	196.58	\N
762	2026-02-15	aws-dev	BigQuery	81.66	\N
763	2026-02-15	azure-main	Blob Storage	167.56	\N
764	2026-02-15	azure-main	RDS	111.14	\N
765	2026-02-15	azure-main	Lambda	171.97	\N
766	2026-02-15	gcp-analytics	Blob Storage	134.79	\N
767	2026-02-15	gcp-analytics	BigQuery	75.34	\N
768	2026-02-15	gcp-analytics	S3	100.2	\N
769	2026-02-16	aws-prod	RDS	198.85	\N
770	2026-02-16	aws-prod	SQL DB	197.01	\N
771	2026-02-16	aws-prod	VM	43.6	\N
772	2026-02-16	aws-dev	S3	37.76	\N
773	2026-02-16	aws-dev	VM	44.96	\N
774	2026-02-16	aws-dev	EC2	70.12	\N
775	2026-02-16	azure-main	RDS	190.32	\N
776	2026-02-16	azure-main	Blob Storage	150	\N
777	2026-02-16	azure-main	Lambda	105.88	\N
778	2026-02-16	gcp-analytics	SQL DB	25.28	\N
779	2026-02-16	gcp-analytics	S3	100.11	\N
780	2026-02-16	gcp-analytics	Lambda	100.27	\N
781	2026-02-17	aws-prod	EC2	83.72	\N
782	2026-02-17	aws-prod	SQL DB	106.8	\N
783	2026-02-17	aws-prod	Blob Storage	58.29	\N
784	2026-02-17	aws-dev	EC2	40.7	\N
785	2026-02-17	aws-dev	SQL DB	181.34	\N
786	2026-02-17	aws-dev	BigQuery	141.84	\N
787	2026-02-17	azure-main	S3	106.81	\N
788	2026-02-17	azure-main	VM	137.57	\N
789	2026-02-17	azure-main	Blob Storage	65.02	\N
790	2026-02-17	gcp-analytics	Blob Storage	90.41	\N
791	2026-02-17	gcp-analytics	EC2	110.51	\N
792	2026-02-17	gcp-analytics	RDS	146.34	\N
793	2026-02-18	aws-prod	BigQuery	96.95	\N
794	2026-02-18	aws-prod	EC2	166.3	\N
795	2026-02-18	aws-prod	SQL DB	176.87	\N
796	2026-02-18	aws-dev	RDS	129.14	\N
797	2026-02-18	aws-dev	EC2	89.44	\N
798	2026-02-18	aws-dev	Lambda	188.22	\N
799	2026-02-18	azure-main	EC2	183.8	\N
800	2026-02-18	azure-main	Blob Storage	169.04	\N
801	2026-02-18	azure-main	Lambda	23.92	\N
802	2026-02-18	gcp-analytics	SQL DB	149.71	\N
803	2026-02-18	gcp-analytics	EC2	24.3	\N
804	2026-02-18	gcp-analytics	RDS	190.53	\N
805	2026-02-19	aws-prod	SQL DB	78.42	\N
806	2026-02-19	aws-prod	Lambda	10.72	\N
807	2026-02-19	aws-prod	BigQuery	181.75	\N
808	2026-02-19	aws-dev	EC2	150.95	\N
809	2026-02-19	aws-dev	BigQuery	116.4	\N
810	2026-02-19	aws-dev	S3	143.15	\N
811	2026-02-19	azure-main	Lambda	92.77	\N
812	2026-02-19	azure-main	EC2	116.38	\N
813	2026-02-19	azure-main	RDS	175.13	\N
814	2026-02-19	gcp-analytics	Lambda	153.36	\N
815	2026-02-19	gcp-analytics	S3	30.31	\N
816	2026-02-19	gcp-analytics	SQL DB	146.15	\N
817	2026-02-20	aws-prod	Lambda	131.27	\N
818	2026-02-20	aws-prod	SQL DB	75.95	\N
819	2026-02-20	aws-prod	VM	186.92	\N
820	2026-02-20	aws-dev	S3	89.09	\N
821	2026-02-20	aws-dev	Lambda	23.2	\N
822	2026-02-20	aws-dev	VM	21	\N
823	2026-02-20	azure-main	SQL DB	134.39	\N
824	2026-02-20	azure-main	Lambda	104.21	\N
825	2026-02-20	azure-main	Blob Storage	177.1	\N
826	2026-02-20	gcp-analytics	VM	114.52	\N
827	2026-02-20	gcp-analytics	SQL DB	16.14	\N
828	2026-02-20	gcp-analytics	BigQuery	136.29	\N
829	2026-02-21	aws-prod	Lambda	119.68	\N
830	2026-02-21	aws-prod	RDS	109.08	\N
831	2026-02-21	aws-prod	BigQuery	144.58	\N
832	2026-02-21	aws-dev	BigQuery	95.41	\N
833	2026-02-21	aws-dev	S3	139.94	\N
834	2026-02-21	aws-dev	Lambda	133.4	\N
835	2026-02-21	azure-main	S3	199.48	\N
836	2026-02-21	azure-main	Lambda	188.23	\N
837	2026-02-21	azure-main	BigQuery	150.86	\N
838	2026-02-21	gcp-analytics	SQL DB	170.76	\N
839	2026-02-21	gcp-analytics	Blob Storage	47.64	\N
840	2026-02-21	gcp-analytics	S3	20.13	\N
841	2026-02-22	aws-prod	VM	133.18	\N
842	2026-02-22	aws-prod	RDS	82.28	\N
843	2026-02-22	aws-prod	Lambda	79.77	\N
844	2026-02-22	aws-dev	VM	67.38	\N
845	2026-02-22	aws-dev	Blob Storage	182.09	\N
846	2026-02-22	aws-dev	SQL DB	90.66	\N
847	2026-02-22	azure-main	Blob Storage	19.5	\N
848	2026-02-22	azure-main	BigQuery	106.74	\N
849	2026-02-22	azure-main	Lambda	139.67	\N
850	2026-02-22	gcp-analytics	VM	126.31	\N
851	2026-02-22	gcp-analytics	BigQuery	23.21	\N
852	2026-02-22	gcp-analytics	Blob Storage	64.6	\N
853	2026-02-23	aws-prod	RDS	154.43	\N
854	2026-02-23	aws-prod	SQL DB	71.08	\N
855	2026-02-23	aws-prod	S3	16.37	\N
856	2026-02-23	aws-dev	Blob Storage	119.12	\N
857	2026-02-23	aws-dev	RDS	131.52	\N
858	2026-02-23	aws-dev	BigQuery	134.93	\N
859	2026-02-23	azure-main	SQL DB	175.68	\N
860	2026-02-23	azure-main	RDS	37.85	\N
861	2026-02-23	azure-main	Blob Storage	152.15	\N
862	2026-02-23	gcp-analytics	S3	193.39	\N
863	2026-02-23	gcp-analytics	RDS	119.76	\N
864	2026-02-23	gcp-analytics	BigQuery	101.41	\N
865	2026-02-24	aws-prod	Blob Storage	46.67	\N
866	2026-02-24	aws-prod	BigQuery	179.61	\N
867	2026-02-24	aws-prod	Lambda	56.5	\N
868	2026-02-24	aws-dev	Blob Storage	122.23	\N
869	2026-02-24	aws-dev	EC2	161.46	\N
870	2026-02-24	aws-dev	BigQuery	120.35	\N
871	2026-02-24	azure-main	SQL DB	190.57	\N
872	2026-02-24	azure-main	BigQuery	28.61	\N
873	2026-02-24	azure-main	RDS	140	\N
874	2026-02-24	gcp-analytics	RDS	53.92	\N
875	2026-02-24	gcp-analytics	SQL DB	101.8	\N
876	2026-02-24	gcp-analytics	Lambda	183	\N
877	2026-02-25	aws-prod	SQL DB	26.37	\N
878	2026-02-25	aws-prod	VM	84.98	\N
879	2026-02-25	aws-prod	Blob Storage	116.49	\N
880	2026-02-25	aws-dev	RDS	51.26	\N
881	2026-02-25	aws-dev	Blob Storage	186.94	\N
882	2026-02-25	aws-dev	BigQuery	35.96	\N
883	2026-02-25	azure-main	S3	34.11	\N
884	2026-02-25	azure-main	RDS	188.49	\N
885	2026-02-25	azure-main	SQL DB	93.89	\N
886	2026-02-25	gcp-analytics	RDS	23.81	\N
887	2026-02-25	gcp-analytics	SQL DB	57.44	\N
888	2026-02-25	gcp-analytics	EC2	117.13	\N
889	2026-02-26	aws-prod	Blob Storage	42.39	\N
890	2026-02-26	aws-prod	VM	105.13	\N
891	2026-02-26	aws-prod	EC2	23.49	\N
892	2026-02-26	aws-dev	VM	16.41	\N
893	2026-02-26	aws-dev	SQL DB	140.67	\N
894	2026-02-26	aws-dev	EC2	148.71	\N
895	2026-02-26	azure-main	S3	147.26	\N
896	2026-02-26	azure-main	Lambda	77.84	\N
897	2026-02-26	azure-main	Blob Storage	86.79	\N
898	2026-02-26	gcp-analytics	EC2	190.14	\N
899	2026-02-26	gcp-analytics	BigQuery	166.64	\N
900	2026-02-26	gcp-analytics	S3	94.05	\N
901	2026-02-27	aws-prod	BigQuery	152.43	\N
902	2026-02-27	aws-prod	RDS	73.42	\N
903	2026-02-27	aws-prod	EC2	11.22	\N
904	2026-02-27	aws-dev	SQL DB	109.56	\N
905	2026-02-27	aws-dev	RDS	158.1	\N
906	2026-02-27	aws-dev	VM	123.8	\N
907	2026-02-27	azure-main	EC2	184.13	\N
908	2026-02-27	azure-main	VM	198.27	\N
909	2026-02-27	azure-main	S3	172.7	\N
910	2026-02-27	gcp-analytics	Lambda	32.43	\N
911	2026-02-27	gcp-analytics	EC2	173.37	\N
912	2026-02-27	gcp-analytics	RDS	71.36	\N
913	2026-02-28	aws-prod	EC2	109.4	\N
914	2026-02-28	aws-prod	RDS	184.26	\N
915	2026-02-28	aws-prod	Lambda	101.53	\N
916	2026-02-28	aws-dev	RDS	41.77	\N
917	2026-02-28	aws-dev	SQL DB	79.89	\N
918	2026-02-28	aws-dev	BigQuery	86.23	\N
919	2026-02-28	azure-main	BigQuery	154.58	\N
920	2026-02-28	azure-main	Blob Storage	47.21	\N
921	2026-02-28	azure-main	RDS	122.84	\N
922	2026-02-28	gcp-analytics	SQL DB	194.32	\N
923	2026-02-28	gcp-analytics	VM	163.1	\N
924	2026-02-28	gcp-analytics	RDS	96.08	\N
925	2026-03-01	aws-prod	VM	50.7	\N
926	2026-03-01	aws-prod	EC2	41.88	\N
927	2026-03-01	aws-prod	S3	148	\N
928	2026-03-01	aws-dev	Blob Storage	56.28	\N
929	2026-03-01	aws-dev	RDS	50.94	\N
930	2026-03-01	aws-dev	S3	103.79	\N
931	2026-03-01	azure-main	RDS	140.3	\N
932	2026-03-01	azure-main	EC2	19.06	\N
933	2026-03-01	azure-main	Lambda	21.03	\N
934	2026-03-01	gcp-analytics	VM	80.73	\N
935	2026-03-01	gcp-analytics	Blob Storage	167.86	\N
936	2026-03-01	gcp-analytics	RDS	152.99	\N
937	2026-03-02	aws-prod	BigQuery	172.68	\N
938	2026-03-02	aws-prod	Lambda	38.21	\N
939	2026-03-02	aws-prod	SQL DB	52.82	\N
940	2026-03-02	aws-dev	RDS	127.74	\N
941	2026-03-02	aws-dev	Lambda	159.47	\N
942	2026-03-02	aws-dev	S3	143.49	\N
943	2026-03-02	azure-main	S3	113.16	\N
944	2026-03-02	azure-main	RDS	91.34	\N
945	2026-03-02	azure-main	SQL DB	115.17	\N
946	2026-03-02	gcp-analytics	VM	164.03	\N
947	2026-03-02	gcp-analytics	SQL DB	27.44	\N
948	2026-03-02	gcp-analytics	Lambda	146.84	\N
949	2026-03-03	aws-prod	Lambda	59.53	\N
950	2026-03-03	aws-prod	SQL DB	55.48	\N
951	2026-03-03	aws-prod	RDS	37.43	\N
952	2026-03-03	aws-dev	SQL DB	81.23	\N
953	2026-03-03	aws-dev	S3	43.72	\N
954	2026-03-03	aws-dev	EC2	39.06	\N
955	2026-03-03	azure-main	Lambda	115.47	\N
956	2026-03-03	azure-main	Blob Storage	134.09	\N
957	2026-03-03	azure-main	RDS	90.94	\N
958	2026-03-03	gcp-analytics	SQL DB	47.15	\N
959	2026-03-03	gcp-analytics	VM	140.38	\N
960	2026-03-03	gcp-analytics	S3	25.77	\N
961	2026-03-04	aws-prod	Lambda	153.3	\N
962	2026-03-04	aws-prod	EC2	28.03	\N
963	2026-03-04	aws-prod	BigQuery	131.44	\N
964	2026-03-04	aws-dev	RDS	15.84	\N
965	2026-03-04	aws-dev	Blob Storage	61.83	\N
966	2026-03-04	aws-dev	Lambda	25.66	\N
967	2026-03-04	azure-main	SQL DB	33.15	\N
968	2026-03-04	azure-main	Blob Storage	16.64	\N
969	2026-03-04	azure-main	VM	49.53	\N
970	2026-03-04	gcp-analytics	VM	128.35	\N
971	2026-03-04	gcp-analytics	BigQuery	104.25	\N
972	2026-03-04	gcp-analytics	SQL DB	124.32	\N
973	2026-03-05	aws-prod	EC2	41.26	\N
974	2026-03-05	aws-prod	RDS	189.35	\N
975	2026-03-05	aws-prod	VM	152.59	\N
977	2026-03-05	aws-dev	VM	104.55	\N
978	2026-03-05	aws-dev	Lambda	38.09	\N
979	2026-03-05	azure-main	EC2	182.67	\N
980	2026-03-05	azure-main	S3	63.21	\N
981	2026-03-05	azure-main	Lambda	32.3	\N
982	2026-03-05	gcp-analytics	SQL DB	22.53	\N
983	2026-03-05	gcp-analytics	S3	54.66	\N
984	2026-03-05	gcp-analytics	BigQuery	67.65	\N
985	2026-03-06	aws-prod	VM	116.58	\N
986	2026-03-06	aws-prod	RDS	14.59	\N
987	2026-03-06	aws-prod	BigQuery	129.1	\N
988	2026-03-06	aws-dev	BigQuery	186.28	\N
989	2026-03-06	aws-dev	Blob Storage	163.11	\N
990	2026-03-06	aws-dev	VM	170.18	\N
991	2026-03-06	azure-main	S3	191.56	\N
992	2026-03-06	azure-main	Blob Storage	40.88	\N
993	2026-03-06	azure-main	Lambda	70.39	\N
994	2026-03-06	gcp-analytics	RDS	61.66	\N
995	2026-03-06	gcp-analytics	Blob Storage	174.43	\N
996	2026-03-06	gcp-analytics	EC2	67.52	\N
997	2026-03-07	aws-prod	Lambda	178.73	\N
998	2026-03-07	aws-prod	RDS	166.52	\N
999	2026-03-07	aws-prod	VM	57.21	\N
1000	2026-03-07	aws-dev	SQL DB	85.48	\N
1001	2026-03-07	aws-dev	VM	29.88	\N
1002	2026-03-07	aws-dev	EC2	155.14	\N
1003	2026-03-07	azure-main	Blob Storage	131.8	\N
1004	2026-03-07	azure-main	EC2	60.72	\N
1005	2026-03-07	azure-main	SQL DB	194.29	\N
1006	2026-03-07	gcp-analytics	VM	57.29	\N
1007	2026-03-07	gcp-analytics	S3	93.33	\N
1008	2026-03-07	gcp-analytics	RDS	149.88	\N
1009	2026-03-08	aws-prod	Lambda	61.43	\N
1010	2026-03-08	aws-prod	RDS	91.41	\N
1011	2026-03-08	aws-prod	SQL DB	65.44	\N
1012	2026-03-08	aws-dev	Blob Storage	123.73	\N
1013	2026-03-08	aws-dev	RDS	197.05	\N
1014	2026-03-08	aws-dev	VM	92.17	\N
1015	2026-03-08	azure-main	RDS	71.38	\N
1016	2026-03-08	azure-main	VM	108.09	\N
1017	2026-03-08	azure-main	EC2	146.64	\N
1018	2026-03-08	gcp-analytics	RDS	121.8	\N
1019	2026-03-08	gcp-analytics	Blob Storage	151.44	\N
1020	2026-03-08	gcp-analytics	SQL DB	72.82	\N
1021	2026-03-09	aws-prod	RDS	57.87	\N
1022	2026-03-09	aws-prod	EC2	121.82	\N
1023	2026-03-09	aws-prod	Lambda	190.51	\N
1024	2026-03-09	aws-dev	Blob Storage	108.15	\N
1025	2026-03-09	aws-dev	EC2	172.66	\N
1026	2026-03-09	aws-dev	VM	56.7	\N
1027	2026-03-09	azure-main	RDS	100.59	\N
1028	2026-03-09	azure-main	SQL DB	91.07	\N
1029	2026-03-09	azure-main	Blob Storage	20.82	\N
1030	2026-03-09	gcp-analytics	BigQuery	61.15	\N
1031	2026-03-09	gcp-analytics	VM	23.52	\N
1032	2026-03-09	gcp-analytics	SQL DB	67.86	\N
1033	2026-03-10	aws-prod	EC2	63.35	\N
1034	2026-03-10	aws-prod	Blob Storage	95.47	\N
1035	2026-03-10	aws-prod	VM	130.41	\N
1036	2026-03-10	aws-dev	Lambda	43.96	\N
1037	2026-03-10	aws-dev	BigQuery	131.77	\N
1038	2026-03-10	aws-dev	VM	177.38	\N
1039	2026-03-10	azure-main	RDS	60.1	\N
1040	2026-03-10	azure-main	Blob Storage	158.83	\N
1041	2026-03-10	azure-main	S3	141.3	\N
1042	2026-03-10	gcp-analytics	BigQuery	40.95	\N
1043	2026-03-10	gcp-analytics	S3	170.26	\N
1044	2026-03-10	gcp-analytics	Blob Storage	122.66	\N
1045	2026-03-11	aws-prod	BigQuery	121.26	\N
1046	2026-03-11	aws-prod	S3	41.08	\N
1047	2026-03-11	aws-prod	Lambda	177.35	\N
1048	2026-03-11	aws-dev	SQL DB	49.06	\N
1049	2026-03-11	aws-dev	Lambda	48.74	\N
1050	2026-03-11	aws-dev	RDS	181.45	\N
1051	2026-03-11	azure-main	S3	62.14	\N
1052	2026-03-11	azure-main	RDS	13.43	\N
1053	2026-03-11	azure-main	Blob Storage	157.5	\N
1054	2026-03-11	gcp-analytics	SQL DB	115.51	\N
1055	2026-03-11	gcp-analytics	Lambda	115.63	\N
1056	2026-03-11	gcp-analytics	RDS	114.02	\N
1057	2026-03-12	aws-prod	VM	155.78	\N
1058	2026-03-12	aws-prod	RDS	171.14	\N
1059	2026-03-12	aws-prod	Blob Storage	128.95	\N
1060	2026-03-12	aws-dev	VM	119.13	\N
1061	2026-03-12	aws-dev	BigQuery	98.11	\N
1062	2026-03-12	aws-dev	SQL DB	25.48	\N
1063	2026-03-12	azure-main	VM	45.54	\N
1064	2026-03-12	azure-main	SQL DB	108.01	\N
1065	2026-03-12	azure-main	EC2	136.85	\N
1066	2026-03-12	gcp-analytics	EC2	171.06	\N
1067	2026-03-12	gcp-analytics	Lambda	12.04	\N
1068	2026-03-12	gcp-analytics	S3	90.57	\N
1069	2026-03-13	aws-prod	S3	139.32	\N
1070	2026-03-13	aws-prod	RDS	143.82	\N
1071	2026-03-13	aws-prod	Lambda	20.36	\N
1072	2026-03-13	aws-dev	BigQuery	19.89	\N
1073	2026-03-13	aws-dev	VM	12.05	\N
1074	2026-03-13	aws-dev	SQL DB	181.63	\N
1075	2026-03-13	azure-main	SQL DB	79.81	\N
1076	2026-03-13	azure-main	RDS	120.11	\N
1077	2026-03-13	azure-main	Blob Storage	25.85	\N
1078	2026-03-13	gcp-analytics	EC2	179.4	\N
1079	2026-03-13	gcp-analytics	Blob Storage	166.25	\N
1080	2026-03-13	gcp-analytics	VM	78.77	\N
19081	2026-01-16	aws-prod-finops	EC2	136.42	2026-03-16T15:54:55
19082	2026-01-16	aws-prod-finops	RDS	75.13	2026-03-16T15:54:55
19083	2026-01-16	aws-prod-finops	S3	30.21	2026-03-16T15:54:55
19084	2026-01-16	aws-prod-finops	Data Transfer	22.74	2026-03-16T15:54:55
19085	2026-01-17	aws-prod-finops	EC2	139.37	2026-03-16T15:54:55
19086	2026-01-17	aws-prod-finops	RDS	76.75	2026-03-16T15:54:55
19087	2026-01-17	aws-prod-finops	S3	30.86	2026-03-16T15:54:55
19088	2026-01-17	aws-prod-finops	Data Transfer	23.23	2026-03-16T15:54:55
19089	2026-01-18	aws-prod-finops	EC2	142.32	2026-03-16T15:54:55
19090	2026-01-18	aws-prod-finops	RDS	78.38	2026-03-16T15:54:55
19091	2026-01-18	aws-prod-finops	S3	31.51	2026-03-16T15:54:55
19092	2026-01-18	aws-prod-finops	Data Transfer	23.72	2026-03-16T15:54:55
19093	2026-01-19	aws-prod-finops	EC2	145.29	2026-03-16T15:54:55
19094	2026-01-19	aws-prod-finops	RDS	80.02	2026-03-16T15:54:55
19095	2026-01-19	aws-prod-finops	S3	32.17	2026-03-16T15:54:55
19096	2026-01-19	aws-prod-finops	Data Transfer	24.22	2026-03-16T15:54:55
19097	2026-01-20	aws-prod-finops	EC2	148.27	2026-03-16T15:54:55
19098	2026-01-20	aws-prod-finops	RDS	81.66	2026-03-16T15:54:55
19099	2026-01-20	aws-prod-finops	S3	32.83	2026-03-16T15:54:55
19100	2026-01-20	aws-prod-finops	Data Transfer	24.71	2026-03-16T15:54:55
19101	2026-01-21	aws-prod-finops	EC2	178.5	2026-03-16T15:54:55
19102	2026-01-21	aws-prod-finops	RDS	83.31	2026-03-16T15:54:55
19103	2026-01-21	aws-prod-finops	S3	33.49	2026-03-16T15:54:55
19104	2026-01-21	aws-prod-finops	Data Transfer	25.21	2026-03-16T15:54:55
19105	2026-01-22	aws-prod-finops	EC2	154.28	2026-03-16T15:54:55
19106	2026-01-22	aws-prod-finops	RDS	84.96	2026-03-16T15:54:55
19107	2026-01-22	aws-prod-finops	S3	34.16	2026-03-16T15:54:55
19108	2026-01-22	aws-prod-finops	Data Transfer	25.71	2026-03-16T15:54:55
19109	2026-01-23	aws-prod-finops	EC2	138.81	2026-03-16T15:54:55
19110	2026-01-23	aws-prod-finops	RDS	76.45	2026-03-16T15:54:55
19111	2026-01-23	aws-prod-finops	S3	30.73	2026-03-16T15:54:55
19112	2026-01-23	aws-prod-finops	Data Transfer	23.14	2026-03-16T15:54:55
19113	2026-01-24	aws-prod-finops	EC2	141.8	2026-03-16T15:54:55
19114	2026-01-24	aws-prod-finops	RDS	78.09	2026-03-16T15:54:55
19115	2026-01-24	aws-prod-finops	S3	31.4	2026-03-16T15:54:55
19116	2026-01-24	aws-prod-finops	Data Transfer	23.63	2026-03-16T15:54:55
19117	2026-01-25	aws-prod-finops	EC2	144.8	2026-03-16T15:54:55
19118	2026-01-25	aws-prod-finops	RDS	79.75	2026-03-16T15:54:55
19119	2026-01-25	aws-prod-finops	S3	32.06	2026-03-16T15:54:55
19120	2026-01-25	aws-prod-finops	Data Transfer	24.13	2026-03-16T15:54:55
19121	2026-01-26	aws-prod-finops	EC2	147.82	2026-03-16T15:54:55
19122	2026-01-26	aws-prod-finops	RDS	81.41	2026-03-16T15:54:55
19123	2026-01-26	aws-prod-finops	S3	32.73	2026-03-16T15:54:55
19124	2026-01-26	aws-prod-finops	Data Transfer	24.64	2026-03-16T15:54:55
19125	2026-01-27	aws-prod-finops	EC2	150.84	2026-03-16T15:54:55
19126	2026-01-27	aws-prod-finops	RDS	83.07	2026-03-16T15:54:55
19127	2026-01-27	aws-prod-finops	S3	33.4	2026-03-16T15:54:55
19128	2026-01-27	aws-prod-finops	Data Transfer	25.14	2026-03-16T15:54:55
19129	2026-01-28	aws-prod-finops	EC2	153.88	2026-03-16T15:54:55
19130	2026-01-28	aws-prod-finops	RDS	84.75	2026-03-16T15:54:55
19131	2026-01-28	aws-prod-finops	S3	34.07	2026-03-16T15:54:55
19132	2026-01-28	aws-prod-finops	Data Transfer	25.65	2026-03-16T15:54:55
19133	2026-01-29	aws-prod-finops	EC2	156.94	2026-03-16T15:54:55
19134	2026-01-29	aws-prod-finops	RDS	86.43	2026-03-16T15:54:55
19135	2026-01-29	aws-prod-finops	S3	34.75	2026-03-16T15:54:55
19136	2026-01-29	aws-prod-finops	Data Transfer	26.16	2026-03-16T15:54:55
19137	2026-01-30	aws-prod-finops	EC2	141.2	2026-03-16T15:54:55
19138	2026-01-30	aws-prod-finops	RDS	77.76	2026-03-16T15:54:55
19139	2026-01-30	aws-prod-finops	S3	31.26	2026-03-16T15:54:55
19140	2026-01-30	aws-prod-finops	Data Transfer	23.53	2026-03-16T15:54:55
19141	2026-01-31	aws-prod-finops	EC2	144.23	2026-03-16T15:54:55
19142	2026-01-31	aws-prod-finops	RDS	79.43	2026-03-16T15:54:55
19143	2026-01-31	aws-prod-finops	S3	31.93	2026-03-16T15:54:55
19144	2026-01-31	aws-prod-finops	Data Transfer	24.04	2026-03-16T15:54:55
19145	2026-02-01	aws-prod-finops	EC2	147.28	2026-03-16T15:54:55
19146	2026-02-01	aws-prod-finops	RDS	81.11	2026-03-16T15:54:55
19147	2026-02-01	aws-prod-finops	S3	32.61	2026-03-16T15:54:55
19148	2026-02-01	aws-prod-finops	Data Transfer	24.55	2026-03-16T15:54:55
19149	2026-02-02	aws-prod-finops	EC2	150.34	2026-03-16T15:54:55
19150	2026-02-02	aws-prod-finops	RDS	82.8	2026-03-16T15:54:55
19151	2026-02-02	aws-prod-finops	S3	33.29	2026-03-16T15:54:55
19152	2026-02-02	aws-prod-finops	Data Transfer	25.06	2026-03-16T15:54:55
19153	2026-02-03	aws-prod-finops	EC2	153.41	2026-03-16T15:54:55
19154	2026-02-03	aws-prod-finops	RDS	84.49	2026-03-16T15:54:55
19155	2026-02-03	aws-prod-finops	S3	33.97	2026-03-16T15:54:55
19156	2026-02-03	aws-prod-finops	Data Transfer	25.57	2026-03-16T15:54:55
19157	2026-02-04	aws-prod-finops	EC2	156.5	2026-03-16T15:54:55
19158	2026-02-04	aws-prod-finops	RDS	86.19	2026-03-16T15:54:55
19159	2026-02-04	aws-prod-finops	S3	34.65	2026-03-16T15:54:55
19160	2026-02-04	aws-prod-finops	Data Transfer	26.08	2026-03-16T15:54:55
19161	2026-02-05	aws-prod-finops	EC2	159.6	2026-03-16T15:54:55
19162	2026-02-05	aws-prod-finops	RDS	87.89	2026-03-16T15:54:55
19163	2026-02-05	aws-prod-finops	S3	35.34	2026-03-16T15:54:55
19164	2026-02-05	aws-prod-finops	Data Transfer	26.6	2026-03-16T15:54:55
19165	2026-02-06	aws-prod-finops	EC2	143.58	2026-03-16T15:54:55
19166	2026-02-06	aws-prod-finops	RDS	79.08	2026-03-16T15:54:55
19167	2026-02-06	aws-prod-finops	S3	31.79	2026-03-16T15:54:55
19168	2026-02-06	aws-prod-finops	Data Transfer	23.93	2026-03-16T15:54:55
19169	2026-02-07	aws-prod-finops	EC2	173.06	2026-03-16T15:54:55
19170	2026-02-07	aws-prod-finops	RDS	80.77	2026-03-16T15:54:55
19171	2026-02-07	aws-prod-finops	S3	32.47	2026-03-16T15:54:55
19172	2026-02-07	aws-prod-finops	Data Transfer	24.44	2026-03-16T15:54:55
19173	2026-02-08	aws-prod-finops	EC2	149.76	2026-03-16T15:54:55
19174	2026-02-08	aws-prod-finops	RDS	82.47	2026-03-16T15:54:55
19175	2026-02-08	aws-prod-finops	S3	33.16	2026-03-16T15:54:55
19176	2026-02-08	aws-prod-finops	Data Transfer	24.96	2026-03-16T15:54:55
19177	2026-02-09	aws-prod-finops	EC2	152.86	2026-03-16T15:54:55
19178	2026-02-09	aws-prod-finops	RDS	84.19	2026-03-16T15:54:55
19179	2026-02-09	aws-prod-finops	S3	33.85	2026-03-16T15:54:55
19180	2026-02-09	aws-prod-finops	Data Transfer	25.48	2026-03-16T15:54:55
19181	2026-02-10	aws-prod-finops	EC2	155.98	2026-03-16T15:54:55
19182	2026-02-10	aws-prod-finops	RDS	85.9	2026-03-16T15:54:55
19183	2026-02-10	aws-prod-finops	S3	34.54	2026-03-16T15:54:55
19184	2026-02-10	aws-prod-finops	Data Transfer	26	2026-03-16T15:54:55
19185	2026-02-11	aws-prod-finops	EC2	159.11	2026-03-16T15:54:55
19186	2026-02-11	aws-prod-finops	RDS	87.63	2026-03-16T15:54:55
19187	2026-02-11	aws-prod-finops	S3	35.23	2026-03-16T15:54:55
19188	2026-02-11	aws-prod-finops	Data Transfer	26.52	2026-03-16T15:54:55
19189	2026-02-12	aws-prod-finops	EC2	162.26	2026-03-16T15:54:55
19190	2026-02-12	aws-prod-finops	RDS	89.36	2026-03-16T15:54:55
19191	2026-02-12	aws-prod-finops	S3	35.93	2026-03-16T15:54:55
19192	2026-02-12	aws-prod-finops	Data Transfer	27.04	2026-03-16T15:54:55
19193	2026-02-13	aws-prod-finops	EC2	145.97	2026-03-16T15:54:55
19194	2026-02-13	aws-prod-finops	RDS	80.39	2026-03-16T15:54:55
19195	2026-02-13	aws-prod-finops	S3	32.32	2026-03-16T15:54:55
19196	2026-02-13	aws-prod-finops	Data Transfer	24.33	2026-03-16T15:54:55
19197	2026-02-14	aws-prod-finops	EC2	149.1	2026-03-16T15:54:55
19198	2026-02-14	aws-prod-finops	RDS	82.11	2026-03-16T15:54:55
19199	2026-02-14	aws-prod-finops	S3	33.01	2026-03-16T15:54:55
19200	2026-02-14	aws-prod-finops	Data Transfer	24.85	2026-03-16T15:54:55
19201	2026-02-15	aws-prod-finops	EC2	152.24	2026-03-16T15:54:55
19202	2026-02-15	aws-prod-finops	RDS	83.84	2026-03-16T15:54:55
19203	2026-02-15	aws-prod-finops	S3	33.71	2026-03-16T15:54:55
19204	2026-02-15	aws-prod-finops	Data Transfer	25.37	2026-03-16T15:54:55
19205	2026-02-16	aws-prod-finops	EC2	155.39	2026-03-16T15:54:55
19206	2026-02-16	aws-prod-finops	RDS	85.58	2026-03-16T15:54:55
19207	2026-02-16	aws-prod-finops	S3	34.4	2026-03-16T15:54:55
19208	2026-02-16	aws-prod-finops	Data Transfer	25.9	2026-03-16T15:54:55
19209	2026-02-17	aws-prod-finops	EC2	158.55	2026-03-16T15:54:55
19210	2026-02-17	aws-prod-finops	RDS	87.32	2026-03-16T15:54:55
19211	2026-02-17	aws-prod-finops	S3	35.11	2026-03-16T15:54:55
19212	2026-02-17	aws-prod-finops	Data Transfer	26.43	2026-03-16T15:54:55
19213	2026-02-18	aws-prod-finops	EC2	161.73	2026-03-16T15:54:55
19214	2026-02-18	aws-prod-finops	RDS	89.07	2026-03-16T15:54:55
19215	2026-02-18	aws-prod-finops	S3	35.81	2026-03-16T15:54:55
19216	2026-02-18	aws-prod-finops	Data Transfer	26.95	2026-03-16T15:54:55
19217	2026-02-19	aws-prod-finops	EC2	164.92	2026-03-16T15:54:55
19218	2026-02-19	aws-prod-finops	RDS	90.82	2026-03-16T15:54:55
19219	2026-02-19	aws-prod-finops	S3	36.51	2026-03-16T15:54:55
19220	2026-02-19	aws-prod-finops	Data Transfer	27.49	2026-03-16T15:54:55
19221	2026-02-20	aws-prod-finops	EC2	148.36	2026-03-16T15:54:55
19222	2026-02-20	aws-prod-finops	RDS	81.71	2026-03-16T15:54:55
19223	2026-02-20	aws-prod-finops	S3	32.85	2026-03-16T15:54:55
19224	2026-02-20	aws-prod-finops	Data Transfer	24.73	2026-03-16T15:54:55
19225	2026-02-21	aws-prod-finops	EC2	178.81	2026-03-16T15:54:55
19226	2026-02-21	aws-prod-finops	RDS	83.45	2026-03-16T15:54:55
19227	2026-02-21	aws-prod-finops	S3	33.55	2026-03-16T15:54:55
19228	2026-02-21	aws-prod-finops	Data Transfer	25.26	2026-03-16T15:54:55
19229	2026-02-22	aws-prod-finops	EC2	154.71	2026-03-16T15:54:55
19230	2026-02-22	aws-prod-finops	RDS	85.2	2026-03-16T15:54:55
19231	2026-02-22	aws-prod-finops	S3	34.26	2026-03-16T15:54:55
19232	2026-02-22	aws-prod-finops	Data Transfer	25.79	2026-03-16T15:54:55
19233	2026-02-23	aws-prod-finops	EC2	157.91	2026-03-16T15:54:55
19234	2026-02-23	aws-prod-finops	RDS	86.96	2026-03-16T15:54:55
19235	2026-02-23	aws-prod-finops	S3	34.96	2026-03-16T15:54:55
19236	2026-02-23	aws-prod-finops	Data Transfer	26.32	2026-03-16T15:54:55
19237	2026-02-24	aws-prod-finops	EC2	161.12	2026-03-16T15:54:55
19238	2026-02-24	aws-prod-finops	RDS	88.73	2026-03-16T15:54:55
19239	2026-02-24	aws-prod-finops	S3	35.67	2026-03-16T15:54:55
19240	2026-02-24	aws-prod-finops	Data Transfer	26.85	2026-03-16T15:54:55
19241	2026-02-25	aws-prod-finops	EC2	164.34	2026-03-16T15:54:55
19242	2026-02-25	aws-prod-finops	RDS	90.51	2026-03-16T15:54:55
19243	2026-02-25	aws-prod-finops	S3	36.39	2026-03-16T15:54:55
19244	2026-02-25	aws-prod-finops	Data Transfer	27.39	2026-03-16T15:54:55
19245	2026-02-26	aws-prod-finops	EC2	167.58	2026-03-16T15:54:55
19246	2026-02-26	aws-prod-finops	RDS	92.29	2026-03-16T15:54:55
19247	2026-02-26	aws-prod-finops	S3	37.1	2026-03-16T15:54:55
19248	2026-02-26	aws-prod-finops	Data Transfer	27.93	2026-03-16T15:54:55
19249	2026-02-27	aws-prod-finops	EC2	150.75	2026-03-16T15:54:55
19250	2026-02-27	aws-prod-finops	RDS	83.02	2026-03-16T15:54:55
19251	2026-02-27	aws-prod-finops	S3	33.38	2026-03-16T15:54:55
19252	2026-02-27	aws-prod-finops	Data Transfer	25.12	2026-03-16T15:54:55
19253	2026-02-28	aws-prod-finops	EC2	153.96	2026-03-16T15:54:55
19254	2026-02-28	aws-prod-finops	RDS	84.79	2026-03-16T15:54:55
19255	2026-02-28	aws-prod-finops	S3	34.09	2026-03-16T15:54:55
19256	2026-02-28	aws-prod-finops	Data Transfer	25.66	2026-03-16T15:54:55
19257	2026-03-01	aws-prod-finops	EC2	157.19	2026-03-16T15:54:55
19258	2026-03-01	aws-prod-finops	RDS	86.57	2026-03-16T15:54:55
19259	2026-03-01	aws-prod-finops	S3	34.8	2026-03-16T15:54:55
19260	2026-03-01	aws-prod-finops	Data Transfer	26.2	2026-03-16T15:54:55
19261	2026-03-02	aws-prod-finops	EC2	160.43	2026-03-16T15:54:55
19262	2026-03-02	aws-prod-finops	RDS	88.35	2026-03-16T15:54:55
19263	2026-03-02	aws-prod-finops	S3	35.52	2026-03-16T15:54:55
19264	2026-03-02	aws-prod-finops	Data Transfer	26.74	2026-03-16T15:54:55
19265	2026-03-03	aws-prod-finops	EC2	163.69	2026-03-16T15:54:55
19266	2026-03-03	aws-prod-finops	RDS	90.15	2026-03-16T15:54:55
19267	2026-03-03	aws-prod-finops	S3	36.24	2026-03-16T15:54:55
19268	2026-03-03	aws-prod-finops	Data Transfer	27.28	2026-03-16T15:54:55
19269	2026-03-04	aws-prod-finops	EC2	166.96	2026-03-16T15:54:55
19270	2026-03-04	aws-prod-finops	RDS	91.95	2026-03-16T15:54:55
19271	2026-03-04	aws-prod-finops	S3	36.97	2026-03-16T15:54:55
19272	2026-03-04	aws-prod-finops	Data Transfer	27.83	2026-03-16T15:54:55
19273	2026-03-05	aws-prod-finops	EC2	170.24	2026-03-16T15:54:55
19274	2026-03-05	aws-prod-finops	RDS	93.75	2026-03-16T15:54:55
19275	2026-03-05	aws-prod-finops	S3	37.69	2026-03-16T15:54:55
19276	2026-03-05	aws-prod-finops	Data Transfer	28.37	2026-03-16T15:54:55
19277	2026-03-06	aws-prod-finops	EC2	153.13	2026-03-16T15:54:55
19278	2026-03-06	aws-prod-finops	RDS	84.33	2026-03-16T15:54:55
19279	2026-03-06	aws-prod-finops	S3	33.91	2026-03-16T15:54:55
19280	2026-03-06	aws-prod-finops	Data Transfer	25.52	2026-03-16T15:54:55
19281	2026-03-07	aws-prod-finops	EC2	310.04	2026-03-16T15:54:55
19282	2026-03-07	aws-prod-finops	RDS	86.13	2026-03-16T15:54:55
19283	2026-03-07	aws-prod-finops	S3	34.63	2026-03-16T15:54:55
19284	2026-03-07	aws-prod-finops	Data Transfer	43.79	2026-03-16T15:54:55
19285	2026-03-08	aws-prod-finops	EC2	268.25	2026-03-16T15:54:55
19286	2026-03-08	aws-prod-finops	RDS	87.93	2026-03-16T15:54:55
19287	2026-03-08	aws-prod-finops	S3	35.35	2026-03-16T15:54:55
19288	2026-03-08	aws-prod-finops	Data Transfer	44.71	2026-03-16T15:54:55
19289	2026-03-09	aws-prod-finops	EC2	273.77	2026-03-16T15:54:55
19290	2026-03-09	aws-prod-finops	RDS	89.74	2026-03-16T15:54:55
19291	2026-03-09	aws-prod-finops	S3	36.08	2026-03-16T15:54:55
19292	2026-03-09	aws-prod-finops	Data Transfer	45.63	2026-03-16T15:54:55
19293	2026-03-10	aws-prod-finops	EC2	279.31	2026-03-16T15:54:55
19294	2026-03-10	aws-prod-finops	RDS	91.56	2026-03-16T15:54:55
19295	2026-03-10	aws-prod-finops	S3	36.81	2026-03-16T15:54:55
19296	2026-03-10	aws-prod-finops	Data Transfer	46.55	2026-03-16T15:54:55
19297	2026-03-11	aws-prod-finops	EC2	284.88	2026-03-16T15:54:55
19298	2026-03-11	aws-prod-finops	RDS	93.39	2026-03-16T15:54:55
19299	2026-03-11	aws-prod-finops	S3	37.55	2026-03-16T15:54:55
19300	2026-03-11	aws-prod-finops	Data Transfer	47.48	2026-03-16T15:54:55
19301	2026-03-12	aws-prod-finops	EC2	290.47	2026-03-16T15:54:55
19302	2026-03-12	aws-prod-finops	RDS	95.22	2026-03-16T15:54:55
19303	2026-03-12	aws-prod-finops	S3	38.28	2026-03-16T15:54:55
19304	2026-03-12	aws-prod-finops	Data Transfer	48.41	2026-03-16T15:54:55
19305	2026-03-13	aws-prod-finops	EC2	261.28	2026-03-16T15:54:55
19306	2026-03-13	aws-prod-finops	RDS	85.65	2026-03-16T15:54:55
19307	2026-03-13	aws-prod-finops	S3	34.43	2026-03-16T15:54:55
19308	2026-03-13	aws-prod-finops	Data Transfer	43.55	2026-03-16T15:54:55
19309	2026-03-14	aws-prod-finops	EC2	266.83	2026-03-16T15:54:55
19310	2026-03-14	aws-prod-finops	RDS	87.47	2026-03-16T15:54:55
19311	2026-03-14	aws-prod-finops	S3	35.17	2026-03-16T15:54:55
19312	2026-03-14	aws-prod-finops	Data Transfer	44.47	2026-03-16T15:54:55
19313	2026-03-15	aws-prod-finops	EC2	272.41	2026-03-16T15:54:55
19314	2026-03-15	aws-prod-finops	RDS	89.3	2026-03-16T15:54:55
19315	2026-03-15	aws-prod-finops	S3	35.9	2026-03-16T15:54:55
19316	2026-03-15	aws-prod-finops	Data Transfer	45.4	2026-03-16T15:54:55
19317	2026-03-16	aws-prod-finops	EC2	278.01	2026-03-16T15:54:55
19318	2026-03-16	aws-prod-finops	RDS	91.13	2026-03-16T15:54:55
19319	2026-03-16	aws-prod-finops	S3	36.64	2026-03-16T15:54:55
19320	2026-03-16	aws-prod-finops	Data Transfer	46.33	2026-03-16T15:54:55
19321	2026-01-16	azure-finance-subscription	Virtual Machines	119.06	2026-03-16T15:54:55
19322	2026-01-16	azure-finance-subscription	Storage	34.1	2026-03-16T15:54:55
19323	2026-01-16	azure-finance-subscription	SQL Database	69.18	2026-03-16T15:54:55
19324	2026-01-16	azure-finance-subscription	Bandwidth	18.05	2026-03-16T15:54:55
19325	2026-01-17	azure-finance-subscription	Virtual Machines	121.63	2026-03-16T15:54:55
19326	2026-01-17	azure-finance-subscription	Storage	34.84	2026-03-16T15:54:55
19327	2026-01-17	azure-finance-subscription	SQL Database	70.67	2026-03-16T15:54:55
19328	2026-01-17	azure-finance-subscription	Bandwidth	18.44	2026-03-16T15:54:55
19329	2026-01-18	azure-finance-subscription	Virtual Machines	124.21	2026-03-16T15:54:55
19330	2026-01-18	azure-finance-subscription	Storage	35.58	2026-03-16T15:54:55
19331	2026-01-18	azure-finance-subscription	SQL Database	72.17	2026-03-16T15:54:55
19332	2026-01-18	azure-finance-subscription	Bandwidth	18.83	2026-03-16T15:54:55
19333	2026-01-19	azure-finance-subscription	Virtual Machines	126.8	2026-03-16T15:54:55
19334	2026-01-19	azure-finance-subscription	Storage	36.32	2026-03-16T15:54:55
19335	2026-01-19	azure-finance-subscription	SQL Database	73.68	2026-03-16T15:54:55
19336	2026-01-19	azure-finance-subscription	Bandwidth	19.22	2026-03-16T15:54:55
19337	2026-01-20	azure-finance-subscription	Virtual Machines	129.41	2026-03-16T15:54:55
19338	2026-01-20	azure-finance-subscription	Storage	37.07	2026-03-16T15:54:55
19339	2026-01-20	azure-finance-subscription	SQL Database	75.19	2026-03-16T15:54:55
19340	2026-01-20	azure-finance-subscription	Bandwidth	19.62	2026-03-16T15:54:55
19341	2026-01-21	azure-finance-subscription	Virtual Machines	151.82	2026-03-16T15:54:55
19342	2026-01-21	azure-finance-subscription	Storage	37.81	2026-03-16T15:54:55
19343	2026-01-21	azure-finance-subscription	SQL Database	76.71	2026-03-16T15:54:55
19344	2026-01-21	azure-finance-subscription	Bandwidth	20.01	2026-03-16T15:54:55
19345	2026-01-22	azure-finance-subscription	Virtual Machines	134.65	2026-03-16T15:54:55
19346	2026-01-22	azure-finance-subscription	Storage	38.57	2026-03-16T15:54:55
19347	2026-01-22	azure-finance-subscription	SQL Database	78.24	2026-03-16T15:54:55
19348	2026-01-22	azure-finance-subscription	Bandwidth	20.41	2026-03-16T15:54:55
19349	2026-01-23	azure-finance-subscription	Virtual Machines	121.15	2026-03-16T15:54:55
19350	2026-01-23	azure-finance-subscription	Storage	34.7	2026-03-16T15:54:55
19351	2026-01-23	azure-finance-subscription	SQL Database	70.39	2026-03-16T15:54:55
19352	2026-01-23	azure-finance-subscription	Bandwidth	18.37	2026-03-16T15:54:55
19353	2026-01-24	azure-finance-subscription	Virtual Machines	123.76	2026-03-16T15:54:55
19354	2026-01-24	azure-finance-subscription	Storage	35.45	2026-03-16T15:54:55
19355	2026-01-24	azure-finance-subscription	SQL Database	71.91	2026-03-16T15:54:55
19356	2026-01-24	azure-finance-subscription	Bandwidth	18.76	2026-03-16T15:54:55
19357	2026-01-25	azure-finance-subscription	Virtual Machines	126.38	2026-03-16T15:54:55
19358	2026-01-25	azure-finance-subscription	Storage	36.2	2026-03-16T15:54:55
19359	2026-01-25	azure-finance-subscription	SQL Database	73.43	2026-03-16T15:54:55
19360	2026-01-25	azure-finance-subscription	Bandwidth	19.16	2026-03-16T15:54:55
19361	2026-01-26	azure-finance-subscription	Virtual Machines	129.01	2026-03-16T15:54:55
19362	2026-01-26	azure-finance-subscription	Storage	36.95	2026-03-16T15:54:55
19363	2026-01-26	azure-finance-subscription	SQL Database	74.96	2026-03-16T15:54:55
19364	2026-01-26	azure-finance-subscription	Bandwidth	19.56	2026-03-16T15:54:55
19365	2026-01-27	azure-finance-subscription	Virtual Machines	131.65	2026-03-16T15:54:55
19366	2026-01-27	azure-finance-subscription	Storage	37.71	2026-03-16T15:54:55
19367	2026-01-27	azure-finance-subscription	SQL Database	76.49	2026-03-16T15:54:55
19368	2026-01-27	azure-finance-subscription	Bandwidth	19.96	2026-03-16T15:54:55
19369	2026-01-28	azure-finance-subscription	Virtual Machines	134.3	2026-03-16T15:54:55
19370	2026-01-28	azure-finance-subscription	Storage	38.47	2026-03-16T15:54:55
19371	2026-01-28	azure-finance-subscription	SQL Database	78.04	2026-03-16T15:54:55
19372	2026-01-28	azure-finance-subscription	Bandwidth	20.36	2026-03-16T15:54:55
19373	2026-01-29	azure-finance-subscription	Virtual Machines	136.97	2026-03-16T15:54:55
19374	2026-01-29	azure-finance-subscription	Storage	39.23	2026-03-16T15:54:55
19375	2026-01-29	azure-finance-subscription	SQL Database	79.58	2026-03-16T15:54:55
19376	2026-01-29	azure-finance-subscription	Bandwidth	20.76	2026-03-16T15:54:55
19377	2026-01-30	azure-finance-subscription	Virtual Machines	123.23	2026-03-16T15:54:55
19378	2026-01-30	azure-finance-subscription	Storage	35.3	2026-03-16T15:54:55
19379	2026-01-30	azure-finance-subscription	SQL Database	71.6	2026-03-16T15:54:55
19380	2026-01-30	azure-finance-subscription	Bandwidth	18.68	2026-03-16T15:54:55
19381	2026-01-31	azure-finance-subscription	Virtual Machines	125.88	2026-03-16T15:54:55
19382	2026-01-31	azure-finance-subscription	Storage	36.06	2026-03-16T15:54:55
19383	2026-01-31	azure-finance-subscription	SQL Database	73.14	2026-03-16T15:54:55
19384	2026-01-31	azure-finance-subscription	Bandwidth	19.08	2026-03-16T15:54:55
19385	2026-02-01	azure-finance-subscription	Virtual Machines	128.54	2026-03-16T15:54:55
19386	2026-02-01	azure-finance-subscription	Storage	36.82	2026-03-16T15:54:55
19387	2026-02-01	azure-finance-subscription	SQL Database	74.69	2026-03-16T15:54:55
19388	2026-02-01	azure-finance-subscription	Bandwidth	19.49	2026-03-16T15:54:55
19389	2026-02-02	azure-finance-subscription	Virtual Machines	131.21	2026-03-16T15:54:55
19390	2026-02-02	azure-finance-subscription	Storage	37.58	2026-03-16T15:54:55
19391	2026-02-02	azure-finance-subscription	SQL Database	76.24	2026-03-16T15:54:55
19392	2026-02-02	azure-finance-subscription	Bandwidth	19.89	2026-03-16T15:54:55
19393	2026-02-03	azure-finance-subscription	Virtual Machines	133.89	2026-03-16T15:54:55
19394	2026-02-03	azure-finance-subscription	Storage	38.35	2026-03-16T15:54:55
19395	2026-02-03	azure-finance-subscription	SQL Database	77.8	2026-03-16T15:54:55
19396	2026-02-03	azure-finance-subscription	Bandwidth	20.3	2026-03-16T15:54:55
19397	2026-02-04	azure-finance-subscription	Virtual Machines	136.58	2026-03-16T15:54:55
19398	2026-02-04	azure-finance-subscription	Storage	39.12	2026-03-16T15:54:55
19399	2026-02-04	azure-finance-subscription	SQL Database	79.36	2026-03-16T15:54:55
19400	2026-02-04	azure-finance-subscription	Bandwidth	20.71	2026-03-16T15:54:55
19401	2026-02-05	azure-finance-subscription	Virtual Machines	139.29	2026-03-16T15:54:55
19402	2026-02-05	azure-finance-subscription	Storage	39.9	2026-03-16T15:54:55
19403	2026-02-05	azure-finance-subscription	SQL Database	80.93	2026-03-16T15:54:55
19404	2026-02-05	azure-finance-subscription	Bandwidth	21.12	2026-03-16T15:54:55
19405	2026-02-06	azure-finance-subscription	Virtual Machines	125.31	2026-03-16T15:54:55
19406	2026-02-06	azure-finance-subscription	Storage	35.89	2026-03-16T15:54:55
19407	2026-02-06	azure-finance-subscription	SQL Database	72.81	2026-03-16T15:54:55
19408	2026-02-06	azure-finance-subscription	Bandwidth	19	2026-03-16T15:54:55
19409	2026-02-07	azure-finance-subscription	Virtual Machines	147.2	2026-03-16T15:54:55
19410	2026-02-07	azure-finance-subscription	Storage	36.66	2026-03-16T15:54:55
19411	2026-02-07	azure-finance-subscription	SQL Database	74.37	2026-03-16T15:54:55
19412	2026-02-07	azure-finance-subscription	Bandwidth	19.4	2026-03-16T15:54:55
19413	2026-02-08	azure-finance-subscription	Virtual Machines	130.7	2026-03-16T15:54:55
19414	2026-02-08	azure-finance-subscription	Storage	37.44	2026-03-16T15:54:55
19415	2026-02-08	azure-finance-subscription	SQL Database	75.94	2026-03-16T15:54:55
19416	2026-02-08	azure-finance-subscription	Bandwidth	19.81	2026-03-16T15:54:55
19417	2026-02-09	azure-finance-subscription	Virtual Machines	133.41	2026-03-16T15:54:55
19418	2026-02-09	azure-finance-subscription	Storage	38.21	2026-03-16T15:54:55
19419	2026-02-09	azure-finance-subscription	SQL Database	77.52	2026-03-16T15:54:55
19420	2026-02-09	azure-finance-subscription	Bandwidth	20.22	2026-03-16T15:54:55
19421	2026-02-10	azure-finance-subscription	Virtual Machines	136.13	2026-03-16T15:54:55
19422	2026-02-10	azure-finance-subscription	Storage	38.99	2026-03-16T15:54:55
19423	2026-02-10	azure-finance-subscription	SQL Database	79.1	2026-03-16T15:54:55
19424	2026-02-10	azure-finance-subscription	Bandwidth	20.64	2026-03-16T15:54:55
19425	2026-02-11	azure-finance-subscription	Virtual Machines	138.87	2026-03-16T15:54:55
19426	2026-02-11	azure-finance-subscription	Storage	39.78	2026-03-16T15:54:55
19427	2026-02-11	azure-finance-subscription	SQL Database	80.69	2026-03-16T15:54:55
19428	2026-02-11	azure-finance-subscription	Bandwidth	21.05	2026-03-16T15:54:55
19429	2026-02-12	azure-finance-subscription	Virtual Machines	141.61	2026-03-16T15:54:55
19430	2026-02-12	azure-finance-subscription	Storage	40.56	2026-03-16T15:54:55
19431	2026-02-12	azure-finance-subscription	SQL Database	82.28	2026-03-16T15:54:55
19432	2026-02-12	azure-finance-subscription	Bandwidth	21.47	2026-03-16T15:54:55
19433	2026-02-13	azure-finance-subscription	Virtual Machines	127.4	2026-03-16T15:54:55
19434	2026-02-13	azure-finance-subscription	Storage	36.49	2026-03-16T15:54:55
19435	2026-02-13	azure-finance-subscription	SQL Database	74.02	2026-03-16T15:54:55
19436	2026-02-13	azure-finance-subscription	Bandwidth	19.31	2026-03-16T15:54:55
19437	2026-02-14	azure-finance-subscription	Virtual Machines	130.13	2026-03-16T15:54:55
19438	2026-02-14	azure-finance-subscription	Storage	37.27	2026-03-16T15:54:55
19439	2026-02-14	azure-finance-subscription	SQL Database	75.61	2026-03-16T15:54:55
19440	2026-02-14	azure-finance-subscription	Bandwidth	19.73	2026-03-16T15:54:55
19441	2026-02-15	azure-finance-subscription	Virtual Machines	132.86	2026-03-16T15:54:55
19442	2026-02-15	azure-finance-subscription	Storage	38.06	2026-03-16T15:54:55
19443	2026-02-15	azure-finance-subscription	SQL Database	77.2	2026-03-16T15:54:55
19444	2026-02-15	azure-finance-subscription	Bandwidth	20.14	2026-03-16T15:54:55
19445	2026-02-16	azure-finance-subscription	Virtual Machines	135.61	2026-03-16T15:54:55
19446	2026-02-16	azure-finance-subscription	Storage	38.84	2026-03-16T15:54:55
19447	2026-02-16	azure-finance-subscription	SQL Database	78.8	2026-03-16T15:54:55
19448	2026-02-16	azure-finance-subscription	Bandwidth	20.56	2026-03-16T15:54:55
19449	2026-02-17	azure-finance-subscription	Virtual Machines	138.38	2026-03-16T15:54:55
19450	2026-02-17	azure-finance-subscription	Storage	39.63	2026-03-16T15:54:55
19451	2026-02-17	azure-finance-subscription	SQL Database	80.4	2026-03-16T15:54:55
19452	2026-02-17	azure-finance-subscription	Bandwidth	20.98	2026-03-16T15:54:55
19453	2026-02-18	azure-finance-subscription	Virtual Machines	141.15	2026-03-16T15:54:55
19454	2026-02-18	azure-finance-subscription	Storage	40.43	2026-03-16T15:54:55
19455	2026-02-18	azure-finance-subscription	SQL Database	82.01	2026-03-16T15:54:55
19456	2026-02-18	azure-finance-subscription	Bandwidth	21.4	2026-03-16T15:54:55
19457	2026-02-19	azure-finance-subscription	Virtual Machines	143.93	2026-03-16T15:54:55
19458	2026-02-19	azure-finance-subscription	Storage	41.23	2026-03-16T15:54:55
19459	2026-02-19	azure-finance-subscription	SQL Database	83.63	2026-03-16T15:54:55
19460	2026-02-19	azure-finance-subscription	Bandwidth	21.82	2026-03-16T15:54:55
19461	2026-02-20	azure-finance-subscription	Virtual Machines	129.48	2026-03-16T15:54:55
19462	2026-02-20	azure-finance-subscription	Storage	37.09	2026-03-16T15:54:55
19463	2026-02-20	azure-finance-subscription	SQL Database	75.23	2026-03-16T15:54:55
19464	2026-02-20	azure-finance-subscription	Bandwidth	19.63	2026-03-16T15:54:55
19465	2026-02-21	azure-finance-subscription	Virtual Machines	152.09	2026-03-16T15:54:55
19466	2026-02-21	azure-finance-subscription	Storage	37.88	2026-03-16T15:54:55
19467	2026-02-21	azure-finance-subscription	SQL Database	76.84	2026-03-16T15:54:55
19468	2026-02-21	azure-finance-subscription	Bandwidth	20.05	2026-03-16T15:54:55
19469	2026-02-22	azure-finance-subscription	Virtual Machines	135.03	2026-03-16T15:54:55
19470	2026-02-22	azure-finance-subscription	Storage	38.68	2026-03-16T15:54:55
19471	2026-02-22	azure-finance-subscription	SQL Database	78.46	2026-03-16T15:54:55
19472	2026-02-22	azure-finance-subscription	Bandwidth	20.47	2026-03-16T15:54:55
19473	2026-02-23	azure-finance-subscription	Virtual Machines	137.82	2026-03-16T15:54:55
19474	2026-02-23	azure-finance-subscription	Storage	39.47	2026-03-16T15:54:55
19475	2026-02-23	azure-finance-subscription	SQL Database	80.08	2026-03-16T15:54:55
19476	2026-02-23	azure-finance-subscription	Bandwidth	20.89	2026-03-16T15:54:55
19477	2026-02-24	azure-finance-subscription	Virtual Machines	140.62	2026-03-16T15:54:55
19478	2026-02-24	azure-finance-subscription	Storage	40.28	2026-03-16T15:54:55
19479	2026-02-24	azure-finance-subscription	SQL Database	81.7	2026-03-16T15:54:55
19480	2026-02-24	azure-finance-subscription	Bandwidth	21.32	2026-03-16T15:54:55
19481	2026-02-25	azure-finance-subscription	Virtual Machines	143.43	2026-03-16T15:54:55
19482	2026-02-25	azure-finance-subscription	Storage	41.08	2026-03-16T15:54:55
19483	2026-02-25	azure-finance-subscription	SQL Database	83.34	2026-03-16T15:54:55
19484	2026-02-25	azure-finance-subscription	Bandwidth	21.74	2026-03-16T15:54:55
19485	2026-02-26	azure-finance-subscription	Virtual Machines	146.25	2026-03-16T15:54:55
19486	2026-02-26	azure-finance-subscription	Storage	41.89	2026-03-16T15:54:55
19487	2026-02-26	azure-finance-subscription	SQL Database	84.98	2026-03-16T15:54:55
19488	2026-02-26	azure-finance-subscription	Bandwidth	22.17	2026-03-16T15:54:55
19489	2026-02-27	azure-finance-subscription	Virtual Machines	131.57	2026-03-16T15:54:55
19490	2026-02-27	azure-finance-subscription	Storage	37.68	2026-03-16T15:54:55
19491	2026-02-27	azure-finance-subscription	SQL Database	76.44	2026-03-16T15:54:55
19492	2026-02-27	azure-finance-subscription	Bandwidth	19.94	2026-03-16T15:54:55
19493	2026-02-28	azure-finance-subscription	Virtual Machines	134.37	2026-03-16T15:54:55
19494	2026-02-28	azure-finance-subscription	Storage	38.49	2026-03-16T15:54:55
19495	2026-02-28	azure-finance-subscription	SQL Database	78.08	2026-03-16T15:54:55
19496	2026-02-28	azure-finance-subscription	Bandwidth	20.37	2026-03-16T15:54:55
19497	2026-03-01	azure-finance-subscription	Virtual Machines	137.19	2026-03-16T15:54:55
19498	2026-03-01	azure-finance-subscription	Storage	39.3	2026-03-16T15:54:55
19499	2026-03-01	azure-finance-subscription	SQL Database	79.71	2026-03-16T15:54:55
19500	2026-03-01	azure-finance-subscription	Bandwidth	20.8	2026-03-16T15:54:55
19501	2026-03-02	azure-finance-subscription	Virtual Machines	140.02	2026-03-16T15:54:55
19502	2026-03-02	azure-finance-subscription	Storage	40.11	2026-03-16T15:54:55
19503	2026-03-02	azure-finance-subscription	SQL Database	81.36	2026-03-16T15:54:55
19504	2026-03-02	azure-finance-subscription	Bandwidth	21.23	2026-03-16T15:54:55
19505	2026-03-03	azure-finance-subscription	Virtual Machines	142.86	2026-03-16T15:54:55
19506	2026-03-03	azure-finance-subscription	Storage	40.92	2026-03-16T15:54:55
19507	2026-03-03	azure-finance-subscription	SQL Database	83.01	2026-03-16T15:54:55
19508	2026-03-03	azure-finance-subscription	Bandwidth	21.66	2026-03-16T15:54:55
19509	2026-03-04	azure-finance-subscription	Virtual Machines	145.71	2026-03-16T15:54:55
19510	2026-03-04	azure-finance-subscription	Storage	41.74	2026-03-16T15:54:55
19511	2026-03-04	azure-finance-subscription	SQL Database	84.66	2026-03-16T15:54:55
19512	2026-03-04	azure-finance-subscription	Bandwidth	22.09	2026-03-16T15:54:55
19513	2026-03-05	azure-finance-subscription	Virtual Machines	213.95	2026-03-16T15:54:55
19514	2026-03-05	azure-finance-subscription	Storage	42.56	2026-03-16T15:54:55
19515	2026-03-05	azure-finance-subscription	SQL Database	86.33	2026-03-16T15:54:55
19516	2026-03-05	azure-finance-subscription	Bandwidth	32.43	2026-03-16T15:54:55
19517	2026-03-06	azure-finance-subscription	Virtual Machines	192.45	2026-03-16T15:54:55
19518	2026-03-06	azure-finance-subscription	Storage	38.28	2026-03-16T15:54:55
19519	2026-03-06	azure-finance-subscription	SQL Database	77.66	2026-03-16T15:54:55
19520	2026-03-06	azure-finance-subscription	Bandwidth	29.18	2026-03-16T15:54:55
19521	2026-03-07	azure-finance-subscription	Virtual Machines	226.04	2026-03-16T15:54:55
19522	2026-03-07	azure-finance-subscription	Storage	39.1	2026-03-16T15:54:55
19523	2026-03-07	azure-finance-subscription	SQL Database	79.31	2026-03-16T15:54:55
19524	2026-03-07	azure-finance-subscription	Bandwidth	29.8	2026-03-16T15:54:55
19525	2026-03-08	azure-finance-subscription	Virtual Machines	200.67	2026-03-16T15:54:55
19526	2026-03-08	azure-finance-subscription	Storage	39.91	2026-03-16T15:54:55
19527	2026-03-08	azure-finance-subscription	SQL Database	80.97	2026-03-16T15:54:55
19528	2026-03-08	azure-finance-subscription	Bandwidth	30.42	2026-03-16T15:54:55
19529	2026-03-09	azure-finance-subscription	Virtual Machines	204.8	2026-03-16T15:54:55
19530	2026-03-09	azure-finance-subscription	Storage	40.74	2026-03-16T15:54:55
19531	2026-03-09	azure-finance-subscription	SQL Database	82.64	2026-03-16T15:54:55
19532	2026-03-09	azure-finance-subscription	Bandwidth	31.05	2026-03-16T15:54:55
19533	2026-03-10	azure-finance-subscription	Virtual Machines	208.95	2026-03-16T15:54:55
19534	2026-03-10	azure-finance-subscription	Storage	41.56	2026-03-16T15:54:55
19535	2026-03-10	azure-finance-subscription	SQL Database	84.31	2026-03-16T15:54:55
19536	2026-03-10	azure-finance-subscription	Bandwidth	31.68	2026-03-16T15:54:55
19537	2026-03-11	azure-finance-subscription	Virtual Machines	213.11	2026-03-16T15:54:55
19538	2026-03-11	azure-finance-subscription	Storage	42.39	2026-03-16T15:54:55
19539	2026-03-11	azure-finance-subscription	SQL Database	85.99	2026-03-16T15:54:55
19540	2026-03-11	azure-finance-subscription	Bandwidth	32.31	2026-03-16T15:54:55
19541	2026-03-12	azure-finance-subscription	Virtual Machines	217.29	2026-03-16T15:54:55
19542	2026-03-12	azure-finance-subscription	Storage	43.22	2026-03-16T15:54:55
19543	2026-03-12	azure-finance-subscription	SQL Database	87.68	2026-03-16T15:54:55
19544	2026-03-12	azure-finance-subscription	Bandwidth	32.94	2026-03-16T15:54:55
19545	2026-03-13	azure-finance-subscription	Virtual Machines	195.45	2026-03-16T15:54:55
19546	2026-03-13	azure-finance-subscription	Storage	38.88	2026-03-16T15:54:55
19547	2026-03-13	azure-finance-subscription	SQL Database	78.87	2026-03-16T15:54:55
19548	2026-03-13	azure-finance-subscription	Bandwidth	29.63	2026-03-16T15:54:55
19549	2026-03-14	azure-finance-subscription	Virtual Machines	199.61	2026-03-16T15:54:55
19550	2026-03-14	azure-finance-subscription	Storage	39.7	2026-03-16T15:54:55
19551	2026-03-14	azure-finance-subscription	SQL Database	80.54	2026-03-16T15:54:55
19552	2026-03-14	azure-finance-subscription	Bandwidth	30.26	2026-03-16T15:54:55
19553	2026-03-15	azure-finance-subscription	Virtual Machines	203.78	2026-03-16T15:54:55
19554	2026-03-15	azure-finance-subscription	Storage	40.53	2026-03-16T15:54:55
19555	2026-03-15	azure-finance-subscription	SQL Database	82.23	2026-03-16T15:54:55
19556	2026-03-15	azure-finance-subscription	Bandwidth	30.89	2026-03-16T15:54:55
19557	2026-03-16	azure-finance-subscription	Virtual Machines	207.97	2026-03-16T15:54:55
19558	2026-03-16	azure-finance-subscription	Storage	41.37	2026-03-16T15:54:55
19559	2026-03-16	azure-finance-subscription	SQL Database	83.92	2026-03-16T15:54:55
19560	2026-03-16	azure-finance-subscription	Bandwidth	31.53	2026-03-16T15:54:55
19561	2026-01-16	gcp-analytics-billing	BigQuery	95.89	2026-03-16T15:54:55
19562	2026-01-16	gcp-analytics-billing	Cloud Storage	24.71	2026-03-16T15:54:55
19563	2026-01-16	gcp-analytics-billing	Compute Engine	103.28	2026-03-16T15:54:55
19564	2026-01-16	gcp-analytics-billing	Cloud Functions	13.24	2026-03-16T15:54:55
19565	2026-01-17	gcp-analytics-billing	BigQuery	97.96	2026-03-16T15:54:55
19566	2026-01-17	gcp-analytics-billing	Cloud Storage	25.25	2026-03-16T15:54:55
19567	2026-01-17	gcp-analytics-billing	Compute Engine	105.51	2026-03-16T15:54:55
19568	2026-01-17	gcp-analytics-billing	Cloud Functions	13.53	2026-03-16T15:54:55
19569	2026-01-18	gcp-analytics-billing	BigQuery	100.04	2026-03-16T15:54:55
19570	2026-01-18	gcp-analytics-billing	Cloud Storage	25.78	2026-03-16T15:54:55
19571	2026-01-18	gcp-analytics-billing	Compute Engine	107.75	2026-03-16T15:54:55
19572	2026-01-18	gcp-analytics-billing	Cloud Functions	13.82	2026-03-16T15:54:55
19573	2026-01-19	gcp-analytics-billing	BigQuery	102.13	2026-03-16T15:54:55
19574	2026-01-19	gcp-analytics-billing	Cloud Storage	26.32	2026-03-16T15:54:55
19575	2026-01-19	gcp-analytics-billing	Compute Engine	110	2026-03-16T15:54:55
19576	2026-01-19	gcp-analytics-billing	Cloud Functions	14.11	2026-03-16T15:54:55
19577	2026-01-20	gcp-analytics-billing	BigQuery	104.22	2026-03-16T15:54:55
19578	2026-01-20	gcp-analytics-billing	Cloud Storage	26.86	2026-03-16T15:54:55
19579	2026-01-20	gcp-analytics-billing	Compute Engine	112.26	2026-03-16T15:54:55
19580	2026-01-20	gcp-analytics-billing	Cloud Functions	14.39	2026-03-16T15:54:55
19581	2026-01-21	gcp-analytics-billing	BigQuery	123.34	2026-03-16T15:54:55
19582	2026-01-21	gcp-analytics-billing	Cloud Storage	27.4	2026-03-16T15:54:55
19583	2026-01-21	gcp-analytics-billing	Compute Engine	114.52	2026-03-16T15:54:55
19584	2026-01-21	gcp-analytics-billing	Cloud Functions	14.69	2026-03-16T15:54:55
19585	2026-01-22	gcp-analytics-billing	BigQuery	108.44	2026-03-16T15:54:55
19586	2026-01-22	gcp-analytics-billing	Cloud Storage	27.95	2026-03-16T15:54:55
19587	2026-01-22	gcp-analytics-billing	Compute Engine	116.8	2026-03-16T15:54:55
19588	2026-01-22	gcp-analytics-billing	Cloud Functions	14.98	2026-03-16T15:54:55
19589	2026-01-23	gcp-analytics-billing	BigQuery	97.57	2026-03-16T15:54:55
19590	2026-01-23	gcp-analytics-billing	Cloud Storage	25.15	2026-03-16T15:54:55
19591	2026-01-23	gcp-analytics-billing	Compute Engine	105.09	2026-03-16T15:54:55
19592	2026-01-23	gcp-analytics-billing	Cloud Functions	13.48	2026-03-16T15:54:55
19593	2026-01-24	gcp-analytics-billing	BigQuery	99.67	2026-03-16T15:54:55
19594	2026-01-24	gcp-analytics-billing	Cloud Storage	25.69	2026-03-16T15:54:55
19595	2026-01-24	gcp-analytics-billing	Compute Engine	107.35	2026-03-16T15:54:55
19596	2026-01-24	gcp-analytics-billing	Cloud Functions	13.77	2026-03-16T15:54:55
19597	2026-01-25	gcp-analytics-billing	BigQuery	101.78	2026-03-16T15:54:55
19598	2026-01-25	gcp-analytics-billing	Cloud Storage	26.23	2026-03-16T15:54:55
19599	2026-01-25	gcp-analytics-billing	Compute Engine	109.63	2026-03-16T15:54:55
19600	2026-01-25	gcp-analytics-billing	Cloud Functions	14.06	2026-03-16T15:54:55
19601	2026-01-26	gcp-analytics-billing	BigQuery	103.9	2026-03-16T15:54:55
19602	2026-01-26	gcp-analytics-billing	Cloud Storage	26.78	2026-03-16T15:54:55
19603	2026-01-26	gcp-analytics-billing	Compute Engine	111.91	2026-03-16T15:54:55
19604	2026-01-26	gcp-analytics-billing	Cloud Functions	14.35	2026-03-16T15:54:55
19605	2026-01-27	gcp-analytics-billing	BigQuery	106.03	2026-03-16T15:54:55
19606	2026-01-27	gcp-analytics-billing	Cloud Storage	27.33	2026-03-16T15:54:55
19607	2026-01-27	gcp-analytics-billing	Compute Engine	114.2	2026-03-16T15:54:55
19608	2026-01-27	gcp-analytics-billing	Cloud Functions	14.64	2026-03-16T15:54:55
19609	2026-01-28	gcp-analytics-billing	BigQuery	108.16	2026-03-16T15:54:55
19610	2026-01-28	gcp-analytics-billing	Cloud Storage	27.88	2026-03-16T15:54:55
19611	2026-01-28	gcp-analytics-billing	Compute Engine	116.5	2026-03-16T15:54:55
19612	2026-01-28	gcp-analytics-billing	Cloud Functions	14.94	2026-03-16T15:54:55
19613	2026-01-29	gcp-analytics-billing	BigQuery	110.31	2026-03-16T15:54:55
19614	2026-01-29	gcp-analytics-billing	Cloud Storage	28.43	2026-03-16T15:54:55
19615	2026-01-29	gcp-analytics-billing	Compute Engine	118.82	2026-03-16T15:54:55
19616	2026-01-29	gcp-analytics-billing	Cloud Functions	15.24	2026-03-16T15:54:55
19617	2026-01-30	gcp-analytics-billing	BigQuery	99.25	2026-03-16T15:54:55
19618	2026-01-30	gcp-analytics-billing	Cloud Storage	25.58	2026-03-16T15:54:55
19619	2026-01-30	gcp-analytics-billing	Compute Engine	106.9	2026-03-16T15:54:55
19620	2026-01-30	gcp-analytics-billing	Cloud Functions	13.71	2026-03-16T15:54:55
19621	2026-01-31	gcp-analytics-billing	BigQuery	101.38	2026-03-16T15:54:55
19622	2026-01-31	gcp-analytics-billing	Cloud Storage	26.13	2026-03-16T15:54:55
19623	2026-01-31	gcp-analytics-billing	Compute Engine	109.2	2026-03-16T15:54:55
19624	2026-01-31	gcp-analytics-billing	Cloud Functions	14	2026-03-16T15:54:55
19625	2026-02-01	gcp-analytics-billing	BigQuery	103.52	2026-03-16T15:54:55
19626	2026-02-01	gcp-analytics-billing	Cloud Storage	26.68	2026-03-16T15:54:55
19627	2026-02-01	gcp-analytics-billing	Compute Engine	111.5	2026-03-16T15:54:55
19628	2026-02-01	gcp-analytics-billing	Cloud Functions	14.3	2026-03-16T15:54:55
19629	2026-02-02	gcp-analytics-billing	BigQuery	105.67	2026-03-16T15:54:55
19630	2026-02-02	gcp-analytics-billing	Cloud Storage	27.24	2026-03-16T15:54:55
19631	2026-02-02	gcp-analytics-billing	Compute Engine	113.82	2026-03-16T15:54:55
19632	2026-02-02	gcp-analytics-billing	Cloud Functions	14.59	2026-03-16T15:54:55
19633	2026-02-03	gcp-analytics-billing	BigQuery	107.83	2026-03-16T15:54:55
19634	2026-02-03	gcp-analytics-billing	Cloud Storage	27.79	2026-03-16T15:54:55
19635	2026-02-03	gcp-analytics-billing	Compute Engine	116.15	2026-03-16T15:54:55
19636	2026-02-03	gcp-analytics-billing	Cloud Functions	14.89	2026-03-16T15:54:55
19637	2026-02-04	gcp-analytics-billing	BigQuery	110	2026-03-16T15:54:55
19638	2026-02-04	gcp-analytics-billing	Cloud Storage	28.35	2026-03-16T15:54:55
19639	2026-02-04	gcp-analytics-billing	Compute Engine	118.48	2026-03-16T15:54:55
19640	2026-02-04	gcp-analytics-billing	Cloud Functions	15.19	2026-03-16T15:54:55
19641	2026-02-05	gcp-analytics-billing	BigQuery	112.18	2026-03-16T15:54:55
19642	2026-02-05	gcp-analytics-billing	Cloud Storage	28.91	2026-03-16T15:54:55
19643	2026-02-05	gcp-analytics-billing	Compute Engine	120.83	2026-03-16T15:54:55
19644	2026-02-05	gcp-analytics-billing	Cloud Functions	15.49	2026-03-16T15:54:55
19645	2026-02-06	gcp-analytics-billing	BigQuery	100.93	2026-03-16T15:54:55
19646	2026-02-06	gcp-analytics-billing	Cloud Storage	26.01	2026-03-16T15:54:55
19647	2026-02-06	gcp-analytics-billing	Compute Engine	108.71	2026-03-16T15:54:55
19648	2026-02-06	gcp-analytics-billing	Cloud Functions	13.94	2026-03-16T15:54:55
19649	2026-02-07	gcp-analytics-billing	BigQuery	119.58	2026-03-16T15:54:55
19650	2026-02-07	gcp-analytics-billing	Cloud Storage	26.57	2026-03-16T15:54:55
19651	2026-02-07	gcp-analytics-billing	Compute Engine	111.04	2026-03-16T15:54:55
19652	2026-02-07	gcp-analytics-billing	Cloud Functions	14.24	2026-03-16T15:54:55
19653	2026-02-08	gcp-analytics-billing	BigQuery	105.26	2026-03-16T15:54:55
19654	2026-02-08	gcp-analytics-billing	Cloud Storage	27.13	2026-03-16T15:54:55
19655	2026-02-08	gcp-analytics-billing	Compute Engine	113.38	2026-03-16T15:54:55
19656	2026-02-08	gcp-analytics-billing	Cloud Functions	14.54	2026-03-16T15:54:55
19657	2026-02-09	gcp-analytics-billing	BigQuery	107.45	2026-03-16T15:54:55
19658	2026-02-09	gcp-analytics-billing	Cloud Storage	27.69	2026-03-16T15:54:55
19659	2026-02-09	gcp-analytics-billing	Compute Engine	115.73	2026-03-16T15:54:55
19660	2026-02-09	gcp-analytics-billing	Cloud Functions	14.84	2026-03-16T15:54:55
19661	2026-02-10	gcp-analytics-billing	BigQuery	109.64	2026-03-16T15:54:55
19662	2026-02-10	gcp-analytics-billing	Cloud Storage	28.26	2026-03-16T15:54:55
19663	2026-02-10	gcp-analytics-billing	Compute Engine	118.09	2026-03-16T15:54:55
19664	2026-02-10	gcp-analytics-billing	Cloud Functions	15.14	2026-03-16T15:54:55
19665	2026-02-11	gcp-analytics-billing	BigQuery	111.84	2026-03-16T15:54:55
19666	2026-02-11	gcp-analytics-billing	Cloud Storage	28.82	2026-03-16T15:54:55
19667	2026-02-11	gcp-analytics-billing	Compute Engine	120.46	2026-03-16T15:54:55
19668	2026-02-11	gcp-analytics-billing	Cloud Functions	15.45	2026-03-16T15:54:55
19669	2026-02-12	gcp-analytics-billing	BigQuery	114.05	2026-03-16T15:54:55
19670	2026-02-12	gcp-analytics-billing	Cloud Storage	29.39	2026-03-16T15:54:55
19671	2026-02-12	gcp-analytics-billing	Compute Engine	122.84	2026-03-16T15:54:55
19672	2026-02-12	gcp-analytics-billing	Cloud Functions	15.75	2026-03-16T15:54:55
19673	2026-02-13	gcp-analytics-billing	BigQuery	102.6	2026-03-16T15:54:55
19674	2026-02-13	gcp-analytics-billing	Cloud Storage	26.44	2026-03-16T15:54:55
19675	2026-02-13	gcp-analytics-billing	Compute Engine	110.51	2026-03-16T15:54:55
19676	2026-02-13	gcp-analytics-billing	Cloud Functions	14.17	2026-03-16T15:54:55
19677	2026-02-14	gcp-analytics-billing	BigQuery	104.8	2026-03-16T15:54:55
19678	2026-02-14	gcp-analytics-billing	Cloud Storage	27.01	2026-03-16T15:54:55
19679	2026-02-14	gcp-analytics-billing	Compute Engine	112.88	2026-03-16T15:54:55
19680	2026-02-14	gcp-analytics-billing	Cloud Functions	14.47	2026-03-16T15:54:55
19681	2026-02-15	gcp-analytics-billing	BigQuery	107.01	2026-03-16T15:54:55
19682	2026-02-15	gcp-analytics-billing	Cloud Storage	27.58	2026-03-16T15:54:55
19683	2026-02-15	gcp-analytics-billing	Compute Engine	115.26	2026-03-16T15:54:55
19684	2026-02-15	gcp-analytics-billing	Cloud Functions	14.78	2026-03-16T15:54:55
19685	2026-02-16	gcp-analytics-billing	BigQuery	109.22	2026-03-16T15:54:55
19686	2026-02-16	gcp-analytics-billing	Cloud Storage	28.15	2026-03-16T15:54:55
19687	2026-02-16	gcp-analytics-billing	Compute Engine	117.64	2026-03-16T15:54:55
19688	2026-02-16	gcp-analytics-billing	Cloud Functions	15.08	2026-03-16T15:54:55
19689	2026-02-17	gcp-analytics-billing	BigQuery	111.44	2026-03-16T15:54:55
19690	2026-02-17	gcp-analytics-billing	Cloud Storage	28.72	2026-03-16T15:54:55
19691	2026-02-17	gcp-analytics-billing	Compute Engine	120.04	2026-03-16T15:54:55
19692	2026-02-17	gcp-analytics-billing	Cloud Functions	15.39	2026-03-16T15:54:55
19693	2026-02-18	gcp-analytics-billing	BigQuery	113.68	2026-03-16T15:54:55
19694	2026-02-18	gcp-analytics-billing	Cloud Storage	29.3	2026-03-16T15:54:55
19695	2026-02-18	gcp-analytics-billing	Compute Engine	122.44	2026-03-16T15:54:55
19696	2026-02-18	gcp-analytics-billing	Cloud Functions	15.7	2026-03-16T15:54:55
19697	2026-02-19	gcp-analytics-billing	BigQuery	115.92	2026-03-16T15:54:55
19698	2026-02-19	gcp-analytics-billing	Cloud Storage	29.88	2026-03-16T15:54:55
19699	2026-02-19	gcp-analytics-billing	Compute Engine	124.86	2026-03-16T15:54:55
19700	2026-02-19	gcp-analytics-billing	Cloud Functions	16.01	2026-03-16T15:54:55
19701	2026-02-20	gcp-analytics-billing	BigQuery	104.28	2026-03-16T15:54:55
19702	2026-02-20	gcp-analytics-billing	Cloud Storage	26.88	2026-03-16T15:54:55
19703	2026-02-20	gcp-analytics-billing	Compute Engine	112.32	2026-03-16T15:54:55
19704	2026-02-20	gcp-analytics-billing	Cloud Functions	14.4	2026-03-16T15:54:55
19705	2026-02-21	gcp-analytics-billing	BigQuery	123.55	2026-03-16T15:54:55
19706	2026-02-21	gcp-analytics-billing	Cloud Storage	27.45	2026-03-16T15:54:55
19707	2026-02-21	gcp-analytics-billing	Compute Engine	114.72	2026-03-16T15:54:55
19708	2026-02-21	gcp-analytics-billing	Cloud Functions	14.71	2026-03-16T15:54:55
19709	2026-02-22	gcp-analytics-billing	BigQuery	108.75	2026-03-16T15:54:55
19710	2026-02-22	gcp-analytics-billing	Cloud Storage	28.03	2026-03-16T15:54:55
19711	2026-02-22	gcp-analytics-billing	Compute Engine	117.13	2026-03-16T15:54:55
19712	2026-02-22	gcp-analytics-billing	Cloud Functions	15.02	2026-03-16T15:54:55
19713	2026-02-23	gcp-analytics-billing	BigQuery	110.99	2026-03-16T15:54:55
19714	2026-02-23	gcp-analytics-billing	Cloud Storage	28.61	2026-03-16T15:54:55
19715	2026-02-23	gcp-analytics-billing	Compute Engine	119.55	2026-03-16T15:54:55
19716	2026-02-23	gcp-analytics-billing	Cloud Functions	15.33	2026-03-16T15:54:55
19717	2026-02-24	gcp-analytics-billing	BigQuery	113.25	2026-03-16T15:54:55
19718	2026-02-24	gcp-analytics-billing	Cloud Storage	29.19	2026-03-16T15:54:55
19719	2026-02-24	gcp-analytics-billing	Compute Engine	121.98	2026-03-16T15:54:55
19720	2026-02-24	gcp-analytics-billing	Cloud Functions	15.64	2026-03-16T15:54:55
19721	2026-02-25	gcp-analytics-billing	BigQuery	115.52	2026-03-16T15:54:55
19722	2026-02-25	gcp-analytics-billing	Cloud Storage	29.77	2026-03-16T15:54:55
19723	2026-02-25	gcp-analytics-billing	Compute Engine	124.42	2026-03-16T15:54:55
19724	2026-02-25	gcp-analytics-billing	Cloud Functions	15.95	2026-03-16T15:54:55
19725	2026-02-26	gcp-analytics-billing	BigQuery	117.79	2026-03-16T15:54:55
19726	2026-02-26	gcp-analytics-billing	Cloud Storage	30.36	2026-03-16T15:54:55
19727	2026-02-26	gcp-analytics-billing	Compute Engine	126.87	2026-03-16T15:54:55
19728	2026-02-26	gcp-analytics-billing	Cloud Functions	16.27	2026-03-16T15:54:55
19729	2026-02-27	gcp-analytics-billing	BigQuery	105.96	2026-03-16T15:54:55
19730	2026-02-27	gcp-analytics-billing	Cloud Storage	27.31	2026-03-16T15:54:55
19731	2026-02-27	gcp-analytics-billing	Compute Engine	114.13	2026-03-16T15:54:55
19732	2026-02-27	gcp-analytics-billing	Cloud Functions	14.63	2026-03-16T15:54:55
19733	2026-02-28	gcp-analytics-billing	BigQuery	108.22	2026-03-16T15:54:55
19734	2026-02-28	gcp-analytics-billing	Cloud Storage	27.89	2026-03-16T15:54:55
19735	2026-02-28	gcp-analytics-billing	Compute Engine	116.56	2026-03-16T15:54:55
19736	2026-02-28	gcp-analytics-billing	Cloud Functions	14.95	2026-03-16T15:54:55
19737	2026-03-01	gcp-analytics-billing	BigQuery	110.49	2026-03-16T15:54:55
19738	2026-03-01	gcp-analytics-billing	Cloud Storage	28.48	2026-03-16T15:54:55
19739	2026-03-01	gcp-analytics-billing	Compute Engine	119.01	2026-03-16T15:54:55
19740	2026-03-01	gcp-analytics-billing	Cloud Functions	15.26	2026-03-16T15:54:55
19741	2026-03-02	gcp-analytics-billing	BigQuery	112.77	2026-03-16T15:54:55
19742	2026-03-02	gcp-analytics-billing	Cloud Storage	29.06	2026-03-16T15:54:55
19743	2026-03-02	gcp-analytics-billing	Compute Engine	121.46	2026-03-16T15:54:55
19744	2026-03-02	gcp-analytics-billing	Cloud Functions	15.58	2026-03-16T15:54:55
19745	2026-03-03	gcp-analytics-billing	BigQuery	115.06	2026-03-16T15:54:55
19746	2026-03-03	gcp-analytics-billing	Cloud Storage	29.65	2026-03-16T15:54:55
19747	2026-03-03	gcp-analytics-billing	Compute Engine	123.93	2026-03-16T15:54:55
19748	2026-03-03	gcp-analytics-billing	Cloud Functions	15.89	2026-03-16T15:54:55
19749	2026-03-04	gcp-analytics-billing	BigQuery	117.35	2026-03-16T15:54:55
19750	2026-03-04	gcp-analytics-billing	Cloud Storage	30.25	2026-03-16T15:54:55
19751	2026-03-04	gcp-analytics-billing	Compute Engine	126.4	2026-03-16T15:54:55
19752	2026-03-04	gcp-analytics-billing	Cloud Functions	16.21	2026-03-16T15:54:55
19753	2026-03-05	gcp-analytics-billing	BigQuery	119.66	2026-03-16T15:54:55
19754	2026-03-05	gcp-analytics-billing	Cloud Storage	30.84	2026-03-16T15:54:55
19755	2026-03-05	gcp-analytics-billing	Compute Engine	128.88	2026-03-16T15:54:55
19756	2026-03-05	gcp-analytics-billing	Cloud Functions	16.53	2026-03-16T15:54:55
19757	2026-03-06	gcp-analytics-billing	BigQuery	107.64	2026-03-16T15:54:55
19758	2026-03-06	gcp-analytics-billing	Cloud Storage	27.74	2026-03-16T15:54:55
19759	2026-03-06	gcp-analytics-billing	Compute Engine	115.94	2026-03-16T15:54:55
19760	2026-03-06	gcp-analytics-billing	Cloud Functions	14.87	2026-03-16T15:54:55
19761	2026-03-07	gcp-analytics-billing	BigQuery	127.52	2026-03-16T15:54:55
19762	2026-03-07	gcp-analytics-billing	Cloud Storage	28.33	2026-03-16T15:54:55
19763	2026-03-07	gcp-analytics-billing	Compute Engine	118.41	2026-03-16T15:54:55
19764	2026-03-07	gcp-analytics-billing	Cloud Functions	15.18	2026-03-16T15:54:55
19765	2026-03-08	gcp-analytics-billing	BigQuery	152.64	2026-03-16T15:54:55
19766	2026-03-08	gcp-analytics-billing	Cloud Storage	28.93	2026-03-16T15:54:55
19767	2026-03-08	gcp-analytics-billing	Compute Engine	164.4	2026-03-16T15:54:55
19768	2026-03-08	gcp-analytics-billing	Cloud Functions	15.5	2026-03-16T15:54:55
19769	2026-03-09	gcp-analytics-billing	BigQuery	155.78	2026-03-16T15:54:55
19770	2026-03-09	gcp-analytics-billing	Cloud Storage	29.52	2026-03-16T15:54:55
19771	2026-03-09	gcp-analytics-billing	Compute Engine	167.79	2026-03-16T15:54:55
19772	2026-03-09	gcp-analytics-billing	Cloud Functions	15.82	2026-03-16T15:54:55
19773	2026-03-10	gcp-analytics-billing	BigQuery	158.93	2026-03-16T15:54:55
19774	2026-03-10	gcp-analytics-billing	Cloud Storage	30.12	2026-03-16T15:54:55
19775	2026-03-10	gcp-analytics-billing	Compute Engine	171.19	2026-03-16T15:54:55
19776	2026-03-10	gcp-analytics-billing	Cloud Functions	16.14	2026-03-16T15:54:55
19777	2026-03-11	gcp-analytics-billing	BigQuery	162.1	2026-03-16T15:54:55
19778	2026-03-11	gcp-analytics-billing	Cloud Storage	30.72	2026-03-16T15:54:55
19779	2026-03-11	gcp-analytics-billing	Compute Engine	174.6	2026-03-16T15:54:55
19780	2026-03-11	gcp-analytics-billing	Cloud Functions	16.46	2026-03-16T15:54:55
19781	2026-03-12	gcp-analytics-billing	BigQuery	165.28	2026-03-16T15:54:55
19782	2026-03-12	gcp-analytics-billing	Cloud Storage	31.32	2026-03-16T15:54:55
19783	2026-03-12	gcp-analytics-billing	Compute Engine	178.02	2026-03-16T15:54:55
19784	2026-03-12	gcp-analytics-billing	Cloud Functions	16.78	2026-03-16T15:54:55
19785	2026-03-13	gcp-analytics-billing	BigQuery	148.67	2026-03-16T15:54:55
19786	2026-03-13	gcp-analytics-billing	Cloud Storage	28.17	2026-03-16T15:54:55
19787	2026-03-13	gcp-analytics-billing	Compute Engine	160.13	2026-03-16T15:54:55
19788	2026-03-13	gcp-analytics-billing	Cloud Functions	15.1	2026-03-16T15:54:55
19789	2026-03-14	gcp-analytics-billing	BigQuery	151.83	2026-03-16T15:54:55
19790	2026-03-14	gcp-analytics-billing	Cloud Storage	28.77	2026-03-16T15:54:55
19791	2026-03-14	gcp-analytics-billing	Compute Engine	163.54	2026-03-16T15:54:55
19792	2026-03-14	gcp-analytics-billing	Cloud Functions	15.42	2026-03-16T15:54:55
19793	2026-03-15	gcp-analytics-billing	BigQuery	155	2026-03-16T15:54:55
19794	2026-03-15	gcp-analytics-billing	Cloud Storage	29.37	2026-03-16T15:54:55
19795	2026-03-15	gcp-analytics-billing	Compute Engine	166.95	2026-03-16T15:54:55
19796	2026-03-15	gcp-analytics-billing	Cloud Functions	15.74	2026-03-16T15:54:55
19797	2026-03-16	gcp-analytics-billing	BigQuery	158.19	2026-03-16T15:54:55
19798	2026-03-16	gcp-analytics-billing	Cloud Storage	29.98	2026-03-16T15:54:55
19799	2026-03-16	gcp-analytics-billing	Compute Engine	170.39	2026-03-16T15:54:55
19800	2026-03-16	gcp-analytics-billing	Cloud Functions	16.06	2026-03-16T15:54:55
\.


--
-- Data for Name: cloud_accounts; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.cloud_accounts (id, username, provider, account_name, account_identifier, details, credentials_encrypted, sync_enabled, status, last_synced_at, last_error, created_at, updated_at, validation_status, validation_message, health_score, last_validation_at, sync_frequency_hours, coverage_start, coverage_end, last_sync_duration_seconds, last_sync_record_count, next_sync_at, company) FROM stdin;
64	admin	aws	aws-prod-finops	arn:aws:iam::123456789012:role/finops-demo-role	{"status": "validated", "message": "AWS spend has accelerated sharply in the last 10 days.", "health_score": 81, "sync_frequency_hours": 6}	gAAAAABpuCfPNmwEV94I3wm851gSNEczyPPnpfwfalFY4mYPxW7X-nsLoH5YRb2i99RAluRxbkB7e1Wxaj4D-NMg9cslLqiWxNFSsH1iE3MWfBbTumApMPLmH7iwzhdF1JjlnnKajJA-ACzap58_gcYiOit5xeL-nsfc56V0Yu5z18w5MBBHIm98foLKWnOKY6x_QLR4UeF-9wegKzdDDxoN3UcMLTFJJA==	1	synced	2026-03-16T15:54:55	\N	2026-03-16 15:54:55	2026-03-16 15:54:55	validated	AWS spend has accelerated sharply in the last 10 days.	81	2026-03-16T15:54:55	6	2026-01-16	2026-03-16	6.4	240	2026-03-16T21:54:55	Cloud Advisor Internal
65	admin	azure	azure-finance-subscription	00000000-1111-2222-3333-444444444444	{"status": "validated", "message": "Azure analytics workloads show an ongoing cost spike.", "health_score": 79, "sync_frequency_hours": 6}	gAAAAABpuCfP0PFiVtF9pb3Q2PwOGFVXAiVbEQtYyXEP4MzJhttg4c9s9EqpDLCN0oJqe_7dYUnwANhel99438ICNcww3_QfX3mXUYv0356DlnTOaZvcucWiEdc72-fYgNaJY-7HkIFgv84KN6CdEtRM8ZkyV0sy0OdzVHdtWBwMY0IvEDqZdLEcuf6DVYSGpOPgLi6QckzJuCDKMuVjYLAnEOn9Qk0YcMZ50fJrx8-1t6RGqdPT_us6cyFjwWRPmzt9DOqhtL1E2S-NpOShOF6MOnxg5XPm7Il0bJnGcRwV6IUjh6jNQYw=	1	synced	2026-03-16T15:54:55	\N	2026-03-16 15:54:55	2026-03-16 15:54:55	validated	Azure analytics workloads show an ongoing cost spike.	79	2026-03-16T15:54:55	6	2026-01-16	2026-03-16	6.4	240	2026-03-16T21:54:55	Cloud Advisor Internal
66	admin	gcp	gcp-analytics-billing	projects/demo-billing/datasets/cloud_billing/tables/export_v1	{"status": "validated", "message": "GCP query demand increased materially near month-end.", "health_score": 84, "sync_frequency_hours": 12}	gAAAAABpuCfPDRWrP9obpK_B2DU8PzfIk1WSXP49ZpbkG-1E-WRj97cYP2kVI7CqubtNdJQzJJ_BGfkTi9lLXLB_v5TaVbvIvOQqsfFZoCfmPURXDykifbUSx33WHhySf_Fk95EoZF4dy2FFaUTAXgy-RSY5WrFoVBAT9dMWpSxk5PO40oeUgbSvb1myYcNt1CV4Izxlv2R4D9eLj6ltmXEhuDX4SiH4Uu1dm0CH3tvRjlht6P-2qW3aKbD6Vjo3v3t12I4a6Bwb7pDWDZMYdoDuwTWABVM_fm48nvJ9S1Q4mCwfRJOn0YprJxaknzT0xA-114zgpYHZlnVrDiEhRvSxDyU51qhzURS1ZI4ZFpf4xvbkAQbSLMpJBiutxio4PthKgXTon5sL	1	synced	2026-03-16T15:54:55	\N	2026-03-16 15:54:55	2026-03-16 15:54:55	validated	GCP query demand increased materially near month-end.	84	2026-03-16T15:54:55	12	2026-01-16	2026-03-16	6.4	240	2026-03-17T03:54:55	Cloud Advisor Internal
\.


--
-- Data for Name: cloud_sync_runs; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.cloud_sync_runs (id, cloud_account_id, username, provider, status, trigger_type, started_at, finished_at, duration_seconds, record_count, coverage_start, coverage_end, error_code, error_message, metadata, company) FROM stdin;
76	64	admin	aws	success	demo_seed	2026-03-16T15:54:55	2026-03-16T15:54:55	6.4	240	2026-01-16	2026-03-16	\N	\N	{"account_identifier": "arn:aws:iam::123456789012:role/finops-demo-role", "seeded": true}	Cloud Advisor Internal
77	65	admin	azure	success	demo_seed	2026-03-16T15:54:55	2026-03-16T15:54:55	6.4	240	2026-01-16	2026-03-16	\N	\N	{"account_identifier": "00000000-1111-2222-3333-444444444444", "seeded": true}	Cloud Advisor Internal
78	66	admin	gcp	success	demo_seed	2026-03-16T15:54:55	2026-03-16T15:54:55	6.4	240	2026-01-16	2026-03-16	\N	\N	{"account_identifier": "projects/demo-billing/datasets/cloud_billing/tables/export_v1", "seeded": true}	Cloud Advisor Internal
\.


--
-- Data for Name: companies; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.companies (company_name, company_type, plan, created_by, created_at, updated_at) FROM stdin;
Cloud Advisor Internal	internal	Enterprise	system	2026-03-15T16:10:57	2026-03-16T05:28:59
Test	client	Starter	admin	2026-03-15T16:17:06	2026-03-16T05:28:59
\.


--
-- Data for Name: company_subscriptions; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.company_subscriptions (company_name, plan, billing_cycle, subscription_status, trial_started_at, trial_ends_at, cancel_at_period_end, stripe_customer_id, stripe_subscription_id, stripe_checkout_session_id, stripe_price_id, current_period_end, source, last_synced_at, updated_at) FROM stdin;
\.


--
-- Data for Name: forecast_notes; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.forecast_notes (username, forecast_date, note) FROM stdin;
\.


--
-- Data for Name: recommendation_events; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.recommendation_events (id, recommendation_id, username, action, old_value, new_value, notes, created_at, company) FROM stdin;
50	17	admin	details_updated	{"owner": null, "priority": "high", "due_date": null}	{"owner": "admin", "priority": "high", "due_date": null}	Updated assignee from quick assignment table	2026-03-15T13:52:03	Cloud Advisor Internal
53	17	admin	details_updated	{"owner": "admin", "priority": "high", "due_date": null}	{"owner": null, "priority": "high", "due_date": null}	Updated assignee from recommendation queue	2026-03-15T14:16:27	Cloud Advisor Internal
54	17	admin	status_changed	new	completed	Completed from recommendations inbox	2026-03-15T14:17:15	Cloud Advisor Internal
55	17	admin	status_changed	completed	completed	Completed from recommendations inbox	2026-03-15T14:17:16	Cloud Advisor Internal
58	96	admin	status_changed	new	accepted	Accepted automatically for demo workflow setup.	2026-03-16T15:54:56	Cloud Advisor Internal
59	99	admin	status_changed	new	snoozed	Snoozed automatically for demo workflow setup.	2026-03-16T15:54:56	Cloud Advisor Internal
\.


--
-- Data for Name: recommendations; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.recommendations (id, username, account_identifier, provider, category, title, description, status, owner, priority, estimated_savings, realized_savings, due_date, dismiss_reason, source, resource, created_at, updated_at, completed_at, confidence_score, rationale, effort_level, action_steps, company) FROM stdin;
16	admin	\N	\N	rightsizing	Rightsize EC2 compute cluster	Several EC2 instances are consistently underutilized and can be moved to a smaller instance family.	new	\N	high	4200	0	\N	\N	optimization_insights	aws-prod:EC2	2026-03-15T11:25:35	2026-03-15T11:25:35	\N	\N	\N	\N	\N	Cloud Advisor Internal
17	admin	\N	\N	database	Rightsize RDS instances	RDS CPU and memory utilization suggest the database tier is oversized for current demand.	completed	\N	high	2100	0	\N	\N	optimization_insights	aws-prod:RDS	2026-03-15T11:25:35	2026-03-15T14:17:16	2026-03-15T14:17:16	\N	\N	\N	\N	Cloud Advisor Internal
18	admin	\N	\N	storage	Remove unattached EBS volumes	Unused EBS volumes are accruing storage charges with no active attachment history.	new	\N	medium	800	0	\N	\N	optimization_insights	aws-dev:EBS	2026-03-15T11:25:35	2026-03-15T11:25:35	\N	\N	\N	\N	\N	Cloud Advisor Internal
19	admin	\N	\N	lifecycle	Move cold S3 data to infrequent access	Older S3 objects are good candidates for lifecycle transitions to lower-cost storage classes.	new	\N	medium	1200	0	\N	\N	optimization_insights	aws-analytics:S3	2026-03-15T11:25:35	2026-03-15T11:25:35	\N	\N	\N	\N	\N	Cloud Advisor Internal
96	admin	arn:aws:iam::123456789012:role/finops-demo-role	aws	anomaly	Investigate compute cost spike	AWS and Azure compute costs accelerated sharply in the last ten days of the demo period.	accepted	admin	high	3100	0	2026-03-18	\N	demo_environment	shared:cost-spike-anomaly	2026-03-16T15:54:56	2026-03-16T15:54:56	\N	0.9	This cost spike demo scenario was seeded to make investigate compute cost spike a visible operational follow-up for the AWS estate.	medium	["Compare the last two weeks of spend against the prior baseline to isolate the spike window.", "Review the top services and accounts contributing to the variance.", "Decide whether the increase is expected demand or avoidable waste before month-end actions are taken."]	Cloud Advisor Internal
97	admin	\N	\N	forecast	Validate forecast increase drivers	Recent cost acceleration is large enough to change the next-month forecast materially.	new	admin	high	1800	0	2026-03-19	\N	demo_environment	shared:forecast-variance	2026-03-16T15:54:56	2026-03-16T15:54:56	\N	0.9	This cost spike demo scenario was seeded to make validate forecast increase drivers a visible operational follow-up for the SHARED estate.	low	["Validate whether the forecast jump is driven by a recent spike or a broader trend shift.", "Check if commitments, reservations, or scheduling changes could offset the projected increase.", "Document the decision so the finance review has a clear explanation for the variance."]	Cloud Advisor Internal
98	admin	projects/demo-billing/datasets/cloud_billing/tables/export_v1	gcp	query-optimization	Review BigQuery demand surge	The demo GCP account shows a sustained increase in analytics query volume near month-end.	new	admin	medium	950	0	2026-03-20	\N	demo_environment	gcp-analytics-billing:query-spike	2026-03-16T15:54:56	2026-03-16T15:54:56	\N	0.78	This cost spike demo scenario was seeded to make review bigquery demand surge a visible operational follow-up for the GCP estate.	medium	["Inspect the largest query or analytics jobs driving the month-end surge.", "Target partitioning, caching, or scheduling changes that reduce repeated scans.", "Track the cost delta after the change to confirm the optimization impact."]	Cloud Advisor Internal
99	admin	\N	\N	forecast	Investigate 1-month forecast spike	The seeded forecast projects a material increase versus the recent baseline so the workflow and dashboard risk summary can be tested.	snoozed	admin	high	3600	0	2026-03-19	\N	cost_forecast	shared:forecast-spike	2026-03-16T15:54:56	2026-03-16T15:54:56	\N	0.9	This cost spike demo scenario was seeded to make investigate 1-month forecast spike a visible operational follow-up for the SHARED estate.	low	["Validate whether the forecast jump is driven by a recent spike or a broader trend shift.", "Check if commitments, reservations, or scheduling changes could offset the projected increase.", "Document the decision so the finance review has a clear explanation for the variance."]	Cloud Advisor Internal
\.


--
-- Data for Name: subscriptions; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.subscriptions (username, plan, updated_at) FROM stdin;
admin	Starter	2026-03-15T16:02:00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: myappuser
--

COPY public.users (username, password, role, company, user_type, created_by, created_at, updated_at, onboarding_complete) FROM stdin;
admin	cloud123	global_admin	Cloud Advisor Internal	internal	\N	2026-03-15T16:10:57	2026-03-15T16:10:57	0
User1	user1	client_admin	Test	client	admin	2026-03-15T16:17:06	2026-03-17T10:34:45	1
Finance	finance123	premium	Test	client	User1	2026-03-15T16:26:23	2026-03-15T16:40:42	0
\.


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

\unrestrict AkyXkBgNqJXRJc50KlLrJ2hLeCMSrQeVmitivlt1aysTeXL2fPWRBRwutQnbgHA

