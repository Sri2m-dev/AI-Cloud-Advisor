from __future__ import annotations

from typing import Any

import streamlit as st

from repositories.knowledge_graph_repository import KnowledgeGraphRepository
from repositories.saas_intelligence_repository import SaaSIntelligenceRepository
from repositories.technology_spend_repository import TechnologySpendRepository


class CopilotRepository:
    @staticmethod
    @st.cache_data(ttl=300)
    def get_knowledge_nodes() -> list[dict[str, Any]]:
        return KnowledgeGraphRepository.get_all_nodes()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_knowledge_relationships() -> list[dict[str, Any]]:
        return KnowledgeGraphRepository.get_all_relationships()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_inventory() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_technology_inventory()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_saas_costs() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_saas_costs()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_license_costs() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_license_costs()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_renewal_risks() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_renewal_risks()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_inactive_users() -> list[dict[str, Any]]:
        return SaaSIntelligenceRepository.get_inactive_users()

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_spend_kpis() -> dict[str, Any]:
        return TechnologySpendRepository.get_kpis()
