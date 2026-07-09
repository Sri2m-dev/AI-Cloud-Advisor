"""AWS connector package exports.

The framework-native AWSReferenceConnector is dependency-free and safe for local
runtime validation. Legacy AWS connector classes are exported only when their
optional provider dependencies are installed.
"""

from connectors.aws.reference_connector import AWSReferenceConnector

try:  # pragma: no cover - optional legacy connector dependencies
    from connectors.aws.aws_connector import AWSConnector
except Exception:  # noqa: BLE001
    AWSConnector = None

try:  # pragma: no cover - optional legacy connector dependencies
    from connectors.aws.aws_credential_manager import AWSCredentialManager
except Exception:  # noqa: BLE001
    AWSCredentialManager = None

try:  # pragma: no cover - optional legacy connector dependencies
    from connectors.aws.aws_permission_validator import AWSPermissionValidator
except Exception:  # noqa: BLE001
    AWSPermissionValidator = None

try:  # pragma: no cover - optional legacy connector dependencies
    from connectors.aws.aws_production_connector import AWSProductionConnector
except Exception:  # noqa: BLE001
    AWSProductionConnector = None

__all__ = [
    "AWSConnector",
    "AWSCredentialManager",
    "AWSPermissionValidator",
    "AWSProductionConnector",
    "AWSReferenceConnector",
]
