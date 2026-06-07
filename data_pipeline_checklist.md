# Data Ingestion Pipeline Checklist

## 1. Data Sources
- [ ] AWS CUR (Cost & Usage Report)
- [ ] Azure Cost Management APIs
- [ ] GCP Billing Export
- [ ] Other SaaS/Cloud APIs

## 2. Extraction
- [ ] Schedule regular data pulls (daily/hourly)
- [ ] Secure credentials and access
- [ ] Store raw data (S3, GCS, Azure Blob, etc.)

## 3. Transformation (ETL)
- [ ] Parse and clean raw data
- [ ] Normalize schema (unify columns, types)
- [ ] Enrich with tags, accounts, business units
- [ ] Handle missing/invalid data

## 4. Load to Warehouse
- [ ] Load into Supabase (or other warehouse)
- [ ] Partition by date/account for performance
- [ ] Validate row counts and data quality

## 5. Mart Tables

### Required Mart & KPI Tables (Phase 1)

- [ ] **kpi_total_cloud_spend**: Stores total cloud spend (all providers, daily/monthly granularity)
- [ ] **kpi_spend_by_cloud**: Spend breakdown by cloud (AWS, Azure, GCP, etc.)
- [ ] **kpi_top_services**: Top N services by spend (per cloud, per period)
- [ ] **mart_cost_anomalies**: Detected cost anomalies with metadata (date, account, service, anomaly score, etc.)
- [ ] **mart_optimization_opportunities**: Recommendations for cost optimization (type, impact, status, etc.)

> **Next Steps:**
> - Define schema for each table (columns, types, keys)
> - Specify ETL logic and refresh schedule
> - Implement population scripts/SQL
> - Validate with sample data and connect to dashboards

- [ ] Examples: total spend, forecast, anomalies, savings

## 7. Automation & Monitoring
- [ ] Automate pipeline (Airflow, Prefect, dbt, etc.)
- [ ] Monitor for failures/data gaps
- [ ] Alert on pipeline errors

## 8. Documentation
- [ ] Document schema, pipeline steps, and data contracts
- [ ] Version control for pipeline code

---

Fill out this checklist as you design and implement your ingestion pipeline. Tackle one cloud/source at a time for best results.
