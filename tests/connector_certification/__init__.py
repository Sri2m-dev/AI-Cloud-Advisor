"""Connector certification tests with lazy legacy-runner exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["CORE_CONNECTORS", "ConnectorCertificationRunner"]

# Pytest imports this directory as the top-level ``connector_certification``
# package in the repository's current import mode. Include the implementation
# package directory so focused tests can resolve its submodules without loading
# optional cloud SDKs from the legacy certification runner.
__path__.append(str(Path(__file__).resolve().parents[2] / "connector_certification"))


def __getattr__(name: str) -> Any:
    """Preserve legacy exports without importing optional cloud SDKs at collection."""

    if name not in __all__:
        raise AttributeError(name)
    from tests.connector_certification import run_connector_certification

    return getattr(run_connector_certification, name)
