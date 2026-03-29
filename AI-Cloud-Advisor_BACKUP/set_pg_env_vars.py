import os

def set_pg_env_vars():
    os.environ['PGDATABASE'] = 'cloud_advisor'  # Change as needed
    os.environ['PGUSER'] = 'your_postgres_user'  # Change as needed
    os.environ['PGPASSWORD'] = 'your_postgres_password'  # Change as needed
    os.environ['PGHOST'] = 'localhost'  # Change as needed
    os.environ['PGPORT'] = '5432'  # Change as needed
    print("PostgreSQL environment variables set for this session.")

if __name__ == "__main__":
    set_pg_env_vars()
    # You can now run your app or migration script in this session
    # Example: os.system('python migrate_sqlite_to_postgres.py')
