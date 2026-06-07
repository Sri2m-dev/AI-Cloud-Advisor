import pandas as pd

def parse_file(file):
    try:
        df = pd.read_excel(file)

        # Normalize column names
        df.columns = [c.lower().strip() for c in df.columns]

        service_col = "service_name" if "service_name" in df.columns else "service"

        df_grouped = df.groupby(service_col)["cost"].sum().reset_index()

        services = [
            {"service_name": row[service_col], "cost": row["cost"]}
            for _, row in df_grouped.iterrows()
        ]

        return {
            "services": services,
            "total_spend": df["cost"].sum(),
            "previous_spend": 0,
            "error": None
        }

    except Exception as e:
        return {
            "services": [],
            "total_spend": 0,
            "previous_spend": 0,
            "error": str(e)
        }

