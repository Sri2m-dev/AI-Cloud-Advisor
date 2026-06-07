def normalize_approvals(df):
    """
    Normalize approvals dataframe columns to enterprise contract.
    """
    rename_map = {
        "recommendation_id": "rec_id",
        "assigned_to": "assignee",
        "requested_by": "requester",
        "approved_by": "approver",
        "created_at": "date"
    }
    return df.rename(columns=rename_map)

