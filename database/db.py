# PostgreSQL integration
import psycopg2
from psycopg2.extras import RealDictCursor
import os

def get_pg_connection():
    """
    Returns a PostgreSQL connection using environment variables.
    """
    conn = psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "cloud_advisor"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "password"),
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        cursor_factory=RealDictCursor
    )
    return conn

def init_pg_db():
    """
    Initializes the PostgreSQL database schema.
    """
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        company VARCHAR(255)
    );
    CREATE TABLE IF NOT EXISTS cloud_accounts (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        provider VARCHAR(20),
        account_id VARCHAR(255),
        credentials_encrypted TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS cost_data (
        id SERIAL PRIMARY KEY,
        account_id INTEGER REFERENCES cloud_accounts(id),
        date DATE,
        service VARCHAR(255),
        cost NUMERIC
    );
    CREATE TABLE IF NOT EXISTS predictions (
        id SERIAL PRIMARY KEY,
        account_id INTEGER REFERENCES cloud_accounts(id),
        month VARCHAR(7),
        predicted_cost NUMERIC
    );
    """)
    conn.commit()
    cur.close()
    conn.close()

# db.py
# Database connection and ORM logic for AI-Cloud-Advisor

import sqlite3

def get_db():
    return sqlite3.connect("cloud_advisor.db", check_same_thread=False)

def create_tables():
    conn.execute("""
    CREATE TABLE IF NOT EXISTS billing_data (
        account TEXT,
        service TEXT,
        cost REAL
    )
    """)
    conn.commit()

    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def insert_cost(account, service, cost):
    conn.execute(
        "INSERT INTO billing_data VALUES (?, ?, ?)",
        (account, service, cost)
    )
    conn.commit()

    conn = get_db()
    conn.execute(
        "INSERT INTO billing_data VALUES (?, ?, ?)",
        (account, service, cost)
    )
    conn.commit()
    conn.close()

def add_user(username, password, role):
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
    conn.commit()
    conn.close()

def get_user(username):
    conn = get_db()
    cur = conn.execute('SELECT username, password, role FROM users WHERE username = ?', (username,))
    user = cur.fetchone()
    conn.close()
    return user
