from repositories.executive_dashboard_repository import (
    ExecutiveDashboardRepository,
)


class ExecutiveDashboardV2Service:

    @staticmethod
    def get_dashboard_data():

        summary = (
            ExecutiveDashboardRepository
            .get_executive_summary()
        )

        spend = (
            ExecutiveDashboardRepository
            .get_enterprise_spend()
        )

        budget = (
            ExecutiveDashboardRepository
            .get_budget_vs_actual()
        )

        forecast = (
            ExecutiveDashboardRepository
            .get_spend_forecast()
        )

        savings = (
            ExecutiveDashboardRepository
            .get_savings()
        )

        return {
            "summary": summary,
            "spend": spend,
            "budget": budget,
            "forecast": forecast,
            "savings": savings,
        }
