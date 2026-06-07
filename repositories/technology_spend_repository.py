from services.supabase_client import supabase


class TechnologySpendRepository:

    @staticmethod
    def get_monthly_summary():

        response = (
            supabase
            .table("technology_monthly_spend_summary")
            .select("*")
            .order("spend_month")
            .execute()
        )

        return response.data or []

    @staticmethod
    def get_latest_summary():

        response = (
            supabase
            .table("technology_monthly_spend_summary")
            .select("*")
            .order("spend_month", desc=True)
            .limit(1)
            .execute()
        )

        data = response.data or []

        if data:
            return data[0]

        return {}