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
    def get_trend():

        return (
            TechnologySpendRepository
            .get_monthly_summary()
        )