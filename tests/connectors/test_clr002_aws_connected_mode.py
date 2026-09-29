from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from connectors.aws.aws_credential_manager import (
    AWSConnectedModeConfigurationError,
    AWSCredentialManager,
    safe_aws_error,
    validate_external_id,
    validate_role_arn,
)
from services.aws_connector_service import AWSConnectorService
from services.aws_onboarding_template_service import (
    AWSOnboardingTemplateService,
)

ROLE_ARN = "arn:aws:iam::123456789012:role/NexoraReadOnlyRole"
EXTERNAL_ID = "nexora-abcdefghijklmnopqrstuvwxyz0123456789"


def test_connected_mode_requires_role_arn():
    manager = AWSCredentialManager(
        external_id=EXTERNAL_ID,
        require_assume_role=True,
    )

    with pytest.raises(
        AWSConnectedModeConfigurationError,
        match="Role ARN",
    ):
        manager.session()


def test_connected_mode_rejects_missing_external_id():
    manager = AWSCredentialManager(
        role_arn=ROLE_ARN,
        require_assume_role=True,
    )

    with pytest.raises(
        AWSConnectedModeConfigurationError,
        match="External ID",
    ):
        manager.session()


@pytest.mark.parametrize(
    "role_arn",
    [
        "",
        "123456789012",
        "arn:aws:s3:::bucket",
        "arn:aws:iam::123:role/Test",
        "arn:aws:iam::123456789012:user/Test",
    ],
)
def test_role_arn_validation_rejects_invalid_values(role_arn):
    with pytest.raises(AWSConnectedModeConfigurationError):
        validate_role_arn(role_arn)


def test_role_arn_validation_extracts_customer_account():
    role_arn, account_id = validate_role_arn(ROLE_ARN)

    assert role_arn == ROLE_ARN
    assert account_id == "123456789012"


def test_external_id_is_generated_with_high_entropy():
    first = AWSOnboardingTemplateService.generate_external_id()
    second = AWSOnboardingTemplateService.generate_external_id()

    assert first.startswith("nexora-")
    assert second.startswith("nexora-")
    assert first != second
    assert len(first) >= 40
    assert validate_external_id(first) == first


def test_assume_role_always_supplies_external_id_and_bounded_duration(
    monkeypatch,
):
    sts = MagicMock()
    sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "temporary-access-key",
            "SecretAccessKey": "temporary-secret-key",
            "SessionToken": "temporary-session-token",
        }
    }

    boto_session = MagicMock()

    monkeypatch.setattr(
        "connectors.aws.aws_credential_manager.boto3.client",
        lambda *args, **kwargs: sts,
    )

    monkeypatch.setattr(
        "connectors.aws.aws_credential_manager.boto3.Session",
        lambda *args, **kwargs: boto_session,
    )

    manager = AWSCredentialManager(
        role_arn=ROLE_ARN,
        external_id=EXTERNAL_ID,
        region="ap-south-1",
        require_assume_role=True,
    )

    assert manager.session() is boto_session

    sts.assume_role.assert_called_once_with(
        RoleArn=ROLE_ARN,
        RoleSessionName="nexora-aws-connector",
        ExternalId=EXTERNAL_ID,
        DurationSeconds=3600,
    )


def test_temporary_credentials_are_not_returned_by_connection_contract(
    monkeypatch,
):
    assumed_sts = MagicMock()
    assumed_sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": (
            "arn:aws:sts::123456789012:" "assumed-role/NexoraReadOnlyRole/nexora-aws-connector"
        ),
    }

    assumed_session = MagicMock()
    assumed_session.client.return_value = assumed_sts

    manager = AWSCredentialManager(
        role_arn=ROLE_ARN,
        external_id=EXTERNAL_ID,
        require_assume_role=True,
    )

    monkeypatch.setattr(
        manager,
        "session",
        lambda: assumed_session,
    )

    result = manager.test_connection()

    assert result["status"] == "CONNECTED"

    serialized = str(result)

    assert "SecretAccessKey" not in serialized
    assert "SessionToken" not in serialized
    assert "AccessKeyId" not in serialized
    assert "temporary-secret-key" not in serialized


def test_connection_rejects_identity_from_wrong_account(monkeypatch):
    sts = MagicMock()
    sts.get_caller_identity.return_value = {
        "Account": "999999999999",
        "Arn": "arn:aws:sts::999999999999:assumed-role/Test/session",
    }

    session = MagicMock()
    session.client.return_value = sts

    manager = AWSCredentialManager(
        role_arn=ROLE_ARN,
        external_id=EXTERNAL_ID,
        require_assume_role=True,
    )

    monkeypatch.setattr(manager, "session", lambda: session)

    result = manager.test_connection()

    assert result["status"] == "FAILED"
    assert "does not match" in result["error"]


def test_aws_client_errors_are_sanitized():
    exc = ClientError(
        {
            "Error": {
                "Code": "AccessDenied",
                "Message": (
                    "secret-sensitive-provider-message " "arn:aws:iam::123456789012:role/private"
                ),
            }
        },
        "AssumeRole",
    )

    message = safe_aws_error(exc)

    assert "secret-sensitive-provider-message" not in message
    assert "private" not in message
    assert message == "AWS denied the requested read-only operation."


def test_trust_policy_requires_external_id():
    policy = AWSOnboardingTemplateService.get_trust_policy(
        nexora_aws_account_arn=("arn:aws:iam::111111111111:role/NexoraConnectorPrincipal"),
        external_id=EXTERNAL_ID,
    )

    statement = policy["Statement"][0]

    assert statement["Effect"] == "Allow"
    assert statement["Action"] == "sts:AssumeRole"
    assert statement["Condition"]["StringEquals"]["sts:ExternalId"] == EXTERNAL_ID


def test_customer_iam_policy_contains_no_write_actions():
    policy = AWSOnboardingTemplateService.get_iam_policy()

    actions = [action for statement in policy["Statement"] for action in statement["Action"]]

    forbidden_prefixes = (
        "Create",
        "Put",
        "Update",
        "Delete",
        "Terminate",
        "Run",
        "Start",
        "Stop",
        "Modify",
        "Attach",
        "Detach",
    )

    for action in actions:
        verb = action.split(":", 1)[1]
        assert not verb.startswith(forbidden_prefixes)


def test_service_connected_mode_validation():
    validated = AWSConnectorService.validate_connected_mode_config(
        ROLE_ARN,
        EXTERNAL_ID,
    )

    assert validated["role_arn"] == ROLE_ARN
    assert validated["account_id"] == "123456789012"
    assert validated["external_id"] == EXTERNAL_ID


def test_service_rejects_incomplete_connected_mode_config():
    with pytest.raises(AWSConnectedModeConfigurationError):
        AWSConnectorService.validate_connected_mode_config(
            ROLE_ARN,
            None,
        )
