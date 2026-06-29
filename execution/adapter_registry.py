from __future__ import annotations

from execution.ansible_adapter import AnsibleExecutionAdapter
from execution.aws_adapter import AWSExecutionAdapter
from execution.azure_adapter import AzureExecutionAdapter
from execution.gcp_adapter import GCPExecutionAdapter
from execution.github_actions_adapter import GitHubActionsExecutionAdapter
from execution.mock_adapter import MockExecutionAdapter
from execution.servicenow_adapter import ServiceNowExecutionAdapter
from execution.terraform_adapter import TerraformExecutionAdapter


ADAPTERS = {
    "mock": MockExecutionAdapter,
    "aws": AWSExecutionAdapter,
    "azure": AzureExecutionAdapter,
    "gcp": GCPExecutionAdapter,
    "terraform": TerraformExecutionAdapter,
    "ansible": AnsibleExecutionAdapter,
    "servicenow": ServiceNowExecutionAdapter,
    "github_actions": GitHubActionsExecutionAdapter,
}


def get_adapter(adapter_name: str | None = None):
    adapter_class = ADAPTERS.get(str(adapter_name or "mock").lower(), MockExecutionAdapter)
    return adapter_class()


def adapter_registry_rows() -> list[dict[str, object]]:
    return [
        {
            "Adapter": name,
            "Enabled": adapter_class.enabled,
            "Mode": "Mock-capable" if name == "mock" else "Execution Disabled",
        }
        for name, adapter_class in ADAPTERS.items()
    ]
