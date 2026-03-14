import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import os

def get_pg_connection():
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "cloud_advisor"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "password"),
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432")
    )

def migrate_table(sqlite_conn, pg_conn, table, columns):
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()
    sqlite_cur.execute(f"SELECT {', '.join(columns)} FROM {table}")
    rows = sqlite_cur.fetchall()
    if not rows:
        print(f"No data to migrate for {table}")
        return
    placeholders = ','.join(['%s'] * len(columns))
    insert_query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    execute_values(pg_cur, insert_query, rows)
    pg_conn.commit()
    print(f"Migrated {len(rows)} rows to {table}")

def main():
    sqlite_conn = sqlite3.connect("cloud_advisor.db")
    pg_conn = get_pg_connection()
    # Migrate users
    migrate_table(sqlite_conn, pg_conn, "users", ["username", "password", "role"])
    # Migrate billing_data
    migrate_table(sqlite_conn, pg_conn, "billing_data", ["account", "service", "cost"])
    # Migrate cloud_accounts
    migrate_table(sqlite_conn, pg_conn, "cloud_accounts", ["id", "provider", "details", "created_at"])
    # Migrate audit_log
    migrate_table(sqlite_conn, pg_conn, "audit_log", ["id", "username", "action", "details", "timestamp"])
    sqlite_conn.close()
    pg_conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    main()
