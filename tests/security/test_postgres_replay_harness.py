from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.test_only_postgres_replay import (
    APPROVED_IMAGE,
    CATALOG_ASSERTION_IDS,
    CATALOG_ASSERTIONS,
    CATALOG_POLICY_IDS,
    CONTAINER_PREFIX,
    OWNERSHIP_LABEL,
    SYNTHETIC_TENANT_ASSERTIONS,
    ReplayError,
    ReplayHarness,
    build_container_args,
    load_manifest,
    validate_container_configuration,
    validate_image_ref,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
TEST_CONTAINER = f"{CONTAINER_PREFIX}0123456789abcdef"
TEST_CONTAINER_ID = "a" * 64
TEST_INVOCATION_ID = "b" * 32
LOCAL_ENDPOINT = "npipe:////./pipe/docker_engine"


def result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class FakeDocker:
    def __init__(
        self,
        *,
        endpoint: str = LOCAL_ENDPOINT,
        endpoint_sequence: list[str] | None = None,
        startup: str = "success",
        returned_id: str = TEST_CONTAINER_ID,
        owned_rows: list[str] | None = None,
        fail_stage: str | None = None,
        cleanup_failure: bool = False,
        environment: dict[str, str] | None = None,
        catalog_stderr: str = "private catalog detail",
    ) -> None:
        self.endpoint = endpoint
        self.endpoint_sequence = endpoint_sequence or []
        self.endpoint_inspections = 0
        self.startup = startup
        self.returned_id = returned_id
        self.owned_rows = owned_rows
        self.fail_stage = fail_stage
        self.cleanup_failure = cleanup_failure
        self.environment = environment or {}
        self.catalog_stderr = catalog_stderr
        self.commands: list[tuple[list[str], dict]] = []
        self.container_created = False
        self.container_name = TEST_CONTAINER
        self.invocation_id = TEST_INVOCATION_ID

    def __call__(self, args, **kwargs):
        args = list(args)
        self.commands.append((args, kwargs))
        expected_environment = {
            key: value
            for key, value in self.environment.items()
            if not key.upper().startswith("DOCKER_")
        }
        assert kwargs["env"] == expected_environment

        if args[:3] == ["docker", "context", "show"]:
            return result(stdout="desktop-linux\n")
        if args[:3] == ["docker", "context", "inspect"]:
            index = self.endpoint_inspections
            self.endpoint_inspections += 1
            host = (
                self.endpoint_sequence[min(index, len(self.endpoint_sequence) - 1)]
                if self.endpoint_sequence
                else self.endpoint
            )
            return result(stdout=json.dumps(host))

        assert args[:2] == ["docker", "--host"]
        assert args[2] == LOCAL_ENDPOINT
        command = args[3:]
        if command[:2] == ["image", "inspect"]:
            return result(stdout=json.dumps([APPROVED_IMAGE]))
        if command[:2] == ["ps", "-a"]:
            if "--filter" in command:
                if self.owned_rows is not None:
                    return result(stdout="\n".join(self.owned_rows))
                if self.container_created:
                    return result(
                        stdout=(f"{TEST_CONTAINER_ID}|{self.container_name}|{self.invocation_id}")
                    )
                return result()
            if self.container_name == "collision":
                return result(stdout=f"{TEST_CONTAINER}\n")
            return result()
        if command and command[0] == "run":
            self.container_name = command[command.index("--name") + 1]
            label = command[command.index("--label") + 1]
            assert label.startswith(f"{OWNERSHIP_LABEL}=")
            self.invocation_id = label.split("=", 1)[1]
            self.container_created = self.startup in {
                "timeout",
                "interrupt",
                "invalid-id-created",
            }
            if self.startup == "timeout":
                raise subprocess.TimeoutExpired(args, kwargs["timeout"])
            if self.startup == "interrupt":
                raise KeyboardInterrupt
            if self.startup == "failure":
                return result(returncode=125, stderr="private diagnostic")
            if self.startup == "invalid-id":
                return result(stdout="")
            if self.startup == "invalid-id-created":
                return result(stdout="short-id")
            return result(stdout=self.returned_id)
        if command and command[0] == "inspect":
            target_id = command[-1]
            if target_id != TEST_CONTAINER_ID:
                return result(returncode=1)
            return result(stdout=f"{TEST_CONTAINER_ID}|/{self.container_name}|{self.invocation_id}")
        if command and command[0] == "exec":
            if "pg_isready" in command:
                return result()
            if (
                "--file" in command
                and self.fail_stage == "migration"
                and command[-1].endswith("public_prerequisites.sql")
            ):
                return result(returncode=7, stderr="private SQL output")
            if "--command" in command:
                sql = command[-1]
                if self.fail_stage == "catalog" and "pg_policies" in sql:
                    return result(returncode=7, stderr=self.catalog_stderr)
                if self.fail_stage == "tenant" and "Tenant A read Tenant B" in sql:
                    return result(returncode=7, stderr="private tenant detail")
            return result()
        if command[:2] == ["rm", "--force"]:
            if self.cleanup_failure:
                return result(returncode=1, stderr="private cleanup detail")
            self.container_created = False
            return result()
        raise AssertionError(f"unexpected fake Docker command: {command!r}")


def make_harness(fake: FakeDocker, *, name=TEST_CONTAINER) -> ReplayHarness:
    return ReplayHarness(
        ROOT,
        runner=fake,
        name_factory=lambda: name,
        identity_factory=lambda: TEST_INVOCATION_ID,
        sleeper=lambda _: None,
        environment=fake.environment,
    )


def test_default_deny_requires_explicit_test_authorization():
    fake = FakeDocker()
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="explicit test-only authorization"):
        harness.run(APPROVED_IMAGE, authorize_test_only=False)

    assert fake.commands == []


def test_blocked_manifest_is_accepted_only_as_test_only_input():
    manifest = load_manifest(ROOT)

    assert manifest["status"] == "BLOCKED"
    assert manifest["executable"] is False
    assert manifest["contract"]["postgres_replay"] == (
        "PASS_TEST_ONLY_LOCAL_NETWORK_DISABLED"
    )
    assert validate_manifest(ROOT, manifest)

    changes = (
        ("status", "READY_FOR_REPLAY"),
        ("executable", True),
        ("contract", {**manifest["contract"], "status": "READY_FOR_REPLAY"}),
        ("contract", {**manifest["contract"], "postgres_replay": "PASS"}),
    )
    for key, unsafe_value in changes:
        changed = copy.deepcopy(manifest)
        if key == "contract":
            changed[key] = unsafe_value
        else:
            changed[key] = unsafe_value
        with pytest.raises(ReplayError, match="must remain BLOCKED"):
            validate_manifest(ROOT, changed)


def test_manifest_hash_mismatch_fails_validation():
    manifest = copy.deepcopy(load_manifest(ROOT))
    manifest["steps"][1]["files"][0]["sha256"] = "0" * 64

    with pytest.raises(ReplayError, match="hash mismatch"):
        validate_manifest(ROOT, manifest)


def test_manifest_file_order_mismatch_fails_validation():
    manifest = copy.deepcopy(load_manifest(ROOT))
    files = manifest["steps"][1]["files"]
    files[0], files[1] = files[1], files[0]

    with pytest.raises(ReplayError, match="order"):
        validate_manifest(ROOT, manifest)


def test_additional_postgres_manifest_step_is_rejected():
    manifest = copy.deepcopy(load_manifest(ROOT))
    manifest["steps"].append(
        {"order": 7, "name": "unexpected", "engine": "postgres", "path": "x.sql"}
    )

    with pytest.raises(ReplayError, match="six-step chain"):
        validate_manifest(ROOT, manifest)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda steps: steps[0].update(order=2), "ordering metadata"),
        (lambda steps: steps[0].update(name="wrong"), "unexpected or additional"),
        (lambda steps: steps[2].update(engine="sqlite"), "engine metadata"),
        (lambda steps: steps[3].update(engine="postgres"), "explicitly SQLite"),
    ],
)
def test_incorrect_manifest_step_metadata_is_rejected(mutate, message):
    manifest = copy.deepcopy(load_manifest(ROOT))
    mutate(manifest["steps"])

    with pytest.raises(ReplayError, match=message):
        validate_manifest(ROOT, manifest)


def test_remote_context_endpoint_is_rejected_before_daemon_commands():
    for endpoint in (
        "tcp://docker.example:2376",
        "ssh://docker.example",
        "npipe:////remote/pipe/docker_engine",
    ):
        fake = FakeDocker(endpoint=endpoint)
        harness = make_harness(fake)

        with pytest.raises(ReplayError, match="remote-capable|local named pipe"):
            harness.assert_local_image(APPROVED_IMAGE)

        assert not any(args[:2] == ["docker", "--host"] for args, _ in fake.commands)


@pytest.mark.parametrize(
    "environment",
    [
        {"DOCKER_HOST": "tcp://remote.invalid"},
        {"docker_context": "remote-context"},
        {"DOCKER_TLS_VERIFY": "1"},
        {"DOCKER_CERT_PATH": "C:\\secret"},
        {"DOCKER_API_VERSION": "1.99"},
        {"DOCKER_CONFIG": "C:\\alternate-config"},
    ],
)
def test_endpoint_overrides_are_rejected_without_logging_values(environment):
    fake = FakeDocker(environment=environment)
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="endpoint override"):
        harness.assert_local_image(APPROVED_IMAGE)

    assert not any("remote.invalid" in str(args) for args, _ in fake.commands)
    assert not any(args[:2] == ["docker", "--host"] for args, _ in fake.commands)


def test_endpoint_change_after_initial_verification_fails_before_operation():
    fake = FakeDocker(endpoint_sequence=[LOCAL_ENDPOINT, "tcp://remote.invalid"])
    harness = make_harness(fake)

    harness.assert_local_image(APPROVED_IMAGE)
    image_inspections_before = sum(args[3:5] == ["image", "inspect"] for args, _ in fake.commands)
    with pytest.raises(ReplayError, match="endpoint changed|remote-capable"):
        harness.assert_local_image(APPROVED_IMAGE)

    assert (
        sum(args[3:5] == ["image", "inspect"] for args, _ in fake.commands)
        == image_inspections_before
    )


def test_docker_commands_pin_verified_endpoint_and_sanitize_environment():
    fake = FakeDocker(environment={"PATH": "safe-path", "DOCKER_SCAN_SUGGEST": "1"})
    harness = make_harness(fake)

    harness.assert_local_image(APPROVED_IMAGE)

    docker_calls = [kwargs for args, kwargs in fake.commands if args[:2] == ["docker", "--host"]]
    assert docker_calls
    assert all(kwargs["env"] == {"PATH": "safe-path"} for kwargs in docker_calls)
    assert all(
        args[2] == LOCAL_ENDPOINT for args, _ in fake.commands if args[:2] == ["docker", "--host"]
    )


def test_container_name_collision_is_rejected():
    fake = FakeDocker()
    fake.container_name = "collision"
    fake.commands.clear()
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="already exists"):
        harness.assert_name_available(TEST_CONTAINER)


def test_container_configuration_is_isolated_and_unsafe_mutation_rejected():
    args = build_container_args(ROOT, APPROVED_IMAGE, TEST_CONTAINER, TEST_INVOCATION_ID)

    assert args[0:3] == ["docker", "run", "--detach"]
    validate_container_configuration(args)
    assert "--pull=never" in args
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert "--cap-drop" in args and args[args.index("--cap-drop") + 1] == "ALL"
    assert "--publish" not in args and "-p" not in args
    assert "--volume" not in args and "-v" not in args
    assert not any(value.startswith("type=volume") for value in args)
    mounts = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "--mount"]
    assert len(mounts) == 44
    assert all(value.endswith(",readonly") for value in mounts)
    targets = set()
    for mount in mounts:
        fields = dict(part.split("=", 1) for part in mount.split(",") if "=" in part)
        source = Path(fields["source"])
        assert source.is_relative_to(ROOT.resolve())
        assert source.is_file()
        assert fields["target"].startswith("/inputs/")
        targets.add(fields["target"])
    expected_targets = {f"/inputs/{Path(path).name}" for path in validate_manifest(ROOT)} | {
        "/inputs/auth_prerequisites.sql"
    }
    assert targets == expected_targets

    unsafe = list(args)
    unsafe[unsafe.index("--network") + 1] = "host"
    with pytest.raises(ReplayError, match="runtime configuration is unsafe"):
        validate_container_configuration(unsafe)


@pytest.mark.parametrize(
    "image",
    [
        "postgres:16",
        "postgres@sha256:" + "0" * 64,
        "evil.example/postgres@sha256:" + "1" * 64,
        "public.ecr.aws/supabase/postgres@sha256:" + "2" * 64,
    ],
)
def test_unauthorized_image_is_rejected(image):
    with pytest.raises(ReplayError, match="approved local PostgreSQL digest"):
        validate_image_ref(image)


def test_local_image_digest_must_be_present_without_pull():
    # A failing local inspection is modeled through the runner dispatch.
    def runner(args, **kwargs):
        if args[:3] == ["docker", "context", "show"]:
            return result(stdout="desktop-linux")
        if args[:3] == ["docker", "context", "inspect"]:
            return result(stdout=json.dumps(LOCAL_ENDPOINT))
        return result(returncode=1)

    harness = ReplayHarness(
        ROOT,
        runner=runner,
        environment={},
    )
    with pytest.raises(ReplayError, match="failed"):
        harness.assert_local_image(APPROVED_IMAGE)


def test_successful_replay_path_uses_only_owned_container_cleanup():
    fake = FakeDocker()
    harness = make_harness(fake)

    harness.run(APPROVED_IMAGE, authorize_test_only=True)

    run_args = next(args for args, _ in fake.commands if args[3:4] == ["run"])
    assert f"{OWNERSHIP_LABEL}={TEST_INVOCATION_ID}" in run_args
    removal = next(args for args, _ in fake.commands if args[3:5] == ["rm", "--force"])
    assert removal[-1] == TEST_CONTAINER_ID
    assert all(args[:2] != ["docker", "volume"] for args, _ in fake.commands)


@pytest.mark.parametrize(
    ("startup", "returned_id", "exception"),
    [
        ("timeout", "", ReplayError),
        ("invalid-id-created", "short-id", ReplayError),
    ],
)
def test_uncertain_start_reconciles_exact_owned_label_and_cleans(startup, returned_id, exception):
    fake = FakeDocker(startup=startup, returned_id=returned_id)
    harness = make_harness(fake)

    with pytest.raises(exception, match="startup failed|no valid container ID"):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    removals = [args for args, _ in fake.commands if args[3:5] == ["rm", "--force"]]
    assert removals == [["docker", "--host", LOCAL_ENDPOINT, "rm", "--force", TEST_CONTAINER_ID]]


def test_keyboard_interrupt_reconciles_owned_container_then_propagates():
    fake = FakeDocker(startup="interrupt")
    harness = make_harness(fake)

    with pytest.raises(KeyboardInterrupt):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    assert any(args[3:5] == ["rm", "--force"] for args, _ in fake.commands)


def test_invalid_or_absent_id_without_owned_container_does_not_remove_anything():
    fake = FakeDocker(startup="invalid-id", returned_id="")
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="no valid container ID"):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    assert not any(args[3:5] == ["rm", "--force"] for args, _ in fake.commands)


def test_startup_failure_reconciliation_does_not_remove_unlabelled_container():
    fake = FakeDocker(startup="failure")
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="startup failed"):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    assert not any(args[3:5] == ["rm", "--force"] for args, _ in fake.commands)


def test_ambiguous_ownership_requires_manual_reconciliation_without_removal():
    for row in (
        f"{TEST_CONTAINER_ID}|wrong-name|{TEST_INVOCATION_ID}",
        f"{TEST_CONTAINER_ID}|{TEST_CONTAINER}|wrong-invocation",
    ):
        fake = FakeDocker(startup="timeout", owned_rows=[row])
        harness = make_harness(fake)

        with pytest.raises(ReplayError, match="manual reconciliation required"):
            harness.run(APPROVED_IMAGE, authorize_test_only=True)

        assert not any(args[3:5] == ["rm", "--force"] for args, _ in fake.commands)


def test_cleanup_failure_is_explicit_and_scoped_to_verified_container():
    fake = FakeDocker(cleanup_failure=True)
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="manual reconciliation required"):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    removals = [args for args, _ in fake.commands if args[3:5] == ["rm", "--force"]]
    assert removals == [["docker", "--host", LOCAL_ENDPOINT, "rm", "--force", TEST_CONTAINER_ID]]


@pytest.mark.parametrize("stage", ["catalog", "tenant"])
def test_catalog_or_tenant_assertion_failure_propagates_and_cleans(stage):
    fake = FakeDocker(fail_stage=stage)
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match=f"{stage} assertions failed"):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    assert any(args[3:5] == ["rm", "--force"] for args, _ in fake.commands)


def test_migration_failure_propagates_and_cleans_exact_container():
    fake = FakeDocker(fail_stage="migration")
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="migration 1/43 failed"):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    removals = [args for args, _ in fake.commands if args[3:5] == ["rm", "--force"]]
    assert removals[-1][-1] == TEST_CONTAINER_ID


def test_fixture_is_test_only_and_has_no_real_identity_or_credentials():
    fixture = (ROOT / "tests/fixtures/postgres_replay/auth_prerequisites.sql").read_text()
    lowered = fixture.lower()

    for required in (
        "create role anon",
        "create role authenticated",
        "create role service_role",
        "create schema auth",
        "create table auth.users",
        "create function auth.uid()",
        "create function auth.jwt()",
        "create function auth.role()",
    ):
        assert required in lowered
    assert "password" not in lowered
    assert not re.search(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", fixture, re.I)
    assert "not supabase auth" in lowered


def test_catalog_assertions_require_rls_role_predicate_and_clause_contracts():
    for fragment in (
        "relrowsecurity",
        "pg_policies",
        "actual_policy.permissive <> 'PERMISSIVE'",
        "actual_policy.roles <> ARRAY['authenticated']::name[]",
        "using_pattern",
        "check_pattern",
        "u.auth_user_id=(selectauth.uid()",
        r"~\(?org_idisnotnull\)?",
        r"~\(?tenant_idisnotnull\)?",
        r"~org_id=\(select\(?u\.org_id\)?::text\)?(asorg_id)?from(public\.)?users(as)?uwhere",
        "CAT-POLICY-WITH-CHECK",
        "prosecdef",
        "search_path=pg_catalog, public",
        "has_function_privilege",
        "on_auth_user_created",
        "NEXORA_CATALOG_ASSERTION: CAT-POLICY-METADATA:%",
        "NEXORA_CATALOG_ASSERTION: CAT-POLICY-USING-PREDICATE:%",
        "NEXORA_CATALOG_ASSERTION: CAT-POLICY-WITH-CHECK:%",
        "NEXORA_CATALOG_ASSERTION: CAT-AUTH-UUID-BINDING:%",
    ):
        assert fragment.lower() in CATALOG_ASSERTIONS.lower()


def _report_history_using_patterns() -> list[str]:
    row = re.search(
        r"\('report_history', 'report_history_select_own_org', 'SELECT',\s*" r"'([^']+)',\s*NULL,",
        CATALOG_ASSERTIONS,
    )
    assert row is not None
    return [fragment[1:] for fragment in row.group(1).split("&")]


def _report_history_matches_using_patterns(expression: str) -> bool:
    if re.search(r"(^|[^a-z0-9_])or([^a-z0-9_]|$)", expression.lower()):
        return False
    normalized = re.sub(r"\s+", "", expression).lower()
    return "u.auth_user_id=(selectauth.uid()" in normalized and all(
        re.search(pattern, normalized) for pattern in _report_history_using_patterns()
    )


def _normalized_report_history_migration_policy() -> str:
    migration = (
        ROOT / "supabase/migrations/202610110001_bind_user_profiles_to_auth_uid.sql"
    ).read_text(encoding="utf-8")
    policy = re.search(
        r"create policy report_history_select_own_org.*?using\s*\((.*?)\);",
        migration,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert policy is not None
    return re.sub(r"\s+", "", policy.group(1)).lower()


def test_report_history_select_pattern_matches_exact_migration_predicate():
    policy = _normalized_report_history_migration_policy()
    assert _report_history_matches_using_patterns(policy)
    assert "u.auth_user_id=(selectauth.uid()" in policy


def test_report_history_select_pattern_accepts_deparsed_cast_alias_and_schema_variants():
    policy = _normalized_report_history_migration_policy()
    previous_text_pattern = r"org_id=\(select\(?u\.org_id\)?::textfrom(public\.)?usersuwhere"
    variants_without_alias = (
        policy.replace("u.org_id::text", "(u.org_id)::text"),
        policy.replace("u.org_id::text", "(u.org_id::text)"),
        policy.replace("frompublic.usersuwhere", "fromusersuwhere"),
        policy.replace("frompublic.usersuwhere", "frompublic.usersasuwhere"),
        policy.replace("frompublic.usersuwhere", "fromusersasuwhere"),
        f"(({policy}))",
    )
    alias_on_first_subquery = policy.replace(
        "u.org_id::textfrom",
        "u.org_id::textasorg_idfrom",
        1,
    )
    alias_on_second_subquery = policy.replace(
        "u.org_id::textfrom",
        "u.org_id::textasorg_idfrom",
        2,
    ).replace("u.org_id::textasorg_idfrom", "u.org_id::textfrom", 1)
    aliases_on_both_subqueries = policy.replace(
        "u.org_id::textfrom",
        "u.org_id::textasorg_idfrom",
    )
    variants_with_alias = (
        alias_on_first_subquery,
        alias_on_second_subquery,
        aliases_on_both_subqueries,
        alias_on_first_subquery.replace(
            "u.org_id::textasorg_idfrom",
            "(u.org_id)::textasorg_idfrom",
        ),
        alias_on_second_subquery.replace(
            "u.org_id::textasorg_idfrom",
            "(u.org_id::text)asorg_idfrom",
        ),
        aliases_on_both_subqueries.replace("frompublic.usersuwhere", "fromusersuwhere"),
        f"(({aliases_on_both_subqueries}))",
    )

    assert all(
        _report_history_matches_using_patterns(variant) for variant in variants_without_alias
    )
    assert all(_report_history_matches_using_patterns(variant) for variant in variants_with_alias)
    assert not re.search(previous_text_pattern, variants_without_alias[1])
    assert not re.search(previous_text_pattern, variants_without_alias[3])


def test_policy_using_patterns_accept_rendered_qualification_and_parentheses():
    uuid_scope = r"org_id=\(selectu\.org_idfrom(public\.)?usersuwhere"
    text_scope = r"org_id=\(select\(?u\.org_id\)?::textfrom(public\.)?usersuwhere"
    rendered_forms = (
        "org_id=(selectu.org_idfrompublic.usersuwhereu.auth_user_id=(selectauth.uid()asuid))",
        "org_id=(selectu.org_idfromusersuwhereu.auth_user_id=(selectauth.uid()asuid))",
        "org_id=(select(u.org_id)::textfromusersuwhereu.auth_user_id=(selectauth.uid()asuid))",
    )

    assert re.search(uuid_scope, rendered_forms[0])
    assert re.search(uuid_scope, rendered_forms[1])
    assert re.search(text_scope, rendered_forms[2])


def test_each_policy_using_failure_has_a_distinct_allowlisted_identifier():
    identifiers = re.findall(r"'(public\.[a-z_]+\.[a-z0-9_]+)'", CATALOG_ASSERTIONS)

    assert tuple(identifiers) == CATALOG_POLICY_IDS
    for policy_id in CATALOG_POLICY_IDS:
        assert f"CAT-POLICY-USING-PREDICATE:{policy_id}" in CATALOG_ASSERTION_IDS


def test_using_patterns_reject_missing_tenant_predicate_and_auth_binding():
    complete = _normalized_report_history_migration_policy()
    missing_org_predicate = complete.replace("org_id=(select", "org_id=true", 1)
    missing_tenant_predicate = complete.replace("tenant_id=(select", "tenant_id=true", 1)
    missing_org_non_null = complete.replace("org_idisnotnulland", "", 1)
    missing_tenant_non_null = complete.replace("tenant_idisnotnulland", "", 1)
    missing_auth_binding = complete.replace(
        "u.auth_user_id=(selectauth.uid())", "u.email='private@example.invalid'"
    )

    assert _report_history_matches_using_patterns(complete)
    assert not _report_history_matches_using_patterns(missing_org_predicate)
    assert not _report_history_matches_using_patterns(missing_tenant_predicate)
    assert not _report_history_matches_using_patterns(missing_org_non_null)
    assert not _report_history_matches_using_patterns(missing_tenant_non_null)
    missing_auth_binding = complete.replace(
        "u.auth_user_id=(selectauth.uid())",
        "u.email='private@example.invalid'",
    )
    assert not _report_history_matches_using_patterns(missing_auth_binding)


def test_report_history_or_scope_bypasses_are_rejected_by_catalog_contract():
    weakened = (
        "org_id is not null OR true and tenant_id is not null and "
        "org_id = (select u.org_id::text from public.users u where "
        "u.auth_user_id = (select auth.uid())) and tenant_id = "
        "(select u.org_id::text from public.users u where "
        "u.auth_user_id = (select auth.uid()))"
    )
    or_guard = r"(^|[^a-z0-9_])or([^a-z0-9_]|$)"

    assert "policy_expression ~ '(^|[^a-z0-9_])or([^a-z0-9_]|$)'" in CATALOG_ASSERTIONS
    assert not _report_history_matches_using_patterns(weakened)
    assert re.search(or_guard, weakened.lower())


def test_catalog_contract_rejects_permissive_and_unexpected_policy_behavior():
    assert "actual_policy.permissive <> 'PERMISSIVE'" in CATALOG_ASSERTIONS
    assert "actual_policy.roles <> ARRAY['authenticated']::name[]" in CATALOG_ASSERTIONS
    assert "CAT-UNEXPECTED-POLICY" in CATALOG_ASSERTIONS
    assert "CAT-LEGACY-EMAIL-POLICY" in CATALOG_ASSERTIONS
    assert "CAT-POLICY-METADATA" in CATALOG_ASSERTIONS


def test_unexpected_permissive_policy_failure_propagates_and_cleans_owned_container():
    fake = FakeDocker(
        fail_stage="catalog",
        catalog_stderr="ERROR: NEXORA_CATALOG_ASSERTION: CAT-UNEXPECTED-POLICY",
    )
    harness = make_harness(fake)

    with pytest.raises(ReplayError, match="catalog assertions failed"):
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    assert any(args[3:5] == ["rm", "--force"] for args, _ in fake.commands)


def test_catalog_assertion_failure_reports_only_allowlisted_identifier():
    fake = FakeDocker(
        fail_stage="catalog",
        catalog_stderr=(
            "ERROR: NEXORA_CATALOG_ASSERTION: "
            "CAT-POLICY-USING-PREDICATE:public.report_history.report_history_select_own_org\n"
            "DETAIL: private SQL and customer information"
        ),
    )
    harness = make_harness(fake)

    with pytest.raises(ReplayError) as error:
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    assert "CAT-POLICY-USING-PREDICATE:public.report_history.report_history_select_own_org" in str(
        error.value
    )
    assert "private SQL" not in str(error.value)
    assert "customer information" not in str(error.value)
    assert any(args[3:5] == ["rm", "--force"] for args, _ in fake.commands)


def test_unknown_catalog_error_marker_is_not_reported():
    fake = FakeDocker(
        fail_stage="catalog",
        catalog_stderr=(
            "ERROR: NEXORA_CATALOG_ASSERTION: "
            "CAT-POLICY-USING-PREDICATE:public.secret_table.private_policy\n"
            "DETAIL: private diagnostic"
        ),
    )
    harness = make_harness(fake)

    with pytest.raises(ReplayError) as error:
        harness.run(APPROVED_IMAGE, authorize_test_only=True)

    assert "private_policy" not in str(error.value)
    assert "private diagnostic" not in str(error.value)


def test_synthetic_assertions_cover_both_tenants_and_unbound_principals_for_all_tables():
    for table in (
        "public.users",
        "public.organizations",
        "public.clients",
        "public.recommendations",
        "public.report_history",
        "public.cloud_cost_import",
        "public.cloud_cost_import_part",
        "public.cloud_account_mapping",
        "public.cloud_cost_reconciliation",
    ):
        assert table in SYNTHETIC_TENANT_ASSERTIONS
    for fragment in (
        "SET LOCAL ROLE authenticated",
        "'A'",
        "'B'",
        "'UNBOUND'",
        "'MISSING'",
        "Tenant A read Tenant B row",
        "Tenant B read Tenant A row",
        "principal saw tenant rows",
        "Tenant A wrote a Tenant B recommendation",
        "Tenant A wrote a Tenant B report",
        "do not",
        "Supabase JWT signatures",
        "ROLLBACK;",
    ):
        assert fragment in SYNTHETIC_TENANT_ASSERTIONS
