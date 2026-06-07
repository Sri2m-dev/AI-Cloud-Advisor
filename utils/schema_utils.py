def get_service_name(item):
    if isinstance(item, dict):
        return item.get("service_name") or item.get("name") or "Unknown"
    return "Unknown"


def get_service_column(df):
    return "service_name" if "service_name" in df.columns else "name"

