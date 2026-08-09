from repositories.technology_spend_repository import (
    TechnologySpendRepository,
    technology_spend_kpis,
)
from services.technology_spend_composition import technology_spend_repository


class TechnologySpendService:
    def __init__(self, repository: TechnologySpendRepository | None = None) -> None:
        self.repository = repository or technology_spend_repository()

    def get_summary(self, organization_id):
        rows = self.repository.get_enterprise_spend_breakdown(organization_id)
        return rows[0] if rows else {}

    def get_spend_breakdown(self, organization_id):
        return self.repository.get_enterprise_spend_breakdown(organization_id)

    def get_managed_services(self, organization_id):
        return self.repository.get_managed_services_cost(organization_id)

    def get_saas_spend(self, organization_id):
        return self.repository.get_saas_cost(organization_id)

    def get_kpis(self, organization_id):
        return technology_spend_kpis(self.repository, organization_id)

    def get_budget_vs_actual(self, organization_id):
        return self.repository.get_budget_vs_actual(organization_id)

    def get_enterprise_forecast(self, organization_id):
        return self.repository.get_enterprise_forecast(organization_id)

    def get_recommendations(self, organization_id):
        return self.repository.get_recommendations(organization_id)

    def get_executive_summary(self, organization_id):
        return self.repository.get_executive_summary(organization_id)
