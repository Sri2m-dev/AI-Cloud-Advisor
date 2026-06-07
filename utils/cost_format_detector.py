def detect_provider(df):

    cols = [c.lower() for c in df.columns]

    if "lineitem/usagetype" in cols:
        return "AWS_CUR"

    if "service" in cols and "total cost" in cols:
        return "AWS_SUMMARY"

    if "metercategory" in cols:
        return "AZURE"

    if "service.description" in cols:
        return "GCP"

    return "CUSTOM"