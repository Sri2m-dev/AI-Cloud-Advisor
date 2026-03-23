import requests
import streamlit as st

def get_cost_data():
    import psycopg2
    import os
    try:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST"),
            port=os.getenv("PGPORT"),
            user=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"),
            dbname=os.getenv("PGDATABASE")
        )
        cur = conn.cursor()
        cur.execute("SELECT * FROM billing_data LIMIT 10;")
        data = cur.fetchall()
        cur.close()
        conn.close()
        return data
    except Exception as e:
        st.error(f"DB error: {e}")
        return None
