import psycopg2
import os

def get_cost_data():
    conn = psycopg2.connect(
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        dbname=os.getenv("PGDATABASE")
    )

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM billing_data LIMIT 10;")

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows
