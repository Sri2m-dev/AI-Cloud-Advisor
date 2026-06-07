# Mapping layer for standardizing schema across clouds, APIs, and datasets
# This will help with future-proofing as APIs, tenants, and AI models expand

STANDARD_COLUMNS = {
    "cloud_provider": "cloud",
    "service_name": "service",
    "total_cost": "spend",
    # Add more mappings as needed for new columns or sources
}

# Example usage:
# df.rename(columns=STANDARD_COLUMNS, inplace=True)

