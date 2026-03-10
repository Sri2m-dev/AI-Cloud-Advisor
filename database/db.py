# db.py
# Database connection and ORM logic for AI-Cloud-Advisor

def get_db():
import sqlite3

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
