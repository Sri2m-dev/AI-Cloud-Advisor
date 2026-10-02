from connector_auth.auth_manager import AuthenticationManager
from connector_auth.credentials import (
    ConnectorAuthType,
    ConnectorCredential,
    ConnectorCredentialRequest,
)
from connector_auth.providers import CredentialProvider


ROLE_ARN = "arn:aws:iam::123456789012:role/NexoraReadOnlyRole"


class AssumeRoleCredentialProvider(CredentialProvider):
    def load(self, request: ConnectorCredentialRequest) -> ConnectorCredential:
        return ConnectorCredential(
            auth_type=request.auth_type,
            principal=ROLE_ARN,
            metadata=request.metadata,
        )


def test_aws_assume_role_is_not_authenticated_without_real_aws_authentication():
    manager = AuthenticationManager(
        credential_provider=AssumeRoleCredentialProvider()
    )

    request = ConnectorCredentialRequest(
        auth_type=ConnectorAuthType.AWS_ASSUME_ROLE,
        metadata={
            "provider": "AWS",
            "role_arn": ROLE_ARN,
            "external_id": "nexora-test-external-id",
            "region": "us-east-1",
        },
    )

    context = manager.authenticate(request)

    assert context.authenticated is False

def test_credential_manager_uses_explicit_bootstrap_session_for_assume_role():
    from unittest.mock import MagicMock
    from connectors.aws.aws_credential_manager import AWSCredentialManager

    bootstrap_session = MagicMock()
    manager = AWSCredentialManager(
        role_arn=ROLE_ARN,
        external_id="nexora-test-external-id-1234567890",
        bootstrap_session=bootstrap_session,
    )

    manager.session()

    bootstrap_session.client.assert_called_once_with("sts", region_name="us-east-1")

def test_aws_runtime_provider_builds_default_chain_session():
    from unittest.mock import MagicMock
    from connector_auth.aws_runtime import AWSRuntimeSessionProvider

    session_factory = MagicMock()
    bootstrap_session = MagicMock()
    session_factory.return_value = bootstrap_session

    provider = AWSRuntimeSessionProvider(
        mode="default_chain",
        session_factory=session_factory,
    )
    result = provider.session(region="ap-south-1")

    assert result is bootstrap_session
    session_factory.assert_called_once_with(region_name="ap-south-1")

def test_production_connector_forwards_bootstrap_session_to_credential_manager():
    from unittest.mock import MagicMock, patch
    from connectors.aws.aws_production_connector import AWSProductionConnector

    bootstrap_session = MagicMock()
    customer_session = MagicMock()

    with patch("connectors.aws.aws_production_connector.AWSCredentialManager") as manager_cls:
        manager_cls.return_value.session.return_value = customer_session
        connector = AWSProductionConnector(
            ROLE_ARN,
            "nexora-test-external-id-1234567890",
            "ap-south-1",
            commercial_mode=True,
            bootstrap_session=bootstrap_session,
        )

    manager_cls.assert_called_once_with(
        ROLE_ARN,
        "nexora-test-external-id-1234567890",
        "ap-south-1",
        require_assume_role=True,
        bootstrap_session=bootstrap_session,
    )
    assert connector.session is customer_session

def test_aws_connector_service_test_connection_uses_runtime_bootstrap_session():
    from unittest.mock import MagicMock, patch
    from services.aws_connector_service import AWSConnectorService

    bootstrap_session = MagicMock()

    with patch("services.aws_connector_service.AWSRuntimeSessionProvider") as runtime_cls, \
         patch("services.aws_connector_service.AWSProductionConnector") as connector_cls, \
         patch.object(AWSConnectorService, "_upsert_connector_registry"):
        runtime_cls.return_value.session.return_value = bootstrap_session
        connector_cls.return_value.test_connection.return_value = {"status": "CONNECTED"}

        result = AWSConnectorService.test_connection(
            ROLE_ARN,
            "nexora-test-external-id-1234567890",
            "ap-south-1",
        )

    runtime_cls.return_value.session.assert_called_once_with(region="ap-south-1")
    connector_cls.assert_called_once_with(
        ROLE_ARN,
        "nexora-test-external-id-1234567890",
        "ap-south-1",
        commercial_mode=True,
        bootstrap_session=bootstrap_session,
    )
    assert result["status"] == "CONNECTED"

def test_aws_connector_service_build_connector_composes_runtime_identity():
    from unittest.mock import MagicMock, patch
    from services.aws_connector_service import AWSConnectorService

    bootstrap_session = MagicMock()
    production_connector = MagicMock()

    with patch("services.aws_connector_service.AWSRuntimeSessionProvider") as runtime_cls, \
         patch("services.aws_connector_service.AWSProductionConnector") as connector_cls:
        runtime_cls.return_value.session.return_value = bootstrap_session
        connector_cls.return_value = production_connector

        result = AWSConnectorService._build_connector(
            ROLE_ARN,
            "nexora-test-external-id-1234567890",
            "ap-south-1",
        )

    runtime_cls.return_value.session.assert_called_once_with(region="ap-south-1")
    connector_cls.assert_called_once_with(
        ROLE_ARN,
        "nexora-test-external-id-1234567890",
        "ap-south-1",
        commercial_mode=True,
        bootstrap_session=bootstrap_session,
    )
    assert result is production_connector


def test_aws_runtime_provider_rejects_unsupported_mode():
    import pytest
    from connector_auth.aws_runtime import AWSRuntimeSessionProvider

    provider = AWSRuntimeSessionProvider(mode="unsupported_mode")

    with pytest.raises(
        ValueError,
        match="Unsupported AWS runtime identity mode: unsupported_mode",
    ):
        provider.session(region="ap-south-1")

def test_aws_runtime_provider_builds_web_identity_session():
    from unittest.mock import MagicMock
    from connector_auth.aws_runtime import AWSRuntimeSessionProvider

    sts_client = MagicMock()
    sts_client.assume_role_with_web_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "temporary-access-key",
            "SecretAccessKey": "temporary-secret-key",
            "SessionToken": "temporary-session-token",
        }
    }

    sts_factory = MagicMock(return_value=sts_client)
    session_factory = MagicMock()
    bootstrap_session = MagicMock()
    session_factory.return_value = bootstrap_session

    provider = AWSRuntimeSessionProvider(
        mode="web_identity",
        bootstrap_role_arn="arn:aws:iam::123456789012:role/NexoraBootstrapRole",
        web_identity_token="test-oidc-token",
        session_name="nexora-runtime",
        sts_client_factory=sts_factory,
        session_factory=session_factory,
    )

    result = provider.session(region="ap-south-1")

    sts_factory.assert_called_once_with(region_name="ap-south-1")
    sts_client.assume_role_with_web_identity.assert_called_once_with(
        RoleArn="arn:aws:iam::123456789012:role/NexoraBootstrapRole",
        RoleSessionName="nexora-runtime",
        WebIdentityToken="test-oidc-token",
    )
    session_factory.assert_called_once_with(
        aws_access_key_id="temporary-access-key",
        aws_secret_access_key="temporary-secret-key",
        aws_session_token="temporary-session-token",
        region_name="ap-south-1",
    )
    assert result is bootstrap_session

def test_aws_web_identity_requires_bootstrap_role_arn():
    import pytest
    from connector_auth.aws_runtime import AWSRuntimeSessionProvider

    provider = AWSRuntimeSessionProvider(
        mode="web_identity",
        web_identity_token="test-oidc-token",
    )

    with pytest.raises(
        ValueError,
        match="AWS web identity mode requires bootstrap_role_arn",
    ):
        provider.session(region="ap-south-1")


def test_aws_web_identity_requires_token():
    import pytest
    from connector_auth.aws_runtime import AWSRuntimeSessionProvider

    provider = AWSRuntimeSessionProvider(
        mode="web_identity",
        bootstrap_role_arn="arn:aws:iam::123456789012:role/NexoraBootstrapRole",
    )

    with pytest.raises(
        ValueError,
        match="AWS web identity mode requires web_identity_token",
    ):
        provider.session(region="ap-south-1")

def test_aws_connector_service_build_connector_passes_runtime_mode():
    from unittest.mock import MagicMock, patch
    from services.aws_connector_service import AWSConnectorService

    bootstrap_session = MagicMock()

    with patch(
        "services.aws_connector_service.AWSRuntimeSessionProvider"
    ) as runtime_cls, patch(
        "services.aws_connector_service.AWSProductionConnector"
    ):
        runtime_cls.return_value.session.return_value = bootstrap_session

        AWSConnectorService._build_connector(
            ROLE_ARN,
            "nexora-test-external-id-1234567890",
            "ap-south-1",
            runtime_mode="default_chain",
        )

    runtime_cls.assert_called_once_with(
        mode="default_chain",
        bootstrap_role_arn=None,
        web_identity_token=None,
    )

def test_aws_connector_service_composes_web_identity_runtime():
    from unittest.mock import MagicMock, patch
    from services.aws_connector_service import AWSConnectorService

    bootstrap_session = MagicMock()

    with patch(
        "services.aws_connector_service.AWSRuntimeSessionProvider"
    ) as runtime_cls, patch(
        "services.aws_connector_service.AWSProductionConnector"
    ) as connector_cls:
        runtime_cls.return_value.session.return_value = bootstrap_session

        AWSConnectorService._build_connector(
            ROLE_ARN,
            "nexora-test-external-id-1234567890",
            "ap-south-1",
            runtime_mode="web_identity",
            bootstrap_role_arn=(
                "arn:aws:iam::123456789012:role/NexoraBootstrapRole"
            ),
            web_identity_token="test-oidc-token",
        )

    runtime_cls.assert_called_once_with(
        mode="web_identity",
        bootstrap_role_arn=(
            "arn:aws:iam::123456789012:role/NexoraBootstrapRole"
        ),
        web_identity_token="test-oidc-token",
    )

    runtime_cls.return_value.session.assert_called_once_with(
        region="ap-south-1"
    )

    connector_cls.assert_called_once_with(
        ROLE_ARN,
        "nexora-test-external-id-1234567890",
        "ap-south-1",
        commercial_mode=True,
        bootstrap_session=bootstrap_session,
    )

def test_web_identity_token_file_source_reads_runtime_token(tmp_path):
    from connector_auth.runtime_identity import WebIdentityTokenFileSource

    token_file = tmp_path / "runtime-token"
    token_file.write_text(
        "temporary-runtime-oidc-token",
        encoding="utf-8",
    )

    source = WebIdentityTokenFileSource(str(token_file))

    assert source.token() == "temporary-runtime-oidc-token"

def test_web_identity_token_file_source_rejects_empty_token(tmp_path):
    import pytest
    from connector_auth.runtime_identity import WebIdentityTokenFileSource

    token_file = tmp_path / "runtime-token"
    token_file.write_text("   ", encoding="utf-8")

    source = WebIdentityTokenFileSource(str(token_file))

    with pytest.raises(
        ValueError,
        match="Web identity token file contains no token",
    ):
        source.token()


def test_web_identity_token_file_source_rejects_missing_file(tmp_path):
    import pytest
    from connector_auth.runtime_identity import WebIdentityTokenFileSource

    token_file = tmp_path / "missing-runtime-token"
    source = WebIdentityTokenFileSource(str(token_file))

    with pytest.raises(FileNotFoundError):
        source.token()

def test_aws_connector_service_resolves_web_identity_token_file():
    from unittest.mock import MagicMock, patch
    from services.aws_connector_service import AWSConnectorService

    bootstrap_session = MagicMock()

    with patch(
        "services.aws_connector_service.WebIdentityTokenFileSource"
    ) as token_source_cls, patch(
        "services.aws_connector_service.AWSRuntimeSessionProvider"
    ) as runtime_cls, patch(
        "services.aws_connector_service.AWSProductionConnector"
    ):
        token_source_cls.return_value.token.return_value = "runtime-oidc-token"
        runtime_cls.return_value.session.return_value = bootstrap_session

        AWSConnectorService._build_connector(
            ROLE_ARN,
            "nexora-test-external-id-1234567890",
            "ap-south-1",
            runtime_mode="web_identity",
            bootstrap_role_arn=(
                "arn:aws:iam::123456789012:role/NexoraBootstrapRole"
            ),
            web_identity_token_file="/var/run/secrets/nexora/token",
        )

    token_source_cls.assert_called_once_with(
        "/var/run/secrets/nexora/token"
    )
    token_source_cls.return_value.token.assert_called_once_with()

    runtime_cls.assert_called_once_with(
        mode="web_identity",
        bootstrap_role_arn=(
            "arn:aws:iam::123456789012:role/NexoraBootstrapRole"
        ),
        web_identity_token="runtime-oidc-token",
    )