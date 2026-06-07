


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


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE OR REPLACE FUNCTION "public"."accept_recommendation"("rec_id" "uuid", "user_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
begin
    update recommendations
    set status = 'accepted'
    where id = rec_id;

    insert into actions_log (recommendation_id, user_id, action)
    values (rec_id, user_id, 'accepted');
end;
$$;


ALTER FUNCTION "public"."accept_recommendation"("rec_id" "uuid", "user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."apply_recommendation"("rec_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
begin
    update recommendations
    set status = 'implemented'
    where id = rec_id;

    insert into realized_savings (recommendation_id, amount)
    select id, estimated_savings
    from recommendations
    where id = rec_id;
end;
$$;


ALTER FUNCTION "public"."apply_recommendation"("rec_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."apply_recommendation"("rec_id" "uuid", "user_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
declare
    rec record;
begin
    -- get recommendation
    select * into rec from recommendations where id = rec_id;

    -- update status
    update recommendations
    set status = 'implemented'
    where id = rec_id;

    -- insert savings
    insert into realized_savings (recommendation_id, org_id, amount)
    values (rec.id, rec.org_id, rec.estimated_savings);

    -- log action
    insert into actions_log (recommendation_id, user_id, action)
    values (rec.id, user_id, 'implemented');

end;
$$;


ALTER FUNCTION "public"."apply_recommendation"("rec_id" "uuid", "user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."run_allocation_job"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    app_count INT;
BEGIN

SELECT COUNT(*) INTO app_count FROM core.applications;

UPDATE ingest.cost_line_items
SET allocated_cost = cost
WHERE mapped_application_id IS NOT NULL;


INSERT INTO alloc.allocation_results (
    cost_line_item_id,
    application_id,
    allocated_cost
)
SELECT
    cli.id,
    app.id,
    cli.cost / app_count
FROM ingest.cost_line_items cli
CROSS JOIN core.applications app
WHERE cli.mapped_application_id IS NULL;

END;
$$;


ALTER FUNCTION "public"."run_allocation_job"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."run_full_pipeline"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN

PERFORM run_mapping_job();
PERFORM alloc.run_allocation_engine();
PERFORM metrics.run_metrics_engine();
PERFORM ops.run_recommendation_engine();

END;
$$;


ALTER FUNCTION "public"."run_full_pipeline"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."run_mapping_job"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN

UPDATE ingest.cost_line_items cli
SET mapped_application_id = map.application_id
FROM core.app_resource_mappings map
WHERE cli.resource_id = map.resource_id;

UPDATE ingest.cost_line_items cli
SET mapped_application_id = map.application_id
FROM core.app_resource_mappings map
WHERE map.tag_key = 'app'
AND cli.tags->>'app' = map.tag_value
AND cli.mapped_application_id IS NULL;

UPDATE ingest.cost_line_items cli
SET mapped_application_id = map.application_id
FROM core.app_resource_mappings map
WHERE map.tag_key = 'service'
AND cli.service_id::text = map.tag_value
AND cli.mapped_application_id IS NULL;

END;
$$;


ALTER FUNCTION "public"."run_mapping_job"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."run_metrics_job"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN

INSERT INTO metrics.metric_values (metric_id, application_id, value, timestamp)
SELECT
    md.id,
    mtc.application_id,
    SUM(mtc.total_cost),
    CURRENT_DATE
FROM mart_total_cost mtc
JOIN metrics.metric_definitions md ON md.name = 'total_cost'
GROUP BY md.id, mtc.application_id;


INSERT INTO metrics.metric_values (metric_id, application_id, value, timestamp)
SELECT
    md.id,
    mtc.application_id,
    SUM(mtc.total_cost) / NULLIF(u.active_users, 0),
    CURRENT_DATE
FROM mart_total_cost mtc
JOIN usage.user_metrics u ON mtc.application_id = u.application_id
JOIN metrics.metric_definitions md ON md.name = 'cost_per_user'
GROUP BY md.id, mtc.application_id, u.active_users;


INSERT INTO metrics.metric_values (metric_id, application_id, value, timestamp)
SELECT
    md.id,
    mtc.application_id,
    SUM(mtc.total_cost) / NULLIF(api.total_calls, 0),
    CURRENT_DATE
FROM mart_total_cost mtc
JOIN usage.api_metrics api ON mtc.application_id = api.application_id
JOIN metrics.metric_definitions md ON md.name = 'cost_per_api'
GROUP BY md.id, mtc.application_id, api.total_calls;

END;
$$;


ALTER FUNCTION "public"."run_metrics_job"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."run_recommendation_job"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN

DELETE FROM ops.recommendations;

INSERT INTO ops.recommendations (
    application_id,
    title,
    description,
    recommendation_type,
    priority,
    estimated_savings
)
SELECT
    mv.application_id,
    'High Cost per User',
    'Cost per user is above threshold. Optimize infrastructure or scale users.',
    'efficiency',
    'high',
    mv.value * 0.2
FROM metrics.metric_values mv
JOIN metrics.metric_definitions md 
    ON mv.metric_id = md.id
WHERE md.name = 'cost_per_user'
AND mv.value > 2;

INSERT INTO ops.recommendations (
    application_id,
    title,
    description,
    recommendation_type,
    priority,
    estimated_savings
)
SELECT
    mv.application_id,
    'High Infrastructure Cost',
    'Application cost is high. Review resource utilization.',
    'cost',
    'medium',
    mv.value * 0.15
FROM metrics.metric_values mv
JOIN metrics.metric_definitions md 
    ON mv.metric_id = md.id
WHERE md.name = 'total_cost'
AND mv.value > 500;

INSERT INTO ops.recommendations (
    application_id,
    title,
    description,
    recommendation_type,
    priority,
    estimated_savings
)
SELECT
    mv.application_id,
    'High Cost per API',
    'API cost is high. Optimize compute or caching.',
    'efficiency',
    'high',
    mv.value * 0.25
FROM metrics.metric_values mv
JOIN metrics.metric_definitions md 
    ON mv.metric_id = md.id
WHERE md.name = 'cost_per_api'
AND mv.value > 0.05;

END;
$$;


ALTER FUNCTION "public"."run_recommendation_job"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."actions_log" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "recommendation_id" "uuid",
    "user_id" "uuid",
    "action" "text",
    "timestamp" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."actions_log" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."ai_audit_logs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_email" "text",
    "query" "text",
    "timestamp" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."ai_audit_logs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."allocation_rules" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "service_name" "text",
    "application_id" "uuid",
    "allocation_type" "text",
    "percentage" numeric,
    "created_at" timestamp without time zone DEFAULT "now"(),
    "org_id" "uuid",
    "rule_type" "text"
);


ALTER TABLE "public"."allocation_rules" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."applications" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid",
    "app_name" "text",
    "environment" "text",
    "created_at" timestamp without time zone DEFAULT "now"(),
    "app_code" "text",
    "org_id" "uuid"
);


ALTER TABLE "public"."applications" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cost_usage_tracking" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "application_id" "uuid",
    "created_date" timestamp without time zone,
    "total_cost" numeric,
    "service_name" "text",
    "usage_date" "date" DEFAULT CURRENT_DATE,
    "org_id" "uuid",
    "cloud_provider" "text"
);


ALTER TABLE "public"."cost_usage_tracking" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."allocation_output" AS
 WITH "service_cost" AS (
         SELECT "cost_usage_tracking"."service_name",
            "sum"("cost_usage_tracking"."total_cost") AS "total_cost"
           FROM "public"."cost_usage_tracking"
          GROUP BY "cost_usage_tracking"."service_name"
        ), "allocated" AS (
         SELECT "c"."service_name",
            "a"."app_name",
            "sum"("c"."total_cost") AS "cost",
            'allocated'::"text" AS "cost_type"
           FROM ("public"."cost_usage_tracking" "c"
             JOIN "public"."applications" "a" ON (("c"."application_id" = "a"."id")))
          GROUP BY "c"."service_name", "a"."app_name"
        ), "even_allocated" AS (
         SELECT "s"."service_name",
            "a"."app_name",
            ("s"."total_cost" / ("count"("a"."app_name") OVER (PARTITION BY "s"."service_name"))::numeric) AS "cost",
            'allocated'::"text" AS "cost_type"
           FROM (("service_cost" "s"
             JOIN "public"."allocation_rules" "r" ON (("s"."service_name" = "r"."service_name")))
             JOIN "public"."applications" "a" ON (("a"."app_name" <> 'unallocated'::"text")))
          WHERE ("r"."rule_type" = 'EVEN'::"text")
        )
 SELECT "allocated"."service_name",
    "allocated"."app_name",
    "allocated"."cost",
    "allocated"."cost_type"
   FROM "allocated"
UNION ALL
 SELECT "even_allocated"."service_name",
    "even_allocated"."app_name",
    "even_allocated"."cost",
    "even_allocated"."cost_type"
   FROM "even_allocated";


ALTER VIEW "public"."allocation_output" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."allocation_results" (
    "id" integer NOT NULL,
    "resource_name" "text",
    "application_name" "text",
    "allocated_cost" numeric,
    "status" "text",
    "created_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."allocation_results" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."allocation_results_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."allocation_results_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."allocation_results_id_seq" OWNED BY "public"."allocation_results"."id";



CREATE OR REPLACE VIEW "public"."allocation_validation" AS
 SELECT "service_name",
    "sum"("percentage") AS "total_percent",
        CASE
            WHEN ("sum"("percentage") = (100)::numeric) THEN 'VALID'::"text"
            ELSE 'INVALID'::"text"
        END AS "status"
   FROM "public"."allocation_rules"
  GROUP BY "service_name";


ALTER VIEW "public"."allocation_validation" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."anomalies" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "service" "text",
    "detected_value" numeric,
    "expected_value" numeric,
    "severity" "text",
    "created_at" timestamp without time zone DEFAULT "now"(),
    "cloud_provider" "text",
    "current_cost" numeric,
    "reason" "text",
    "score" numeric,
    "service_name" "text",
    "anomaly_type" "text",
    "detected_signals" "jsonb",
    "confidence" integer
);


ALTER TABLE "public"."anomalies" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."app_cost_summary" (
    "id" bigint NOT NULL,
    "client_id" "uuid" NOT NULL,
    "app_name" "text" NOT NULL,
    "period_month" "text",
    "total_cost" numeric,
    "compute_cost" numeric DEFAULT 0,
    "database_cost" numeric DEFAULT 0,
    "storage_cost" numeric DEFAULT 0,
    "network_cost" numeric DEFAULT 0,
    "potential_savings" numeric DEFAULT 0,
    "calculated_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."app_cost_summary" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."app_cost_summary_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."app_cost_summary_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."app_cost_summary_id_seq" OWNED BY "public"."app_cost_summary"."id";



CREATE TABLE IF NOT EXISTS "public"."app_mapping" (
    "application_id" "uuid",
    "team" "text",
    "environment" "text",
    "business_unit" "text"
);


ALTER TABLE "public"."app_mapping" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."application_databases" (
    "id" bigint NOT NULL,
    "client_id" "uuid" NOT NULL,
    "app_name" "text" NOT NULL,
    "database_name" "text" NOT NULL,
    "database_type" "text" DEFAULT 'postgresql'::"text",
    "instance_size" "text",
    "region" "text",
    "current_cost" numeric DEFAULT 0,
    "utilization_percent" numeric DEFAULT 0,
    "created_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."application_databases" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."application_databases_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."application_databases_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."application_databases_id_seq" OWNED BY "public"."application_databases"."id";



CREATE TABLE IF NOT EXISTS "public"."audit_logs" (
    "id" integer NOT NULL,
    "user_email" character varying,
    "action" character varying,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."audit_logs" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."audit_logs_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."audit_logs_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."audit_logs_id_seq" OWNED BY "public"."audit_logs"."id";



CREATE TABLE IF NOT EXISTS "public"."budget" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "service_name" "text",
    "monthly_budget" numeric
);


ALTER TABLE "public"."budget" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."budget_vs_actual" AS
 SELECT "c"."service_name",
    "sum"("c"."total_cost") AS "actual_cost",
    "b"."monthly_budget",
    ("sum"("c"."total_cost") - "b"."monthly_budget") AS "variance"
   FROM ("public"."cost_usage_tracking" "c"
     LEFT JOIN "public"."budget" "b" ON (("c"."service_name" = "b"."service_name")))
  GROUP BY "c"."service_name", "b"."monthly_budget";


ALTER VIEW "public"."budget_vs_actual" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_cost_classification" AS
 SELECT "service_name",
    "sum"("total_cost") AS "total_cost"
   FROM "public"."cost_usage_tracking"
  GROUP BY "service_name";


ALTER VIEW "public"."mart_cost_classification" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_dynamic_allocation" AS
 SELECT "m"."service_name",
    "a"."app_name",
    (("m"."total_cost" * "ar"."percentage") / (100)::numeric) AS "allocated_cost"
   FROM (("public"."mart_cost_classification" "m"
     JOIN "public"."allocation_rules" "ar" ON (("m"."service_name" = "ar"."service_name")))
     JOIN "public"."applications" "a" ON (("ar"."application_id" = "a"."id")));


ALTER VIEW "public"."mart_dynamic_allocation" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."unallocated_cost" AS
 SELECT "m"."service_name",
    "m"."total_cost"
   FROM ("public"."mart_cost_classification" "m"
     LEFT JOIN "public"."allocation_rules" "ar" ON (("m"."service_name" = "ar"."service_name")))
  WHERE ("ar"."service_name" IS NULL);


ALTER VIEW "public"."unallocated_cost" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."final_cost_view" AS
 SELECT "d"."service_name",
    "d"."app_name",
    "d"."allocated_cost" AS "cost",
    'allocated'::"text" AS "cost_type"
   FROM "public"."mart_dynamic_allocation" "d"
UNION ALL
 SELECT "u"."service_name",
    'unallocated'::"text" AS "app_name",
    "u"."total_cost" AS "cost",
    'unallocated'::"text" AS "cost_type"
   FROM "public"."unallocated_cost" "u";


ALTER VIEW "public"."final_cost_view" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."client_cost_view" AS
 SELECT "c"."client_id",
    "f"."service_name",
    "f"."app_name",
    "f"."cost",
    "f"."cost_type"
   FROM ("public"."final_cost_view" "f"
     LEFT JOIN "public"."applications" "c" ON (("f"."app_name" = "c"."app_name")));


ALTER VIEW "public"."client_cost_view" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cloud_accounts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid",
    "cloud_provider" "text",
    "account_name" "text",
    "region" "text",
    "created_at" timestamp without time zone DEFAULT "now"(),
    "org_id" "uuid"
);


ALTER TABLE "public"."cloud_accounts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."usage_metrics" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid",
    "resource" "text",
    "service" "text",
    "utilization" numeric,
    "status" "text",
    "recorded_at" timestamp without time zone DEFAULT "now"(),
    "application_id" "uuid",
    "account_id" "uuid"
);


ALTER TABLE "public"."usage_metrics" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."client_summary" AS
 SELECT "ca"."org_id",
    "sum"("u"."utilization") AS "total_cost",
    0 AS "total_savings",
    0 AS "roi"
   FROM ("public"."cloud_accounts" "ca"
     LEFT JOIN "public"."usage_metrics" "u" ON (("ca"."id" = "u"."account_id")))
  GROUP BY "ca"."org_id";


ALTER VIEW "public"."client_summary" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clients" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" "text",
    "industry" "text",
    "region" "text",
    "created_at" timestamp without time zone DEFAULT "now"(),
    "org_id" "uuid"
);


ALTER TABLE "public"."clients" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cloud_cost_history" (
    "id" bigint NOT NULL,
    "cloud" "text",
    "account_name" "text",
    "service_name" "text",
    "cost" numeric,
    "usage_date" "date",
    "created_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."cloud_cost_history" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."cloud_cost_history_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."cloud_cost_history_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."cloud_cost_history_id_seq" OWNED BY "public"."cloud_cost_history"."id";



CREATE OR REPLACE VIEW "public"."cost_anomaly_view" AS
 SELECT "u"."service" AS "service_name",
    "u"."recorded_at" AS "usage_date",
    "u"."utilization" AS "cost",
    "lag"("u"."utilization") OVER (PARTITION BY "u"."account_id", "u"."service" ORDER BY "u"."recorded_at") AS "prev_cost",
        CASE
            WHEN ("u"."utilization" > (1.5 * "lag"("u"."utilization") OVER (PARTITION BY "u"."account_id", "u"."service" ORDER BY "u"."recorded_at"))) THEN 'SPIKE'::"text"
            ELSE 'NORMAL'::"text"
        END AS "status",
    "u"."account_id",
    "ca"."org_id"
   FROM ("public"."usage_metrics" "u"
     JOIN "public"."cloud_accounts" "ca" ON (("u"."account_id" = "ca"."id")));


ALTER VIEW "public"."cost_anomaly_view" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."cost_anomaly_org_view" AS
 SELECT "service_name",
    "usage_date",
    "cost",
    "prev_cost",
    "status",
    "account_id",
    "org_id"
   FROM "public"."cost_anomaly_view" "cav";


ALTER VIEW "public"."cost_anomaly_org_view" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."cost_recommendations" AS
 SELECT "service_name",
    'HIGH'::"text" AS "priority",
    'COST_SPIKE'::"text" AS "issue_type",
    'Reduce usage or check scaling policies'::"text" AS "recommendation",
    ("sum"("total_cost") * 0.2) AS "potential_savings"
   FROM "public"."cost_usage_tracking"
  GROUP BY "service_name";


ALTER VIEW "public"."cost_recommendations" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."cost_trend" AS
 SELECT "application_id",
    "date_trunc"('month'::"text", "created_date") AS "month",
    "sum"("total_cost") AS "total_cost"
   FROM "public"."cost_usage_tracking"
  GROUP BY "application_id", ("date_trunc"('month'::"text", "created_date"));


ALTER VIEW "public"."cost_trend" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."cost_trend_view" AS
 SELECT "usage_date",
    "service_name",
    "sum"("total_cost") AS "daily_cost"
   FROM "public"."cost_usage_tracking"
  GROUP BY "usage_date", "service_name"
  ORDER BY "usage_date";


ALTER VIEW "public"."cost_trend_view" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."costs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "org_id" "text",
    "cloud" "text",
    "service_name" "text",
    "total_cost" numeric,
    "created_at" timestamp without time zone DEFAULT "now"(),
    "usage_date" "date",
    "last_updated" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."costs" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_total_cost" AS
 SELECT "org_id",
    "sum"("total_cost") AS "total_cost"
   FROM "public"."costs"
  GROUP BY "org_id";


ALTER VIEW "public"."mart_total_cost" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."cto_dashboard_view" AS
 SELECT "org_id",
    "total_cost"
   FROM "public"."mart_total_cost";


ALTER VIEW "public"."cto_dashboard_view" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."cto_kpi_view" AS
 SELECT "sum"("total_cost") AS "total_cost"
   FROM "public"."cost_usage_tracking";


ALTER VIEW "public"."cto_kpi_view" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."unified_cloud_costs" (
    "id" bigint NOT NULL,
    "cloud" character varying(20),
    "account_name" "text",
    "service_name" "text",
    "region" "text",
    "resource_id" "text",
    "usage_date" "date",
    "usage_quantity" numeric,
    "cost" numeric,
    "currency" character varying(10),
    "environment" "text",
    "application" "text",
    "tags" "jsonb",
    "created_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."unified_cloud_costs" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."daily_cloud_summary" AS
 SELECT "usage_date",
    "cloud",
    "sum"("cost") AS "total_cost"
   FROM "public"."unified_cloud_costs"
  GROUP BY "usage_date", "cloud"
  ORDER BY "usage_date" DESC;


ALTER VIEW "public"."daily_cloud_summary" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."db_performance_metrics" (
    "id" bigint NOT NULL,
    "client_id" "uuid" NOT NULL,
    "db_name" "text" NOT NULL,
    "metric_type" "text",
    "metric_value" numeric,
    "threshold_value" numeric,
    "is_anomaly" boolean DEFAULT false,
    "measured_at" timestamp without time zone,
    "created_at" timestamp without time zone DEFAULT "now"(),
    CONSTRAINT "db_performance_metrics_metric_type_check" CHECK (("metric_type" = ANY (ARRAY['cpu_usage'::"text", 'memory_usage'::"text", 'query_count'::"text", 'slow_queries'::"text", 'connections'::"text", 'iops'::"text"])))
);


ALTER TABLE "public"."db_performance_metrics" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."db_performance_metrics_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."db_performance_metrics_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."db_performance_metrics_id_seq" OWNED BY "public"."db_performance_metrics"."id";



CREATE TABLE IF NOT EXISTS "public"."license_cost" (
    "id" integer NOT NULL,
    "date" "date",
    "software_name" "text",
    "application_name" "text",
    "cost" numeric,
    "licenses_purchased" integer,
    "licenses_used" integer
);


ALTER TABLE "public"."license_cost" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."license_cost_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."license_cost_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."license_cost_id_seq" OWNED BY "public"."license_cost"."id";



CREATE TABLE IF NOT EXISTS "public"."managed_services_cost" (
    "id" integer NOT NULL,
    "date" "date",
    "service_name" "text",
    "application_name" "text",
    "cost" numeric,
    "provider" "text"
);


ALTER TABLE "public"."managed_services_cost" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."managed_services_cost_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."managed_services_cost_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."managed_services_cost_id_seq" OWNED BY "public"."managed_services_cost"."id";



CREATE TABLE IF NOT EXISTS "public"."resource_mapping" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "resource_name" "text" NOT NULL,
    "service_name" "text" NOT NULL,
    "environment" "text",
    "client_id" "uuid",
    "created_at" timestamp without time zone DEFAULT "now"(),
    "resource" "text",
    "application_id" "uuid",
    "org_id" "uuid",
    "team" "text",
    "business_unit" "text"
);


ALTER TABLE "public"."resource_mapping" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_ai_recommendations" AS
 WITH "service_cost" AS (
         SELECT "r"."service_name",
            "sum"("c"."total_cost") AS "total_cost"
           FROM ("public"."cost_usage_tracking" "c"
             LEFT JOIN "public"."resource_mapping" "r" ON (("c"."application_id" = "r"."application_id")))
          GROUP BY "r"."service_name"
        ), "total" AS (
         SELECT "sum"("service_cost"."total_cost") AS "overall_cost"
           FROM "service_cost"
        )
 SELECT COALESCE("s"."service_name", 'Unknown'::"text") AS "service_name",
        CASE
            WHEN ("s"."total_cost" > ("t"."overall_cost" * 0.5)) THEN 'High cost concentration'::"text"
            WHEN ("s"."total_cost" > ("t"."overall_cost" * 0.3)) THEN 'Moderate cost concentration'::"text"
            ELSE 'Normal'::"text"
        END AS "issue",
        CASE
            WHEN ("s"."service_name" = 'EC2'::"text") THEN 'Consider rightsizing or Reserved Instances'::"text"
            WHEN ("s"."service_name" = 'S3'::"text") THEN 'Move infrequent data to Glacier'::"text"
            WHEN ("s"."service_name" = 'RDS'::"text") THEN 'Check for idle DB instances'::"text"
            ELSE 'General cost optimization review'::"text"
        END AS "recommendation",
    "round"(("s"."total_cost" * 0.3), 2) AS "potential_savings",
        CASE
            WHEN ("s"."total_cost" > ("t"."overall_cost" * 0.5)) THEN 'HIGH'::"text"
            WHEN ("s"."total_cost" > ("t"."overall_cost" * 0.3)) THEN 'MEDIUM'::"text"
            ELSE 'LOW'::"text"
        END AS "priority"
   FROM ("service_cost" "s"
     CROSS JOIN "total" "t")
  ORDER BY ("round"(("s"."total_cost" * 0.3), 2)) DESC;


ALTER VIEW "public"."mart_ai_recommendations" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_allocation_expanded" AS
 SELECT "service_name",
    "application_id",
    "percentage"
   FROM "public"."allocation_rules";


ALTER VIEW "public"."mart_allocation_expanded" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."usage_trend" AS
 SELECT "application_id",
    "date_trunc"('month'::"text", "recorded_at") AS "month",
    "sum"("utilization") AS "total_usage"
   FROM "public"."usage_metrics" "u"
  WHERE ("application_id" IS NOT NULL)
  GROUP BY "application_id", ("date_trunc"('month'::"text", "recorded_at"));


ALTER VIEW "public"."usage_trend" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_app_kpi" AS
 SELECT "am"."application_id",
    "am"."team",
    "am"."environment",
    "am"."business_unit",
    "date_trunc"('month'::"text", "c"."created_date") AS "month",
    "sum"("c"."total_cost") AS "total_cost",
    COALESCE("sum"("u"."total_usage"), (0)::numeric) AS "total_usage",
        CASE
            WHEN (COALESCE("sum"("u"."total_usage"), (0)::numeric) > (0)::numeric) THEN ("sum"("c"."total_cost") / "sum"("u"."total_usage"))
            ELSE (0)::numeric
        END AS "cost_per_unit"
   FROM (("public"."cost_usage_tracking" "c"
     LEFT JOIN "public"."app_mapping" "am" ON (("c"."application_id" = "am"."application_id")))
     LEFT JOIN "public"."usage_trend" "u" ON (("am"."application_id" = "u"."application_id")))
  GROUP BY "am"."application_id", "am"."team", "am"."environment", "am"."business_unit", ("date_trunc"('month'::"text", "c"."created_date"));


ALTER VIEW "public"."mart_app_kpi" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_application_cost" AS
 SELECT COALESCE("a"."app_name", 'Unknown'::"text") AS "app_name",
    COALESCE("a"."environment", 'Unknown'::"text") AS "environment",
    COALESCE("r"."business_unit", 'Unknown'::"text") AS "business_unit",
    COALESCE("r"."team", 'Unknown'::"text") AS "team",
    "sum"("c"."total_cost") AS "total_cost"
   FROM (("public"."cost_usage_tracking" "c"
     LEFT JOIN "public"."applications" "a" ON (("c"."application_id" = "a"."id")))
     LEFT JOIN "public"."resource_mapping" "r" ON (("c"."application_id" = "r"."application_id")))
  GROUP BY "a"."app_name", "a"."environment", "r"."business_unit", "r"."team"
  ORDER BY ("sum"("c"."total_cost")) DESC;


ALTER VIEW "public"."mart_application_cost" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_application_costs" AS
 SELECT "app"."name" AS "application",
    "sum"("cli"."allocated_cost") AS "total_cost"
   FROM ("ingest"."cost_line_items" "cli"
     JOIN "core"."applications" "app" ON (("cli"."mapped_application_id" = "app"."id")))
  GROUP BY "app"."name";


ALTER VIEW "public"."mart_application_costs" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_application_summary" AS
 SELECT
        CASE
            WHEN ("cli"."mapped_application_id" IS NULL) THEN 'Unallocated'::"text"
            ELSE "app"."name"
        END AS "application",
    "sum"("cli"."allocated_cost") AS "total_cost"
   FROM ("ingest"."cost_line_items" "cli"
     LEFT JOIN "core"."applications" "app" ON (("cli"."mapped_application_id" = "app"."id")))
  GROUP BY
        CASE
            WHEN ("cli"."mapped_application_id" IS NULL) THEN 'Unallocated'::"text"
            ELSE "app"."name"
        END;


ALTER VIEW "public"."mart_application_summary" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_budget_vs_actual" AS
 WITH "daily_cost" AS (
         SELECT ("cost_usage_tracking"."created_date")::"date" AS "date",
            "sum"("cost_usage_tracking"."total_cost") AS "actual_cost"
           FROM "public"."cost_usage_tracking"
          GROUP BY (("cost_usage_tracking"."created_date")::"date")
        ), "budget" AS (
         SELECT 4000 AS "daily_budget"
        )
 SELECT "d"."date",
    "d"."actual_cost",
    "b"."daily_budget" AS "budget",
    ("d"."actual_cost" - ("b"."daily_budget")::numeric) AS "variance",
        CASE
            WHEN ("d"."actual_cost" > ("b"."daily_budget")::numeric) THEN 'OVER_BUDGET'::"text"
            WHEN ("d"."actual_cost" < ("b"."daily_budget")::numeric) THEN 'UNDER_BUDGET'::"text"
            ELSE 'ON_BUDGET'::"text"
        END AS "status"
   FROM ("daily_cost" "d"
     CROSS JOIN "budget" "b")
  ORDER BY "d"."date";


ALTER VIEW "public"."mart_budget_vs_actual" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_client_cost" AS
 SELECT "a"."client_id",
    "cl"."name" AS "client_name",
    "sum"("c"."total_cost") AS "total_cost"
   FROM (("public"."cost_usage_tracking" "c"
     LEFT JOIN "public"."applications" "a" ON (("c"."application_id" = "a"."id")))
     LEFT JOIN "public"."clients" "cl" ON (("a"."client_id" = "cl"."id")))
  GROUP BY "a"."client_id", "cl"."name"
  ORDER BY ("sum"("c"."total_cost")) DESC;


ALTER VIEW "public"."mart_client_cost" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_cost_forecast" AS
 WITH "base" AS (
         SELECT ("cost_usage_tracking"."created_date")::"date" AS "date",
            "sum"("cost_usage_tracking"."total_cost") AS "cost"
           FROM "public"."cost_usage_tracking"
          GROUP BY (("cost_usage_tracking"."created_date")::"date")
        ), "trend" AS (
         SELECT "base"."date",
            "base"."cost",
            "lag"("base"."cost") OVER (ORDER BY "base"."date") AS "prev_cost"
           FROM "base"
        ), "growth" AS (
         SELECT "trend"."date",
            "trend"."cost",
                CASE
                    WHEN ("trend"."prev_cost" IS NULL) THEN (0)::numeric
                    ELSE ("trend"."cost" - "trend"."prev_cost")
                END AS "daily_growth"
           FROM "trend"
        ), "avg_growth" AS (
         SELECT "avg"("growth"."daily_growth") AS "avg_growth"
           FROM "growth"
        ), "latest" AS (
         SELECT "max"("base"."date") AS "last_date",
            "max"("base"."cost") AS "last_cost"
           FROM "base"
        ), "forecast" AS (
         SELECT "base"."date",
            "base"."cost" AS "actual_cost",
            "base"."cost" AS "forecast_cost"
           FROM "base"
        UNION ALL
         SELECT (("l"."last_date" + (("i"."i" || ' day'::"text"))::interval))::"date" AS "date",
            NULL::numeric AS "actual_cost",
            ("l"."last_cost" + ("a"."avg_growth" * ("i"."i")::numeric)) AS "forecast_cost"
           FROM (("latest" "l"
             CROSS JOIN "avg_growth" "a")
             CROSS JOIN "generate_series"(1, 7) "i"("i"))
        )
 SELECT "date",
    "actual_cost",
    "forecast_cost"
   FROM "forecast"
  ORDER BY "date";


ALTER VIEW "public"."mart_cost_forecast" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_cost_trend" AS
 SELECT "usage_date",
    "org_id",
    "service_name",
    "sum"("total_cost") AS "total_cost"
   FROM "public"."cost_usage_tracking"
  GROUP BY "usage_date", "org_id", "service_name";


ALTER VIEW "public"."mart_cost_trend" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."mart_cto_dashboard" (
    "date" "date",
    "total_cost" numeric,
    "records" integer,
    "client_id" "uuid"
);


ALTER TABLE "public"."mart_cto_dashboard" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_kpi_dashboard" AS
 SELECT "date",
    "total_cost",
    "records"
   FROM "public"."mart_cto_dashboard";


ALTER VIEW "public"."mart_kpi_dashboard" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_kpi_summary" AS
 SELECT "app"."name",
    "sum"("cli"."allocated_cost") AS "total_cost",
    ("sum"("cli"."allocated_cost") / (NULLIF("u"."active_users", 0))::numeric) AS "cost_per_user"
   FROM (("ingest"."cost_line_items" "cli"
     JOIN "core"."applications" "app" ON (("cli"."mapped_application_id" = "app"."id")))
     LEFT JOIN "usage"."user_metrics" "u" ON (("app"."id" = "u"."application_id")))
  GROUP BY "app"."name", "u"."active_users";


ALTER VIEW "public"."mart_kpi_summary" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_mapping_coverage" AS
 SELECT "count"(*) AS "total_records",
    "count"("mapped_application_id") AS "mapped_records",
    ("count"(*) - "count"("mapped_application_id")) AS "unmapped_records",
    "round"(((("count"("mapped_application_id"))::numeric / ("count"(*))::numeric) * (100)::numeric), 2) AS "mapping_percentage"
   FROM "ingest"."cost_line_items";


ALTER VIEW "public"."mart_mapping_coverage" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."recommendations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "org_id" "uuid",
    "service" "text",
    "description" "text",
    "estimated_savings" numeric,
    "status" "text" DEFAULT 'pending'::"text",
    "created_at" timestamp without time zone DEFAULT "now"(),
    "client_id" "uuid",
    "type" "text",
    "message" "text",
    "impact" "text",
    "resolved_at" timestamp without time zone,
    "completed_at" timestamp without time zone
);


ALTER TABLE "public"."recommendations" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_recommendations" AS
 SELECT "id",
    "org_id",
    "service",
    "description",
    "estimated_savings",
    "status",
    "created_at",
    "client_id"
   FROM "public"."recommendations";


ALTER VIEW "public"."mart_recommendations" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_savings" AS
 SELECT "created_date",
    "sum"("total_cost") AS "total_cost",
    ("sum"("total_cost") * 0.8) AS "optimized_cost",
    ("sum"("total_cost") - ("sum"("total_cost") * 0.8)) AS "savings"
   FROM "public"."cost_usage_tracking"
  GROUP BY "created_date"
  ORDER BY "created_date";


ALTER VIEW "public"."mart_savings" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_service_cost" AS
 SELECT "cloud",
    "service_name",
    "sum"("total_cost") AS "total_cost"
   FROM "public"."costs"
  GROUP BY "cloud", "service_name";


ALTER VIEW "public"."mart_service_cost" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_top_services" AS
 SELECT COALESCE("r"."service_name", 'Unknown'::"text") AS "service_name",
    "sum"("c"."total_cost") AS "cost"
   FROM ("public"."cost_usage_tracking" "c"
     LEFT JOIN "public"."resource_mapping" "r" ON (("c"."application_id" = "r"."application_id")))
  GROUP BY "r"."service_name"
  ORDER BY ("sum"("c"."total_cost")) DESC
 LIMIT 5;


ALTER VIEW "public"."mart_top_services" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_true_cost_v2" AS
 SELECT "app_name",
    "sum"("allocated_cost") AS "total_cost"
   FROM "public"."mart_dynamic_allocation"
  GROUP BY "app_name";


ALTER VIEW "public"."mart_true_cost_v2" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_unallocated" AS
 SELECT "count"(*) AS "records",
    "sum"("cost") AS "total_cost"
   FROM "ingest"."cost_line_items"
  WHERE ("mapped_application_id" IS NULL);


ALTER VIEW "public"."mart_unallocated" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."mart_unallocated_cost" AS
 SELECT "count"(*) AS "records",
    "sum"("cost") AS "total_cost"
   FROM "ingest"."cost_line_items"
  WHERE ("mapped_application_id" IS NULL);


ALTER VIEW "public"."mart_unallocated_cost" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."metric_catalog" (
    "metric_name" "text" NOT NULL,
    "description" "text"
);


ALTER TABLE "public"."metric_catalog" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."metric_snapshots" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "metric_name" "text",
    "application_id" "text",
    "value" numeric,
    "snapshot_time" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."metric_snapshots" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."optimization_results" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "application_id" "uuid",
    "baseline_cost" numeric,
    "optimized_cost" numeric,
    "created_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."optimization_results" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."organizations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" "text" NOT NULL,
    "created_at" timestamp without time zone DEFAULT "now"(),
    "status" "text" DEFAULT 'active'::"text"
);


ALTER TABLE "public"."organizations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."realized_savings" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "recommendation_id" "uuid",
    "org_id" "uuid",
    "amount" numeric,
    "applied_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."realized_savings" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."roi_summary" AS
 SELECT "r"."org_id",
    COALESCE("sum"("rs"."amount"), (0)::numeric) AS "realized_savings",
    COALESCE("sum"("r"."estimated_savings"), (0)::numeric) AS "total_possible_savings",
        CASE
            WHEN ("sum"("r"."estimated_savings") = (0)::numeric) THEN (0)::numeric
            ELSE ((COALESCE("sum"("rs"."amount"), (0)::numeric) / "sum"("r"."estimated_savings")) * (100)::numeric)
        END AS "roi"
   FROM ("public"."recommendations" "r"
     LEFT JOIN "public"."realized_savings" "rs" ON (("r"."id" = "rs"."recommendation_id")))
  GROUP BY "r"."org_id";


ALTER VIEW "public"."roi_summary" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."roles" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "role_name" "text"
);


ALTER TABLE "public"."roles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."saas_cost" (
    "id" integer NOT NULL,
    "date" "date",
    "vendor_name" "text",
    "application_name" "text",
    "cost" numeric,
    "user_count" integer
);


ALTER TABLE "public"."saas_cost" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."saas_cost_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."saas_cost_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."saas_cost_id_seq" OWNED BY "public"."saas_cost"."id";



CREATE OR REPLACE VIEW "public"."savings_pipeline" AS
 SELECT "org_id",
    "sum"("estimated_savings") AS "pipeline_savings"
   FROM "public"."recommendations"
  WHERE ("status" = 'pending'::"text")
  GROUP BY "org_id";


ALTER VIEW "public"."savings_pipeline" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."savings_summary" AS
 SELECT "org_id",
    "sum"("amount") AS "total_realized_savings"
   FROM "public"."realized_savings"
  GROUP BY "org_id";


ALTER VIEW "public"."savings_summary" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."service_cost_summary" AS
 SELECT "cloud",
    "service_name",
    "sum"("cost") AS "total_cost"
   FROM "public"."unified_cloud_costs"
  GROUP BY "cloud", "service_name"
  ORDER BY ("sum"("cost")) DESC;


ALTER VIEW "public"."service_cost_summary" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."ui_tiles" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "role" "text",
    "title" "text",
    "icon" "text",
    "description" "text",
    "page_key" "text",
    "is_active" boolean DEFAULT true,
    "display_order" integer
);


ALTER TABLE "public"."ui_tiles" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."unallocated_cost_advanced" AS
 SELECT "m"."service_name",
    "m"."total_cost",
    COALESCE("sum"("ar"."percentage"), (0)::numeric) AS "allocated_percent",
    ((100)::numeric - COALESCE("sum"("ar"."percentage"), (0)::numeric)) AS "unallocated_percent"
   FROM ("public"."mart_cost_classification" "m"
     LEFT JOIN "public"."allocation_rules" "ar" ON (("m"."service_name" = "ar"."service_name")))
  GROUP BY "m"."service_name", "m"."total_cost"
 HAVING (COALESCE("sum"("ar"."percentage"), (0)::numeric) < (100)::numeric);


ALTER VIEW "public"."unallocated_cost_advanced" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."unified_cloud_costs_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."unified_cloud_costs_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."unified_cloud_costs_id_seq" OWNED BY "public"."unified_cloud_costs"."id";



CREATE OR REPLACE VIEW "public"."unified_cost_usage" AS
 SELECT "c"."service_name",
    "c"."usage_date",
    "c"."cost" AS "total_cost",
    "u"."utilization"
   FROM ("public"."cost_anomaly_view" "c"
     LEFT JOIN "public"."usage_metrics" "u" ON ((("c"."service_name" = "u"."service") AND ("c"."usage_date" = "u"."recorded_at"))));


ALTER VIEW "public"."unified_cost_usage" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."user_roles" (
    "id" "uuid" DEFAULT "gen_random_uuid"(),
    "email" "text",
    "role" "text",
    "client_id" "uuid"
);


ALTER TABLE "public"."user_roles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."users" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "email" "text" NOT NULL,
    "name" "text",
    "role" "text",
    "org_id" "uuid",
    "created_at" timestamp without time zone DEFAULT "now"()
);


ALTER TABLE "public"."users" OWNER TO "postgres";


ALTER TABLE ONLY "public"."allocation_results" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."allocation_results_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."app_cost_summary" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."app_cost_summary_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."application_databases" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."application_databases_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."audit_logs" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."audit_logs_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."cloud_cost_history" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."cloud_cost_history_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."db_performance_metrics" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."db_performance_metrics_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."license_cost" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."license_cost_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."managed_services_cost" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."managed_services_cost_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."saas_cost" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."saas_cost_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."unified_cloud_costs" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."unified_cloud_costs_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."actions_log"
    ADD CONSTRAINT "actions_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."ai_audit_logs"
    ADD CONSTRAINT "ai_audit_logs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."allocation_results"
    ADD CONSTRAINT "allocation_results_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."allocation_rules"
    ADD CONSTRAINT "allocation_rules_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."anomalies"
    ADD CONSTRAINT "anomalies_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."app_cost_summary"
    ADD CONSTRAINT "app_cost_summary_client_id_app_name_period_month_key" UNIQUE ("client_id", "app_name", "period_month");



ALTER TABLE ONLY "public"."app_cost_summary"
    ADD CONSTRAINT "app_cost_summary_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."application_databases"
    ADD CONSTRAINT "application_databases_client_id_database_name_key" UNIQUE ("client_id", "database_name");



ALTER TABLE ONLY "public"."application_databases"
    ADD CONSTRAINT "application_databases_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."applications"
    ADD CONSTRAINT "applications_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."audit_logs"
    ADD CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."budget"
    ADD CONSTRAINT "budget_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."clients"
    ADD CONSTRAINT "clients_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cloud_accounts"
    ADD CONSTRAINT "cloud_accounts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cloud_cost_history"
    ADD CONSTRAINT "cloud_cost_history_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cost_usage_tracking"
    ADD CONSTRAINT "cost_usage_tracking_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."costs"
    ADD CONSTRAINT "costs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."db_performance_metrics"
    ADD CONSTRAINT "db_performance_metrics_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."license_cost"
    ADD CONSTRAINT "license_cost_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."managed_services_cost"
    ADD CONSTRAINT "managed_services_cost_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."metric_catalog"
    ADD CONSTRAINT "metric_catalog_pkey" PRIMARY KEY ("metric_name");



ALTER TABLE ONLY "public"."metric_snapshots"
    ADD CONSTRAINT "metric_snapshots_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."optimization_results"
    ADD CONSTRAINT "optimization_results_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."organizations"
    ADD CONSTRAINT "organizations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."realized_savings"
    ADD CONSTRAINT "realized_savings_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."recommendations"
    ADD CONSTRAINT "recommendations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."resource_mapping"
    ADD CONSTRAINT "resource_mapping_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."roles"
    ADD CONSTRAINT "roles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."roles"
    ADD CONSTRAINT "roles_role_name_key" UNIQUE ("role_name");



ALTER TABLE ONLY "public"."saas_cost"
    ADD CONSTRAINT "saas_cost_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."ui_tiles"
    ADD CONSTRAINT "ui_tiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."unified_cloud_costs"
    ADD CONSTRAINT "unified_cloud_costs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."unified_cloud_costs"
    ADD CONSTRAINT "unique_cloud_cost_entry" UNIQUE ("cloud", "account_name", "service_name", "usage_date");



ALTER TABLE ONLY "public"."unified_cloud_costs"
    ADD CONSTRAINT "unique_cloud_service" UNIQUE ("cloud", "service_name");



ALTER TABLE ONLY "public"."costs"
    ADD CONSTRAINT "unique_cost_entry" UNIQUE ("org_id", "cloud", "service_name");



ALTER TABLE ONLY "public"."usage_metrics"
    ADD CONSTRAINT "usage_metrics_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_email_key" UNIQUE ("email");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");



CREATE INDEX "idx_app_cost_summary" ON "public"."app_cost_summary" USING "btree" ("app_name", "period_month");



CREATE INDEX "idx_db_metrics" ON "public"."db_performance_metrics" USING "btree" ("db_name", "measured_at");



CREATE UNIQUE INDEX "unique_recommendation_rule" ON "public"."recommendations" USING "btree" ("org_id", "message");



ALTER TABLE ONLY "public"."allocation_rules"
    ADD CONSTRAINT "allocation_rules_org_id_fkey" FOREIGN KEY ("org_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."app_cost_summary"
    ADD CONSTRAINT "app_cost_summary_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."application_databases"
    ADD CONSTRAINT "application_databases_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."applications"
    ADD CONSTRAINT "applications_org_id_fkey" FOREIGN KEY ("org_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."clients"
    ADD CONSTRAINT "clients_org_id_fkey" FOREIGN KEY ("org_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."cloud_accounts"
    ADD CONSTRAINT "cloud_accounts_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."cloud_accounts"
    ADD CONSTRAINT "cloud_accounts_org_id_fkey" FOREIGN KEY ("org_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."cost_usage_tracking"
    ADD CONSTRAINT "cost_usage_tracking_org_id_fkey" FOREIGN KEY ("org_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."db_performance_metrics"
    ADD CONSTRAINT "db_performance_metrics_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."user_roles"
    ADD CONSTRAINT "fk_client" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."realized_savings"
    ADD CONSTRAINT "realized_savings_recommendation_id_fkey" FOREIGN KEY ("recommendation_id") REFERENCES "public"."recommendations"("id");



ALTER TABLE ONLY "public"."recommendations"
    ADD CONSTRAINT "recommendations_org_id_fkey" FOREIGN KEY ("org_id") REFERENCES "public"."organizations"("id");



ALTER TABLE ONLY "public"."resource_mapping"
    ADD CONSTRAINT "resource_mapping_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_org_id_fkey" FOREIGN KEY ("org_id") REFERENCES "public"."organizations"("id");



CREATE POLICY "Allow all read" ON "public"."organizations" FOR SELECT USING (true);



CREATE POLICY "Allow insert for all" ON "public"."recommendations" FOR INSERT TO "anon" WITH CHECK (true);



CREATE POLICY "Allow insert recommendations" ON "public"."recommendations" FOR INSERT WITH CHECK (true);



CREATE POLICY "Allow read for now" ON "public"."clients" FOR SELECT USING (true);



CREATE POLICY "Allow read for now" ON "public"."usage_metrics" FOR SELECT USING (true);



CREATE POLICY "Allow read recommendations" ON "public"."recommendations" FOR SELECT USING (true);



CREATE POLICY "Users can see only their org data" ON "public"."recommendations" FOR SELECT USING (("org_id" = "auth"."uid"()));



ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cloud_accounts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cloud_cost_history" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."organizations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."recommendations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."unified_cloud_costs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."usage_metrics" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON FUNCTION "public"."accept_recommendation"("rec_id" "uuid", "user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."accept_recommendation"("rec_id" "uuid", "user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."accept_recommendation"("rec_id" "uuid", "user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."apply_recommendation"("rec_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."apply_recommendation"("rec_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."apply_recommendation"("rec_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."apply_recommendation"("rec_id" "uuid", "user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."apply_recommendation"("rec_id" "uuid", "user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."apply_recommendation"("rec_id" "uuid", "user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."run_allocation_job"() TO "anon";
GRANT ALL ON FUNCTION "public"."run_allocation_job"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."run_allocation_job"() TO "service_role";



GRANT ALL ON FUNCTION "public"."run_full_pipeline"() TO "anon";
GRANT ALL ON FUNCTION "public"."run_full_pipeline"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."run_full_pipeline"() TO "service_role";



GRANT ALL ON FUNCTION "public"."run_mapping_job"() TO "anon";
GRANT ALL ON FUNCTION "public"."run_mapping_job"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."run_mapping_job"() TO "service_role";



GRANT ALL ON FUNCTION "public"."run_metrics_job"() TO "anon";
GRANT ALL ON FUNCTION "public"."run_metrics_job"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."run_metrics_job"() TO "service_role";



GRANT ALL ON FUNCTION "public"."run_recommendation_job"() TO "anon";
GRANT ALL ON FUNCTION "public"."run_recommendation_job"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."run_recommendation_job"() TO "service_role";



GRANT ALL ON TABLE "public"."actions_log" TO "anon";
GRANT ALL ON TABLE "public"."actions_log" TO "authenticated";
GRANT ALL ON TABLE "public"."actions_log" TO "service_role";



GRANT ALL ON TABLE "public"."ai_audit_logs" TO "anon";
GRANT ALL ON TABLE "public"."ai_audit_logs" TO "authenticated";
GRANT ALL ON TABLE "public"."ai_audit_logs" TO "service_role";



GRANT ALL ON TABLE "public"."allocation_rules" TO "anon";
GRANT ALL ON TABLE "public"."allocation_rules" TO "authenticated";
GRANT ALL ON TABLE "public"."allocation_rules" TO "service_role";



GRANT ALL ON TABLE "public"."applications" TO "anon";
GRANT ALL ON TABLE "public"."applications" TO "authenticated";
GRANT ALL ON TABLE "public"."applications" TO "service_role";



GRANT ALL ON TABLE "public"."cost_usage_tracking" TO "anon";
GRANT ALL ON TABLE "public"."cost_usage_tracking" TO "authenticated";
GRANT ALL ON TABLE "public"."cost_usage_tracking" TO "service_role";



GRANT ALL ON TABLE "public"."allocation_output" TO "anon";
GRANT ALL ON TABLE "public"."allocation_output" TO "authenticated";
GRANT ALL ON TABLE "public"."allocation_output" TO "service_role";



GRANT ALL ON TABLE "public"."allocation_results" TO "anon";
GRANT ALL ON TABLE "public"."allocation_results" TO "authenticated";
GRANT ALL ON TABLE "public"."allocation_results" TO "service_role";



GRANT ALL ON SEQUENCE "public"."allocation_results_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."allocation_results_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."allocation_results_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."allocation_validation" TO "anon";
GRANT ALL ON TABLE "public"."allocation_validation" TO "authenticated";
GRANT ALL ON TABLE "public"."allocation_validation" TO "service_role";



GRANT ALL ON TABLE "public"."anomalies" TO "anon";
GRANT ALL ON TABLE "public"."anomalies" TO "authenticated";
GRANT ALL ON TABLE "public"."anomalies" TO "service_role";



GRANT ALL ON TABLE "public"."app_cost_summary" TO "anon";
GRANT ALL ON TABLE "public"."app_cost_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."app_cost_summary" TO "service_role";



GRANT ALL ON SEQUENCE "public"."app_cost_summary_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."app_cost_summary_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."app_cost_summary_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."app_mapping" TO "anon";
GRANT ALL ON TABLE "public"."app_mapping" TO "authenticated";
GRANT ALL ON TABLE "public"."app_mapping" TO "service_role";



GRANT ALL ON TABLE "public"."application_databases" TO "anon";
GRANT ALL ON TABLE "public"."application_databases" TO "authenticated";
GRANT ALL ON TABLE "public"."application_databases" TO "service_role";



GRANT ALL ON SEQUENCE "public"."application_databases_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."application_databases_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."application_databases_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."audit_logs" TO "anon";
GRANT ALL ON TABLE "public"."audit_logs" TO "authenticated";
GRANT ALL ON TABLE "public"."audit_logs" TO "service_role";



GRANT ALL ON SEQUENCE "public"."audit_logs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."audit_logs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."audit_logs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."budget" TO "anon";
GRANT ALL ON TABLE "public"."budget" TO "authenticated";
GRANT ALL ON TABLE "public"."budget" TO "service_role";



GRANT ALL ON TABLE "public"."budget_vs_actual" TO "anon";
GRANT ALL ON TABLE "public"."budget_vs_actual" TO "authenticated";
GRANT ALL ON TABLE "public"."budget_vs_actual" TO "service_role";



GRANT ALL ON TABLE "public"."mart_cost_classification" TO "anon";
GRANT ALL ON TABLE "public"."mart_cost_classification" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_cost_classification" TO "service_role";



GRANT ALL ON TABLE "public"."mart_dynamic_allocation" TO "anon";
GRANT ALL ON TABLE "public"."mart_dynamic_allocation" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_dynamic_allocation" TO "service_role";



GRANT ALL ON TABLE "public"."unallocated_cost" TO "anon";
GRANT ALL ON TABLE "public"."unallocated_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."unallocated_cost" TO "service_role";



GRANT ALL ON TABLE "public"."final_cost_view" TO "anon";
GRANT ALL ON TABLE "public"."final_cost_view" TO "authenticated";
GRANT ALL ON TABLE "public"."final_cost_view" TO "service_role";



GRANT ALL ON TABLE "public"."client_cost_view" TO "anon";
GRANT ALL ON TABLE "public"."client_cost_view" TO "authenticated";
GRANT ALL ON TABLE "public"."client_cost_view" TO "service_role";



GRANT ALL ON TABLE "public"."cloud_accounts" TO "anon";
GRANT ALL ON TABLE "public"."cloud_accounts" TO "authenticated";
GRANT ALL ON TABLE "public"."cloud_accounts" TO "service_role";



GRANT ALL ON TABLE "public"."usage_metrics" TO "anon";
GRANT ALL ON TABLE "public"."usage_metrics" TO "authenticated";
GRANT ALL ON TABLE "public"."usage_metrics" TO "service_role";



GRANT ALL ON TABLE "public"."client_summary" TO "anon";
GRANT ALL ON TABLE "public"."client_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."client_summary" TO "service_role";



GRANT ALL ON TABLE "public"."clients" TO "anon";
GRANT ALL ON TABLE "public"."clients" TO "authenticated";
GRANT ALL ON TABLE "public"."clients" TO "service_role";



GRANT ALL ON TABLE "public"."cloud_cost_history" TO "anon";
GRANT ALL ON TABLE "public"."cloud_cost_history" TO "authenticated";
GRANT ALL ON TABLE "public"."cloud_cost_history" TO "service_role";



GRANT ALL ON SEQUENCE "public"."cloud_cost_history_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cloud_cost_history_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cloud_cost_history_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."cost_anomaly_view" TO "anon";
GRANT ALL ON TABLE "public"."cost_anomaly_view" TO "authenticated";
GRANT ALL ON TABLE "public"."cost_anomaly_view" TO "service_role";



GRANT ALL ON TABLE "public"."cost_anomaly_org_view" TO "anon";
GRANT ALL ON TABLE "public"."cost_anomaly_org_view" TO "authenticated";
GRANT ALL ON TABLE "public"."cost_anomaly_org_view" TO "service_role";



GRANT ALL ON TABLE "public"."cost_recommendations" TO "anon";
GRANT ALL ON TABLE "public"."cost_recommendations" TO "authenticated";
GRANT ALL ON TABLE "public"."cost_recommendations" TO "service_role";



GRANT ALL ON TABLE "public"."cost_trend" TO "anon";
GRANT ALL ON TABLE "public"."cost_trend" TO "authenticated";
GRANT ALL ON TABLE "public"."cost_trend" TO "service_role";



GRANT ALL ON TABLE "public"."cost_trend_view" TO "anon";
GRANT ALL ON TABLE "public"."cost_trend_view" TO "authenticated";
GRANT ALL ON TABLE "public"."cost_trend_view" TO "service_role";



GRANT ALL ON TABLE "public"."costs" TO "anon";
GRANT ALL ON TABLE "public"."costs" TO "authenticated";
GRANT ALL ON TABLE "public"."costs" TO "service_role";



GRANT ALL ON TABLE "public"."mart_total_cost" TO "anon";
GRANT ALL ON TABLE "public"."mart_total_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_total_cost" TO "service_role";



GRANT ALL ON TABLE "public"."cto_dashboard_view" TO "anon";
GRANT ALL ON TABLE "public"."cto_dashboard_view" TO "authenticated";
GRANT ALL ON TABLE "public"."cto_dashboard_view" TO "service_role";



GRANT ALL ON TABLE "public"."cto_kpi_view" TO "anon";
GRANT ALL ON TABLE "public"."cto_kpi_view" TO "authenticated";
GRANT ALL ON TABLE "public"."cto_kpi_view" TO "service_role";



GRANT ALL ON TABLE "public"."unified_cloud_costs" TO "anon";
GRANT ALL ON TABLE "public"."unified_cloud_costs" TO "authenticated";
GRANT ALL ON TABLE "public"."unified_cloud_costs" TO "service_role";



GRANT ALL ON TABLE "public"."daily_cloud_summary" TO "anon";
GRANT ALL ON TABLE "public"."daily_cloud_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."daily_cloud_summary" TO "service_role";



GRANT ALL ON TABLE "public"."db_performance_metrics" TO "anon";
GRANT ALL ON TABLE "public"."db_performance_metrics" TO "authenticated";
GRANT ALL ON TABLE "public"."db_performance_metrics" TO "service_role";



GRANT ALL ON SEQUENCE "public"."db_performance_metrics_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."db_performance_metrics_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."db_performance_metrics_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."license_cost" TO "anon";
GRANT ALL ON TABLE "public"."license_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."license_cost" TO "service_role";



GRANT ALL ON SEQUENCE "public"."license_cost_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."license_cost_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."license_cost_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."managed_services_cost" TO "anon";
GRANT ALL ON TABLE "public"."managed_services_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."managed_services_cost" TO "service_role";



GRANT ALL ON SEQUENCE "public"."managed_services_cost_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."managed_services_cost_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."managed_services_cost_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."resource_mapping" TO "anon";
GRANT ALL ON TABLE "public"."resource_mapping" TO "authenticated";
GRANT ALL ON TABLE "public"."resource_mapping" TO "service_role";



GRANT ALL ON TABLE "public"."mart_ai_recommendations" TO "anon";
GRANT ALL ON TABLE "public"."mart_ai_recommendations" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_ai_recommendations" TO "service_role";



GRANT ALL ON TABLE "public"."mart_allocation_expanded" TO "anon";
GRANT ALL ON TABLE "public"."mart_allocation_expanded" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_allocation_expanded" TO "service_role";



GRANT ALL ON TABLE "public"."usage_trend" TO "anon";
GRANT ALL ON TABLE "public"."usage_trend" TO "authenticated";
GRANT ALL ON TABLE "public"."usage_trend" TO "service_role";



GRANT ALL ON TABLE "public"."mart_app_kpi" TO "anon";
GRANT ALL ON TABLE "public"."mart_app_kpi" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_app_kpi" TO "service_role";



GRANT ALL ON TABLE "public"."mart_application_cost" TO "anon";
GRANT ALL ON TABLE "public"."mart_application_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_application_cost" TO "service_role";



GRANT ALL ON TABLE "public"."mart_application_costs" TO "anon";
GRANT ALL ON TABLE "public"."mart_application_costs" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_application_costs" TO "service_role";



GRANT ALL ON TABLE "public"."mart_application_summary" TO "anon";
GRANT ALL ON TABLE "public"."mart_application_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_application_summary" TO "service_role";



GRANT ALL ON TABLE "public"."mart_budget_vs_actual" TO "anon";
GRANT ALL ON TABLE "public"."mart_budget_vs_actual" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_budget_vs_actual" TO "service_role";



GRANT ALL ON TABLE "public"."mart_client_cost" TO "anon";
GRANT ALL ON TABLE "public"."mart_client_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_client_cost" TO "service_role";



GRANT ALL ON TABLE "public"."mart_cost_forecast" TO "anon";
GRANT ALL ON TABLE "public"."mart_cost_forecast" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_cost_forecast" TO "service_role";



GRANT ALL ON TABLE "public"."mart_cost_trend" TO "anon";
GRANT ALL ON TABLE "public"."mart_cost_trend" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_cost_trend" TO "service_role";



GRANT ALL ON TABLE "public"."mart_cto_dashboard" TO "anon";
GRANT ALL ON TABLE "public"."mart_cto_dashboard" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_cto_dashboard" TO "service_role";



GRANT ALL ON TABLE "public"."mart_kpi_dashboard" TO "anon";
GRANT ALL ON TABLE "public"."mart_kpi_dashboard" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_kpi_dashboard" TO "service_role";



GRANT ALL ON TABLE "public"."mart_kpi_summary" TO "anon";
GRANT ALL ON TABLE "public"."mart_kpi_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_kpi_summary" TO "service_role";



GRANT ALL ON TABLE "public"."mart_mapping_coverage" TO "anon";
GRANT ALL ON TABLE "public"."mart_mapping_coverage" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_mapping_coverage" TO "service_role";



GRANT ALL ON TABLE "public"."recommendations" TO "anon";
GRANT ALL ON TABLE "public"."recommendations" TO "authenticated";
GRANT ALL ON TABLE "public"."recommendations" TO "service_role";



GRANT ALL ON TABLE "public"."mart_recommendations" TO "anon";
GRANT ALL ON TABLE "public"."mart_recommendations" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_recommendations" TO "service_role";



GRANT ALL ON TABLE "public"."mart_savings" TO "anon";
GRANT ALL ON TABLE "public"."mart_savings" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_savings" TO "service_role";



GRANT ALL ON TABLE "public"."mart_service_cost" TO "anon";
GRANT ALL ON TABLE "public"."mart_service_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_service_cost" TO "service_role";



GRANT ALL ON TABLE "public"."mart_top_services" TO "anon";
GRANT ALL ON TABLE "public"."mart_top_services" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_top_services" TO "service_role";



GRANT ALL ON TABLE "public"."mart_true_cost_v2" TO "anon";
GRANT ALL ON TABLE "public"."mart_true_cost_v2" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_true_cost_v2" TO "service_role";



GRANT ALL ON TABLE "public"."mart_unallocated" TO "anon";
GRANT ALL ON TABLE "public"."mart_unallocated" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_unallocated" TO "service_role";



GRANT ALL ON TABLE "public"."mart_unallocated_cost" TO "anon";
GRANT ALL ON TABLE "public"."mart_unallocated_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."mart_unallocated_cost" TO "service_role";



GRANT ALL ON TABLE "public"."metric_catalog" TO "anon";
GRANT ALL ON TABLE "public"."metric_catalog" TO "authenticated";
GRANT ALL ON TABLE "public"."metric_catalog" TO "service_role";



GRANT ALL ON TABLE "public"."metric_snapshots" TO "anon";
GRANT ALL ON TABLE "public"."metric_snapshots" TO "authenticated";
GRANT ALL ON TABLE "public"."metric_snapshots" TO "service_role";



GRANT ALL ON TABLE "public"."optimization_results" TO "anon";
GRANT ALL ON TABLE "public"."optimization_results" TO "authenticated";
GRANT ALL ON TABLE "public"."optimization_results" TO "service_role";



GRANT ALL ON TABLE "public"."organizations" TO "anon";
GRANT ALL ON TABLE "public"."organizations" TO "authenticated";
GRANT ALL ON TABLE "public"."organizations" TO "service_role";



GRANT ALL ON TABLE "public"."realized_savings" TO "anon";
GRANT ALL ON TABLE "public"."realized_savings" TO "authenticated";
GRANT ALL ON TABLE "public"."realized_savings" TO "service_role";



GRANT ALL ON TABLE "public"."roi_summary" TO "anon";
GRANT ALL ON TABLE "public"."roi_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."roi_summary" TO "service_role";



GRANT ALL ON TABLE "public"."roles" TO "anon";
GRANT ALL ON TABLE "public"."roles" TO "authenticated";
GRANT ALL ON TABLE "public"."roles" TO "service_role";



GRANT ALL ON TABLE "public"."saas_cost" TO "anon";
GRANT ALL ON TABLE "public"."saas_cost" TO "authenticated";
GRANT ALL ON TABLE "public"."saas_cost" TO "service_role";



GRANT ALL ON SEQUENCE "public"."saas_cost_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."saas_cost_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."saas_cost_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."savings_pipeline" TO "anon";
GRANT ALL ON TABLE "public"."savings_pipeline" TO "authenticated";
GRANT ALL ON TABLE "public"."savings_pipeline" TO "service_role";



GRANT ALL ON TABLE "public"."savings_summary" TO "anon";
GRANT ALL ON TABLE "public"."savings_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."savings_summary" TO "service_role";



GRANT ALL ON TABLE "public"."service_cost_summary" TO "anon";
GRANT ALL ON TABLE "public"."service_cost_summary" TO "authenticated";
GRANT ALL ON TABLE "public"."service_cost_summary" TO "service_role";



GRANT ALL ON TABLE "public"."ui_tiles" TO "anon";
GRANT ALL ON TABLE "public"."ui_tiles" TO "authenticated";
GRANT ALL ON TABLE "public"."ui_tiles" TO "service_role";



GRANT ALL ON TABLE "public"."unallocated_cost_advanced" TO "anon";
GRANT ALL ON TABLE "public"."unallocated_cost_advanced" TO "authenticated";
GRANT ALL ON TABLE "public"."unallocated_cost_advanced" TO "service_role";



GRANT ALL ON SEQUENCE "public"."unified_cloud_costs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."unified_cloud_costs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."unified_cloud_costs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."unified_cost_usage" TO "anon";
GRANT ALL ON TABLE "public"."unified_cost_usage" TO "authenticated";
GRANT ALL ON TABLE "public"."unified_cost_usage" TO "service_role";



GRANT ALL ON TABLE "public"."user_roles" TO "anon";
GRANT ALL ON TABLE "public"."user_roles" TO "authenticated";
GRANT ALL ON TABLE "public"."user_roles" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";







