import os
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from tqdm import tqdm

# --- CONFIGURATION ---
SQLITE_DB_PATH = "cloud_advisor.db"
PG_USER = os.getenv("PGUSER", "your_pg_user")
PG_PASSWORD = os.getenv("PGPASSWORD", "your_pg_password")
PG_HOST = os.getenv("PGHOST", "localhost")
PG_PORT = os.getenv("PGPORT", "5432")
PG_DB = os.getenv("PGDATABASE", "cloud_advisor")

# --- CONNECTION STRINGS ---
sqlite_url = f"sqlite:///{SQLITE_DB_PATH}"
pg_url = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# --- ENGINES ---
sqlite_engine = create_engine(sqlite_url)
pg_engine = create_engine(pg_url)

# --- MIGRATION ---
with sqlite_engine.connect() as sqlite_conn, pg_engine.connect() as pg_conn:
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    print(f"Found tables: {tables}")

    for table in tqdm(tables, desc="Migrating tables"):
        print(f"\nMigrating table: {table}")
        df = pd.read_sql_table(table, sqlite_conn)
        if_exists = "replace" if not pg_engine.dialect.has_table(pg_conn, table) else "append"
        # Create table if not exists, then append data
        df.to_sql(table, pg_engine, if_exists="replace", index=False, method="multi")
        print(f"Table {table} migrated with {len(df)} rows.")

    print("\nMigration complete! All tables and data have been copied to PostgreSQL.")

# --- OPTIONAL: Verify row counts ---
print("\nVerifying row counts:")
with sqlite_engine.connect() as sqlite_conn, pg_engine.connect() as pg_conn:
    for table in tables:
        sqlite_count = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        pg_count = pg_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
        print(f"{table}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
