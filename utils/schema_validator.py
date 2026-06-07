"""
Schema validation utility for Supabase/Postgres tables.
Ensures required tables and columns exist before app startup.
"""
import logging

REQUIRED_TABLES = {
    "users": ["email", "role", "org_id"],
    "recommendations": ["status", "impact"],
    # Add more tables/columns as needed
}

def validate_schema(supabase):
    """
    Checks that all required tables and columns exist in the database.
    Logs errors and returns False if any are missing.
    """
    missing = []
    for table, columns in REQUIRED_TABLES.items():
        try:
            table_info = supabase.table(table).select("*").limit(1).execute()
            actual_cols = set(table_info.data[0].keys()) if table_info.data else set()
            for col in columns:
                if col not in actual_cols:
                    missing.append(f"{table}.{col}")
        except Exception as e:
            missing.append(f"{table} (table missing or inaccessible)")
    if missing:
        logging.error(f"Schema validation failed. Missing: {missing}")
        return False
    return True

