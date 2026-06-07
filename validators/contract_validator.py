# validators/contract_validator.py
"""
Enterprise contract validator for analytics dataframes.
Ensures all required columns are present before downstream use.
"""
def validate_columns(df, required_columns):
    missing = [
        c for c in required_columns
        if c not in df.columns
    ]
    return {
        "valid": len(missing) == 0,
        "missing": missing
    }

