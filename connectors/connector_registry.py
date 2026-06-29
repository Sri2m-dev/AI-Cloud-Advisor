"""Central registry for Nexora cloud, SaaS, and AI connectors."""

from __future__ import annotations

from typing import Any

from connectors.aws import AWSConnector
from connectors.azure import AzureConnector
from connectors.copilot import CopilotConnector
from connectors.datadog import DatadogConnector
from connectors.dynatrace import DynatraceConnector
from connectors.gcp import GCPConnector
from connectors.grafana import GrafanaConnector
from connectors.github import GitHubConnector
from connectors.jira import JiraConnector
from connectors.microsoft365 import Microsoft365Connector
from connectors.newrelic import NewRelicConnector
from connectors.openai import OpenAIConnector
from connectors.prometheus import PrometheusConnector
from connectors.servicenow import ServiceNowConnector
from connectors.slack import SlackConnector
from connectors.splunk import SplunkConnector
from connectors.zoom import ZoomConnector


CONNECTOR_CLASSES = {
    "AWS": AWSConnector,
    "Azure": AzureConnector,
    "GCP": GCPConnector,
    "Microsoft 365": Microsoft365Connector,
    "ServiceNow": ServiceNowConnector,
    "GitHub": GitHubConnector,
    "Jira": JiraConnector,
    "Datadog": DatadogConnector,
    "Dynatrace": DynatraceConnector,
    "New Relic": NewRelicConnector,
    "Splunk": SplunkConnector,
    "Prometheus": PrometheusConnector,
    "Grafana": GrafanaConnector,
    "Slack": SlackConnector,
    "Zoom": ZoomConnector,
    "OpenAI": OpenAIConnector,
    "GitHub Copilot": CopilotConnector,
}


def get_connector(name: str, credentials: dict[str, Any] | None = None, org_id: str | None = None):
    connector_class = CONNECTOR_CLASSES.get(name)
    if not connector_class:
        raise KeyError(f"Unknown connector: {name}")
    return connector_class(credentials=credentials, org_id=org_id)


def get_connector_registry() -> list[dict[str, Any]]:
    return [connector.connector_status() for connector in (cls() for cls in CONNECTOR_CLASSES.values())]


def get_connector_status(name: str) -> dict[str, Any]:
    return get_connector(name).connector_status()


def run_connector_sync(name: str) -> list[dict[str, Any]]:
    connector = get_connector(name)
    sync_methods = [
        method_name
        for method_name in dir(connector)
        if method_name.startswith("sync_") and callable(getattr(connector, method_name))
    ]
    return [getattr(connector, method_name)() for method_name in sorted(sync_methods)]
