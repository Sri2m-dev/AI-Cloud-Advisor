# Mart & KPI Table Schemas

Below are example schemas for your core mart and KPI tables. Adjust as needed for your warehouse (e.g., Supabase/Postgres).

---

## kpi_total_cloud_spend
| Column         | Type        | Description                       |
|---------------|-------------|-----------------------------------|
| id            | SERIAL/UUID | Primary key                       |
| date          | DATE        | Billing date                      |
| total_spend   | NUMERIC     | Total cloud spend (all providers) |
| created_at    | TIMESTAMP   | Record creation time              |

## kpi_spend_by_cloud
| Column         | Type        | Description                       |
|---------------|-------------|-----------------------------------|
| id            | SERIAL/UUID | Primary key                       |
| date          | DATE        | Billing date                      |
| cloud         | TEXT        | Cloud provider (AWS/Azure/GCP)    |
| spend         | NUMERIC     | Spend for this provider           |
| created_at    | TIMESTAMP   | Record creation time              |

## kpi_top_services
| Column         | Type        | Description                       |
|---------------|-------------|-----------------------------------|
| id            | SERIAL/UUID | Primary key                       |
| date          | DATE        | Billing date                      |
| cloud         | TEXT        | Cloud provider                    |
| service       | TEXT        | Service name                      |
| spend         | NUMERIC     | Spend for this service            |
| created_at    | TIMESTAMP   | Record creation time              |

## mart_cost_anomalies
| Column         | Type        | Description                       |
|---------------|-------------|-----------------------------------|
| id            | SERIAL/UUID | Primary key                       |
| date          | DATE        | Date of anomaly                   |
| account_id    | TEXT        | Cloud account identifier          |
| service       | TEXT        | Service name                      |
| anomaly_score | NUMERIC     | Anomaly score                     |
| details       | JSONB/TEXT  | Additional metadata               |
| created_at    | TIMESTAMP   | Record creation time              |

## mart_optimization_opportunities
| Column         | Type        | Description                       |
|---------------|-------------|-----------------------------------|
| id            | SERIAL/UUID | Primary key                       |
| date          | DATE        | Recommendation date               |
| account_id    | TEXT        | Cloud account identifier          |
| type          | TEXT        | Optimization type                 |
| impact        | NUMERIC     | Estimated savings                 |
| status        | TEXT        | Status (open/closed/implemented)  |
| details       | JSONB/TEXT  | Additional metadata               |
| created_at    | TIMESTAMP   | Record creation time              |

---

> Next: Implement ETL logic to populate these tables, then connect them to your dashboards.
