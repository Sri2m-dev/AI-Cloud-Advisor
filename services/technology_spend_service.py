from repositories.technology_spend_repository import (
    TechnologySpendRepository
)


class TechnologySpendService:

    @staticmethod
    def get_summary():

        return (
            TechnologySpendRepository
            .get_latest_summary()
        )

    @staticmethod
    def get_spend_breakdown():

        return (
            TechnologySpendRepository
            .get_enterprise_spend_breakdown()
        )

    @staticmethod
    def get_managed_services():

        return (
            TechnologySpendRepository
            .get_managed_services_cost()
        )

    @staticmethod
    def get_saas_spend():

        return (
            TechnologySpendRepository
            .get_saas_cost()
        )

    @staticmethod
    def get_kpis():

        return (
            TechnologySpendRepository
            .get_kpis()
        )