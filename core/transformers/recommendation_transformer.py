def normalize_recommendations(df):
    rename_map = {
        "provider": "cloud",
        "recommendation": "recommendation_type",
        "resource": "resource_name",
        "saving": "estimated_savings"
    }
    existing = {
        k: v for k, v in rename_map.items()
        if k in df.columns
    }
    return df.rename(columns=existing)

