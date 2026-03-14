import sqlite3

def extract_sqlite_schema(db_path="cloud_advisor.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    with open("sqlite_schema.txt", "w") as f:
        for table in tables:
            f.write(f"\n-- Schema for table: {table}\n")
            cur.execute(f"PRAGMA table_info({table})")
            columns = cur.fetchall()
            for col in columns:
                f.write(f"{col[1]} {col[2]}\n")
    conn.close()
    print("Schema written to sqlite_schema.txt")

if __name__ == "__main__":
    extract_sqlite_schema()
