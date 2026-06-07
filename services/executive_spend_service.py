from services.technology_spend_service import (
    TechnologySpendService
)


class ExecutiveSpendService:

    @staticmethod
    def get_dashboard_data():

        summary = (
            TechnologySpendService
            .get_summary()
        )

        trend = (
            TechnologySpendService
            .get_trend()
        )

        return {
            "summary": summary,
            "trend": trend
        }