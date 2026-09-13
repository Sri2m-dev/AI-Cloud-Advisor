import streamlit as st

from services.supabase_client import supabase


def _normalized(value) -> str:
    return str(value or "").strip().lower()


class ApplicationRepository:

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_registry():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend_mapping():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_spend():
        return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_master():
        try:
            registry_rows = ApplicationRepository.get_application_registry()
            mapping_rows = ApplicationRepository.get_application_spend_mapping()

            mappings_by_registry: dict[str, list[dict]] = {}
            for row in mapping_rows:
                registry_app = row.get("registry_app_name")
                mappings_by_registry.setdefault(_normalized(registry_app), []).append(row)

            master_rows = []
            for registry in registry_rows:
                app_name = registry.get("app_name")
                matches = mappings_by_registry.get(_normalized(app_name), [])

                if not matches:
                    matches = [
                        {
                            "spend_application": app_name,
                            "registry_app": app_name,
                        }
                    ]

                for mapping in matches:
                    master_rows.append(
                        {
                            "app_name": app_name,
                            "business_unit": registry.get("business_unit"),
                            "department": registry.get("department"),
                            "team_name": registry.get("team_name"),
                            "owner_name": registry.get("owner_name"),
                            "owner_email": registry.get("owner_email"),
                            "criticality": registry.get("criticality"),
                            "cloud_provider": registry.get("cloud_provider"),
                            "cost_center": registry.get("cost_center"),
                            "spend_application": mapping.get("spend_application_name"),
                            "registry_app": mapping.get("registry_app_name"),
                        }
                    )

            return master_rows
        except Exception:
            return []
