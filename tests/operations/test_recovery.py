from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from cryptography.fernet import Fernet, InvalidToken
import pytest

from deploy.operations.recovery import package_snapshot, verify_snapshot, restore_files, safe_name, record_backup_status


def snapshot(tmp_path):
    root=tmp_path/"snapshot"
    for directory in ["application","evidence","prospect"]: (root/directory).mkdir(parents=True)
    (root/"database.dump").write_bytes(b"synthetic database dump, not PostgreSQL execution")
    (root/"application/state.db").write_bytes(b"synthetic application bytes")
    (root/"evidence/lifecycle.db").write_bytes(b"synthetic evidence bytes")
    (root/"prospect/source.enc").write_bytes(Fernet(Fernet.generate_key()).encrypt(b"synthetic prospect"))
    return root


def checkpoint():
    return {"mode":"OPERATOR_QUIESCED_CAPTURE","snapshot_id":"synthetic-checkpoint",
            "database_snapshot_id":"synthetic-dump","file_snapshot_id":"synthetic-files",
            "operator_ref":"synthetic-operator","captured_at":datetime.now(timezone.utc).isoformat()}


def test_encrypted_bundle_verified_and_restored_only_to_new_root(tmp_path):
    source=snapshot(tmp_path); artifact=tmp_path/"backup.fernet"; key=Fernet.generate_key()
    result=package_snapshot(source,artifact,key=key,key_id="synthetic-key-id",checkpoint=checkpoint())
    assert result["file_count"]==4
    assert b"synthetic application bytes" not in artifact.read_bytes()
    manifest,files=verify_snapshot(artifact,key=key,key_id="synthetic-key-id")
    assert manifest["checkpoint"]["snapshot_id"]=="synthetic-checkpoint" and len(files)==4
    destination=tmp_path/"restored"
    assert restore_files(artifact,destination,key=key,key_id="synthetic-key-id")["database_restored"] is False
    assert (destination/"application/state.db").read_bytes()==(source/"application/state.db").read_bytes()
    with pytest.raises(ValueError): restore_files(artifact,destination,key=key,key_id="synthetic-key-id")


def test_backup_survives_fresh_python_process_verification(tmp_path):
    source=snapshot(tmp_path); artifact=tmp_path/"backup.fernet"; key=Fernet.generate_key()
    key_file=tmp_path/"synthetic-managed-key"
    key_file.write_bytes(key)
    package_snapshot(source,artifact,key=key,key_id="synthetic-key-id",checkpoint=checkpoint())
    result=subprocess.run([sys.executable,"-m","deploy.operations.recovery","verify","--source",str(artifact),
                           "--key-file",str(key_file),"--key-id","synthetic-key-id"],capture_output=True,text=True)
    assert result.returncode==0 and json.loads(result.stdout)["files_verified"]==4
    assert key.decode() not in result.stdout+result.stderr


def test_wrong_key_or_label_never_creates_restore_target(tmp_path):
    source=snapshot(tmp_path); artifact=tmp_path/"backup"; key=Fernet.generate_key()
    package_snapshot(source,artifact,key=key,key_id="synthetic-key-id",checkpoint=checkpoint())
    with pytest.raises(InvalidToken): restore_files(artifact,tmp_path/"not-created",key=Fernet.generate_key(),key_id="synthetic-key-id")
    assert not (tmp_path/"not-created").exists()
    with pytest.raises(ValueError): verify_snapshot(artifact,key=key,key_id="other-id")


@pytest.mark.parametrize("path", ["../escape","/absolute","C:/file","prospect/../file","prospect/key.key",".env","database.dump/extra"])
def test_path_and_secret_exclusion(path):
    with pytest.raises(ValueError): safe_name(path)


def test_incomplete_stale_or_uncoordinated_snapshot_is_rejected(tmp_path):
    source=snapshot(tmp_path);key=Fernet.generate_key()
    for receipt in [None,checkpoint()|{"mode":"LIVE_COPY"},checkpoint()|{"captured_at":"2000-01-01T00:00:00+00:00"}]:
        with pytest.raises(ValueError): package_snapshot(source,tmp_path/"unused",key=key,key_id="id",checkpoint=receipt)
    (source/"evidence/unsafe.key").write_bytes(b"synthetic-only")
    with pytest.raises(ValueError): package_snapshot(source,tmp_path/"unused",key=key,key_id="id",checkpoint=checkpoint())


def test_backup_failure_preserves_last_success_time(tmp_path):
    status=tmp_path/"status.json"
    record_backup_status(status,True,now=100)
    record_backup_status(status,False,now=200)
    assert json.loads(status.read_text())=={"last_attempt":200,"last_attempt_success":False,"last_success":100}


def test_synthetic_probe_reopens_volume_in_separate_processes(tmp_path):
    for mode in ["write","verify"]:
        result=subprocess.run([sys.executable,"-m","deploy.operations.persistence_probe",mode,str(tmp_path)],capture_output=True,text=True)
        assert result.returncode==0 and json.loads(result.stdout)["status"]=="COMPLETE"


def test_actual_prospect_wrapped_key_survives_backup_and_isolated_file_recovery(tmp_path):
    from services.prospect_data_intake_service import (
        create_prospect_tenant, _tenant_cipher, _write_encrypted, ProspectIntakeError,
    )
    source=tmp_path/"capture"
    for name in ["application","evidence","prospect"]: (source/name).mkdir(parents=True)
    (source/"database.dump").write_bytes(b"synthetic-dump-not-server-validated")
    master=Fernet.generate_key()
    backup_key=Fernet.generate_key()
    tenant=create_prospect_tenant("Synthetic recovery fixture",consent=True,actor="synthetic-operator",
                                  role="finance",root=source/"prospect",key=master)
    cipher=_tenant_cipher(tenant.tenant_id,root=source/"prospect",key=master)
    _write_encrypted(source/"prospect"/tenant.tenant_id/"source.enc",b"synthetic prospect payload",cipher)
    archive=tmp_path/"coordinated.fernet"
    package_snapshot(source,archive,key=backup_key,key_id="synthetic-backup-key",checkpoint=checkpoint())
    destination=tmp_path/"recovered"
    restore_files(archive,destination,key=backup_key,key_id="synthetic-backup-key")
    recovered=_tenant_cipher(tenant.tenant_id,root=destination/"prospect",key=master)
    assert recovered.decrypt((destination/"prospect"/tenant.tenant_id/"source.enc").read_bytes())==b"synthetic prospect payload"
    with pytest.raises(ProspectIntakeError):
        _tenant_cipher(tenant.tenant_id,root=destination/"prospect",key=Fernet.generate_key())
