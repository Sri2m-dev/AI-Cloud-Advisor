from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id


AUTHENTICATION_TYPES = [
    "OAuth2",
    "API Key",
    "Bearer Token",
    "JWT",
    "Basic Auth",
    "Certificate",
    "SAML",
    "LDAP",
    "Database",
    "Webhook Secret",
]

CONNECTOR_TEMPLATES = [
    {
        "Template": "HRMS API",
        "Category": "HR",
        "Source Type": "REST / OpenAPI",
        "Entities": "Users, Departments, Managers, Cost Centers",
        "Authentication": "OAuth2",
        "Certification Target": "Gold",
    },
    {
        "Template": "SAP Finance",
        "Category": "ERP",
        "Source Type": "OData / REST",
        "Entities": "Cost Centers, Vendors, Invoices, Business Units",
        "Authentication": "SAML",
        "Certification Target": "Gold",
    },
    {
        "Template": "Oracle HRMS Database",
        "Category": "Database",
        "Source Type": "Oracle",
        "Entities": "Employees, Roles, Departments, Locations",
        "Authentication": "Database",
        "Certification Target": "Silver",
    },
    {
        "Template": "Retail POS Files",
        "Category": "File",
        "Source Type": "CSV / Excel / JSON",
        "Entities": "Stores, Transactions, Products, Revenue",
        "Authentication": "File Vault",
        "Certification Target": "Silver",
    },
    {
        "Template": "Incident Webhook",
        "Category": "Event",
        "Source Type": "Webhook",
        "Entities": "Incidents, Deployments, Alerts, Recoveries",
        "Authentication": "Webhook Secret",
        "Certification Target": "Gold",
    },
]

MARKETPLACE_CONNECTORS = [
    ("Built-in", "AWS", "Gold", "Cloud accounts, billing, inventory, operations"),
    ("Built-in", "Azure", "Gold", "Subscriptions, cost, resources, governance"),
    ("Built-in", "GCP", "Gold", "Projects, billing, assets, recommendations"),
    ("Built-in", "ServiceNow", "Gold", "CMDB, incidents, changes, CAB, SLAs"),
    ("Built-in", "GitHub", "Gold", "Repositories, deployments, Actions, security"),
    ("Partner", "SAP Finance Accelerator", "Silver", "Finance entities and cost center mapping"),
    ("Customer", "Retail POS Connector", "Bronze", "Store and transaction flat-file ingestion"),
    ("AI Generated", "HRMS OAuth Connector", "Gold", "Users, departments, managers, cost centers"),
]


class UniversalConnectorPlatformService:
    @staticmethod
    def get_studio_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        draft = UniversalConnectorPlatformService.build_connector_draft(
            name="HRMS OAuth Connector",
            base_url="https://company.example/api",
            auth_type="OAuth2",
            source_type="OpenAPI",
            organization_id=org_id,
        )
        certification = UniversalConnectorPlatformService.certify_connector(draft)
        return {
            "organization_id": org_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": {
                "Marketplace Connectors": len(MARKETPLACE_CONNECTORS),
                "Templates": len(CONNECTOR_TEMPLATES),
                "Auth Methods": len(AUTHENTICATION_TYPES),
                "Draft Connectors": 4,
                "Published Connectors": 2,
                "AI Generated": 1,
                "Studio Readiness": 96,
            },
            "marketplace": UniversalConnectorPlatformService.marketplace(),
            "my_connectors": UniversalConnectorPlatformService.my_connectors(),
            "templates": CONNECTOR_TEMPLATES,
            "authentication_types": UniversalConnectorPlatformService.authentication_builder(),
            "api_discovery": UniversalConnectorPlatformService.discover_api(draft["base_url"]),
            "schema_discovery": UniversalConnectorPlatformService.discover_schema(),
            "field_mapping": UniversalConnectorPlatformService.suggest_field_mapping(),
            "knowledge_graph_mapping": UniversalConnectorPlatformService.knowledge_graph_mapping(),
            "digital_twin_mapping": UniversalConnectorPlatformService.digital_twin_mapping(),
            "database_connectors": UniversalConnectorPlatformService.database_connectors(),
            "file_connectors": UniversalConnectorPlatformService.file_connectors(),
            "webhook_builder": UniversalConnectorPlatformService.webhook_builder(),
            "ai_connector_generator": UniversalConnectorPlatformService.ai_connector_generator(draft),
            "scheduler": UniversalConnectorPlatformService.scheduler_plan(),
            "certification": certification,
            "publish_plan": UniversalConnectorPlatformService.publish_plan(draft, certification),
            "copilot_example": UniversalConnectorPlatformService.copilot_example(),
            "executive_summary": (
                "Connector Studio lets customers and partners build certified connectors without waiting for core product releases. "
                "The workspace combines authentication setup, API and schema discovery, AI mapping, Knowledge Graph and Digital Twin mapping, "
                "scheduling, certification, and marketplace publishing."
            ),
        }

    @staticmethod
    def build_connector_draft(
        name: str,
        base_url: str,
        auth_type: str,
        source_type: str = "OpenAPI",
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "organization_id": resolve_organization_id(organization_id),
            "name": name,
            "base_url": base_url,
            "source_type": source_type,
            "auth_type": auth_type,
            "status": "Draft",
            "entities": ["Users", "Departments", "Managers", "Cost Centers"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def marketplace() -> list[dict[str, Any]]:
        return [
            {
                "Type": connector_type,
                "Connector": name,
                "Certification": certification,
                "Compatibility": "Knowledge Graph, Digital Twin, Telemetry Fabric, Event Bus",
                "Supported Entities": supported_entities,
                "Last Validation": "2026-06-28",
            }
            for connector_type, name, certification, supported_entities in MARKETPLACE_CONNECTORS
        ]

    @staticmethod
    def my_connectors() -> list[dict[str, Any]]:
        return [
            {"Connector": "HRMS OAuth Connector", "Status": "Draft", "Certification": "Pending", "Owner": "People Systems", "Last Run": "Not published"},
            {"Connector": "Retail POS Connector", "Status": "Published", "Certification": "Bronze", "Owner": "Retail Ops", "Last Run": "2026-06-27 18:00"},
            {"Connector": "Incident Webhook", "Status": "Published", "Certification": "Gold", "Owner": "SRE", "Last Run": "Event driven"},
            {"Connector": "Oracle HRMS Database", "Status": "Mapping", "Certification": "Pending", "Owner": "HR Technology", "Last Run": "Not scheduled"},
        ]

    @staticmethod
    def authentication_builder() -> list[dict[str, Any]]:
        return [
            {"Authentication Type": auth_type, "Vault Ready": True, "Rotation": "Automatic" if auth_type in {"OAuth2", "JWT", "Certificate"} else "Policy based", "Least Privilege": True}
            for auth_type in AUTHENTICATION_TYPES
        ]

    @staticmethod
    def discover_api(base_url: str) -> dict[str, Any]:
        return {
            "Base URL": base_url,
            "Detected": ["Swagger", "OpenAPI", "REST", "Metadata"],
            "GraphQL": "Not detected",
            "SOAP": "Not detected",
            "Endpoints": [
                {"Method": "GET", "Path": "/employees", "Entity": "Users", "Confidence": 98},
                {"Method": "GET", "Path": "/departments", "Entity": "Departments", "Confidence": 97},
                {"Method": "GET", "Path": "/managers", "Entity": "Managers", "Confidence": 95},
                {"Method": "GET", "Path": "/cost-centers", "Entity": "Cost Centers", "Confidence": 96},
            ],
            "AI Summary": "Detected a people-system API with user, department, manager, and cost-center resources.",
        }

    @staticmethod
    def discover_schema() -> list[dict[str, Any]]:
        return [
            {"Source Field": "employeeName", "Type": "string", "Sample": "Avery Shah", "Null Rate": "0%"},
            {"Source Field": "department", "Type": "string", "Sample": "Finance", "Null Rate": "1%"},
            {"Source Field": "manager", "Type": "string", "Sample": "Jordan Lee", "Null Rate": "4%"},
            {"Source Field": "monthlyCost", "Type": "number", "Sample": "12400", "Null Rate": "0%"},
            {"Source Field": "activeFlag", "Type": "boolean", "Sample": "true", "Null Rate": "0%"},
        ]

    @staticmethod
    def suggest_field_mapping() -> list[dict[str, Any]]:
        return [
            {"Source Field": "employeeName", "Suggested Entity": "User", "Target Field": "display_name", "Confidence": 98, "Status": "Suggested"},
            {"Source Field": "department", "Suggested Entity": "Department", "Target Field": "owner_department", "Confidence": 97, "Status": "Suggested"},
            {"Source Field": "manager", "Suggested Entity": "Owner", "Target Field": "business_owner", "Confidence": 95, "Status": "Suggested"},
            {"Source Field": "monthlyCost", "Suggested Entity": "Financial Entity", "Target Field": "monthly_cost", "Confidence": 96, "Status": "Suggested"},
            {"Source Field": "activeFlag", "Suggested Entity": "Status", "Target Field": "status", "Confidence": 99, "Status": "Suggested"},
        ]

    @staticmethod
    def knowledge_graph_mapping() -> list[dict[str, Any]]:
        return [
            {"Source Entity": "Users", "Graph Node": "User", "Relationship": "BELONGS_TO", "Target": "Department"},
            {"Source Entity": "Departments", "Graph Node": "Department", "Relationship": "OWNS", "Target": "Application"},
            {"Source Entity": "Managers", "Graph Node": "Owner", "Relationship": "ACCOUNTABLE_FOR", "Target": "Business Service"},
            {"Source Entity": "Cost Centers", "Graph Node": "Cost Center", "Relationship": "FUNDS", "Target": "Business Capability"},
        ]

    @staticmethod
    def digital_twin_mapping() -> list[dict[str, Any]]:
        return [
            {"Question": "Is this a User?", "Detected": "Users", "Action": "Map to identity twin"},
            {"Question": "Is this a Department?", "Detected": "Departments", "Action": "Map to organization twin"},
            {"Question": "Is this a License?", "Detected": "monthlyCost", "Action": "Map to financial twin"},
            {"Question": "Is this a Status?", "Detected": "activeFlag", "Action": "Map to lifecycle health"},
        ]

    @staticmethod
    def database_connectors() -> list[dict[str, Any]]:
        return [
            {"Database": "SQL Server", "Discovery": "Tables, relationships, views, schemas", "Status": "Supported"},
            {"Database": "Oracle", "Discovery": "Tables, relationships, views, schemas", "Status": "Supported"},
            {"Database": "PostgreSQL", "Discovery": "Tables, relationships, views, schemas", "Status": "Supported"},
            {"Database": "MySQL", "Discovery": "Tables, relationships, views, schemas", "Status": "Supported"},
            {"Database": "MongoDB", "Discovery": "Collections, documents, indexes", "Status": "Supported"},
            {"Database": "Snowflake", "Discovery": "Databases, schemas, tables, views", "Status": "Supported"},
            {"Database": "SAP HANA", "Discovery": "Schemas, calculation views, tables", "Status": "Supported"},
        ]

    @staticmethod
    def file_connectors() -> list[dict[str, Any]]:
        return [
            {"Format": "CSV", "Mapping": "Columns to Knowledge Graph", "Status": "Supported"},
            {"Format": "Excel", "Mapping": "Sheets and columns to entities", "Status": "Supported"},
            {"Format": "JSON", "Mapping": "Nested documents to entities", "Status": "Supported"},
            {"Format": "XML", "Mapping": "Elements and attributes to entities", "Status": "Supported"},
            {"Format": "Parquet", "Mapping": "Columnar schema to entities", "Status": "Supported"},
            {"Format": "Avro", "Mapping": "Schema registry to entities", "Status": "Supported"},
        ]

    @staticmethod
    def webhook_builder() -> dict[str, Any]:
        return {
            "Supported": True,
            "Flow": ["Incoming Webhook", "Enterprise Event Bus", "AI Correlation", "Incident Timeline"],
            "Use Cases": ["GitHub deployments", "Monitoring alerts", "Security findings", "Incident updates"],
            "Security": "Webhook Secret with replay protection metadata",
        }

    @staticmethod
    def ai_connector_generator(draft: dict[str, Any]) -> dict[str, Any]:
        return {
            "Input": "Swagger.json / OpenAPI / GraphQL schema / Uploaded API specification",
            "Generated Assets": [
                "Authentication",
                "SDK",
                "Endpoints",
                "Sync",
                "Normalization",
                "Scheduler",
                "Tests",
                "Dashboard",
                "Certification",
            ],
            "Connector": draft["name"],
            "Estimated Build Time": "2 hours",
            "Manual Effort Reduced": "85%",
        }

    @staticmethod
    def scheduler_plan() -> list[dict[str, Any]]:
        return [
            {"Step": "Authenticate", "Mode": "Pre-flight", "Required": True},
            {"Step": "Discover API", "Mode": "On demand", "Required": True},
            {"Step": "Sync Users", "Mode": "Hourly", "Required": True},
            {"Step": "Sync Departments", "Mode": "Daily", "Required": True},
            {"Step": "Publish Events", "Mode": "Event driven", "Required": False},
            {"Step": "Run Certification", "Mode": "Before publish", "Required": True},
        ]

    @staticmethod
    def certify_connector(draft: dict[str, Any]) -> dict[str, Any]:
        coverage = {
            "Authentication": True,
            "API Discovery": True,
            "Schema Discovery": True,
            "Field Mapping": True,
            "Normalization": True,
            "Knowledge Graph Mapping": True,
            "Digital Twin Mapping": True,
            "Scheduler": True,
            "Security": True,
            "Performance": True,
        }
        return {
            "Connector": draft["name"],
            "Level": "Gold",
            "Health": 97,
            "Coverage": coverage,
            "Coverage Percent": 100,
            "Performance": "Healthy",
            "Security": "Vault-backed, no raw secrets in generated assets",
            "Reliability": "Retry and certification hooks ready",
        }

    @staticmethod
    def publish_plan(draft: dict[str, Any], certification: dict[str, Any]) -> dict[str, Any]:
        return {
            "Connector": draft["name"],
            "Publish Status": "Ready",
            "Marketplace Type": "Customer Connector",
            "Certification": certification["Level"],
            "Compatibility": ["Knowledge Graph", "Digital Twin", "Telemetry Fabric", "Event Bus", "Copilot"],
            "Required Approvals": ["Integration Owner", "Security Owner"],
        }

    @staticmethod
    def copilot_example() -> dict[str, Any]:
        return {
            "User": "Connect our HRMS.",
            "AI": (
                "Detected Swagger API, OAuth authentication, 14 tables, and entities for Users, Departments, Managers, "
                "and Cost Centers. Suggested mapping is ready. Create connector?"
            ),
            "Suggested Action": "Create draft connector and run certification.",
        }
