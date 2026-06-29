from repositories.saas_governance_repository import (
    SaaSGovernanceRepository
)


class SaaSGovernanceService:

    @staticmethod
    def get_saas_spend():

        return (
            SaaSGovernanceRepository
            .get_saas_cost()
        )

    @staticmethod
    def get_license_cost():

        return (
            SaaSGovernanceRepository
            .get_license_cost()
        )

    @staticmethod
    def get_kpis():

        saas = (
            SaaSGovernanceRepository
            .get_saas_cost()
        )

        licenses = (
            SaaSGovernanceRepository
            .get_license_cost()
        )

        total_saas = sum(
            float(r.get("cost", 0))
            for r in saas
        )

        total_license = sum(
            float(r.get("cost", 0))
            for r in licenses
        )

        total_users = sum(
            int(r.get("user_count", 0))
            for r in saas
        )

        licenses_purchased = sum(
            int(r.get("licenses_purchased", 0))
            for r in licenses
        )

        licenses_used = sum(
            int(r.get("licenses_used", 0))
            for r in licenses
        )

        vendors = len(
            set(
                r.get("vendor_name")
                for r in saas
                if r.get("vendor_name")
            )
        )

        utilization = 0

        if licenses_purchased:
            utilization = round(
                (licenses_used / licenses_purchased) * 100,
                1
            )

        return {
            "total_saas": total_saas,
            "total_license": total_license,
            "total_users": total_users,
            "vendors": vendors,
            "licenses_purchased": licenses_purchased,
            "licenses_used": licenses_used,
            "utilization": utilization,
        }