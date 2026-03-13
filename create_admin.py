import sqlite3
conn = sqlite3.connect("cloud_advisor.db")
conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)")
conn.execute("REPLACE INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "cloud123", "admin"))
conn.commit()
conn.close()
print("Admin user created.")
