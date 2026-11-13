import ast
import json
from pathlib import Path
import os

from cryptography.fernet import Fernet
import pytest
import strictyaml

from deploy.operations.preflight import validate_structure, validate_inputs, IMAGE_NAMES
from deploy.operations.runtime import secret_environment, validate, render_edge, storage_paths_available

ROOT = Path(__file__).resolve().parents[2]


def configured():
    return {"ENVIRONMENT": "production", "AUTH_MODE": "supabase", "NEXORA_PRODUCT_PROFILE": "v1",
            "BACKGROUND_JOBS_ENABLED": "false",
            "NEXORA_JOB_SCHEDULER": "celery", "SUPABASE_URL": "https://example.invalid",
            "FERNET_KEY": Fernet.generate_key().decode(), "NEXORA_PROSPECT_DATA_KEY": Fernet.generate_key().decode(),
            "NEXORA_APPLICATION_DB": "/var/lib/nexora/application/db", "NEXORA_UNIVERSAL_EVIDENCE_DB": "/var/lib/nexora/evidence/db",
            "NEXORA_PROSPECT_DATA_ROOT": "/var/lib/nexora/prospect", "JWT_SECRET": "synthetic" * 8, "API_USERS_JSON": "{}"}


def test_secret_files_loaded_without_exporting_file_references():
    env = secret_environment({"JWT_SECRET_FILE": "managed", "REDIS_URL_FILE": "broker"},
                             lambda name: "synthetic" if name == "managed" else "redis://redis:6379/0")
    assert env["JWT_SECRET"] == "synthetic" and "JWT_SECRET_FILE" not in env
    assert env["CELERY_BROKER_URL"] == env["REDIS_URL"]


def test_ambiguous_or_empty_secrets_deny():
    with pytest.raises(ValueError): secret_environment({"JWT_SECRET_FILE": "managed", "JWT_SECRET": "other"}, lambda p: "s")
    with pytest.raises(ValueError): secret_environment({"JWT_SECRET_FILE": "managed"}, lambda p: "")


@pytest.mark.parametrize("field,value", [("ENVIRONMENT","development"),("AUTH_MODE","dev"),
    ("NEXORA_PRODUCT_PROFILE","legacy"),
    ("BACKGROUND_JOBS_ENABLED","true"),("NEXORA_JOB_SCHEDULER","apscheduler"),
    ("FERNET_KEY","invalid"),("NEXORA_PROSPECT_DATA_KEY","invalid"),
    ("NEXORA_APPLICATION_DB","/app/db"),("JWT_SECRET","short"),("API_USERS_JSON","[]")])
def test_invalid_operational_startup_fails_closed(field,value):
    with pytest.raises((ValueError,TypeError)): validate("api", configured() | {field:value})


def test_valid_startup_configuration_is_not_business_authorization():
    validate("api", configured())
    with pytest.raises(ValueError): validate("beat", configured())


@pytest.mark.parametrize("role", ["worker", "beat"])
def test_v1_profile_refuses_celery_runtime(role):
    env = configured() | {
        "NEXORA_PRODUCT_PROFILE": "v1",
        "NEXORA_SCHEDULED_JOBS_ENABLED": "true",
    }
    with pytest.raises(ValueError, match="excluded from the V1 profile"):
        validate(role, env)


def test_storage_preflight_never_falls_back_to_workspace(tmp_path):
    env={"NEXORA_APPLICATION_DB":str(tmp_path/"app"/"app.db"),
         "NEXORA_UNIVERSAL_EVIDENCE_DB":str(tmp_path/"evidence"/"evidence.db"),"NEXORA_PROSPECT_DATA_ROOT":str(tmp_path/"prospect")}
    with pytest.raises(ValueError): storage_paths_available(env)
    for name in ["app","evidence","prospect"]: (tmp_path/name).mkdir()
    storage_paths_available(env)


@pytest.mark.parametrize("host", ["host;return 200;", "https://example.com", "a\ninclude x", ""])
def test_ingress_host_cannot_inject_configuration(host,tmp_path):
    with pytest.raises(ValueError): render_edge(host,"@@PUBLIC_HOST@@",tmp_path/"config")


def test_rendered_ingress_denies_unverified_surfaces(tmp_path):
    template=(ROOT/"deploy/operations/nginx.conf.template").read_text()
    output=tmp_path/"nginx.conf"
    render_edge("staging.example.invalid",template,output)
    result=output.read_text()
    assert "@@PUBLIC_HOST@@" not in result and "listen 8443 ssl" in result
    assert "TLSv1.2 TLSv1.3" in result and "proxy_set_header X-Forwarded-Proto https" in result
    for prefix in ["/api", "/metrics", "/ready", "/admin", "/auth", "/docs"]:
        assert prefix in result
    assert "proxy_pass http://fastapi" not in result


def test_compose_internal_boundaries_and_scheduler_ownership():
    cfg=json.loads((ROOT/"deploy/operations/compose.yaml").read_text())
    assert validate_structure(cfg)["protected_execution_enabled"] is False
    assert cfg["services"]["beat"]["depends_on"]["worker"]["condition"] == "service_healthy"
    assert "postgres" not in cfg["services"]
    assert all(v.get("external") is True for v in cfg["volumes"].values())
    assert any("NEXORA_BACKUP_STATUS_DIR" in v for v in cfg["services"]["operations"]["volumes"])
    for path in (ROOT/"deploy/operations/monitoring").glob("*.yml"):
        assert strictyaml.dirty_load(path.read_text(),allow_flow_style=True).data


def test_missing_managed_inputs_are_not_reported_valid(tmp_path):
    env={"NEXORA_"+name+"_IMAGE":"image@sha256:"+"a"*64 for name in IMAGE_NAMES}
    with pytest.raises(ValueError): validate_inputs(env,tmp_path)
    with pytest.raises(ValueError): validate_inputs({},tmp_path)


def test_managed_inputs_are_separate_from_repository_and_public_secret_values(tmp_path):
    import re
    managed=tmp_path/"managed";managed.mkdir()
    secret=managed/"placeholder";secret.write_text("synthetic-only")
    public=managed/"public.env";public.write_text("SUPABASE_URL=https://example.invalid\n")
    status=managed/"backup-status";status.mkdir()
    cfg=json.loads((ROOT/"deploy/operations/compose.yaml").read_text())
    env={"NEXORA_"+name+"_IMAGE":"image@sha256:"+"a"*64 for name in IMAGE_NAMES}
    for item in cfg["secrets"].values():
        name=re.match(r"\$\{(NEXORA_\w+_FILE):",item["file"])[1]
        env[name]=str(secret)
    for index,item in enumerate(cfg["volumes"].values()):
        name=re.match(r"\$\{(NEXORA_\w+_VOLUME):",item["name"])[1]
        env[name]="synthetic_volume_"+str(index)
    env.update(NEXORA_PUBLIC_ENV_FILE=str(public),NEXORA_BACKUP_STATUS_DIR=str(status),NEXORA_BACKUP_ROOT=str(status))
    assert validate_inputs(env,tmp_path/"repository")["runtime_qualified"] is False
    public.write_text("JWT_SECRET=synthetic-not-output\n")
    with pytest.raises(ValueError,match="must not contain credential"):
        validate_inputs(env,tmp_path/"repository")


def test_production_credential_key_never_generated_or_hashed(monkeypatch):
    # Execute the actual function in isolation, without importing legacy DB clients.
    tree=ast.parse((ROOT/"database/db.py").read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_get_fernet")
    namespace={"os":os,"Fernet":Fernet,"FERNET_KEY_ENV":"FERNET_KEY"}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"_get_fernet","exec"),namespace)
    monkeypatch.setenv("ENVIRONMENT","production")
    monkeypatch.delenv("FERNET_KEY",raising=False)
    with pytest.raises(RuntimeError): namespace["_get_fernet"]()
    monkeypatch.setenv("FERNET_KEY","short-passphrase")
    with pytest.raises(RuntimeError): namespace["_get_fernet"]()
    key=Fernet.generate_key()
    monkeypatch.setenv("FERNET_KEY",key.decode())
    token=namespace["_get_fernet"]().encrypt(b"synthetic")
    assert Fernet(key).decrypt(token)==b"synthetic"
