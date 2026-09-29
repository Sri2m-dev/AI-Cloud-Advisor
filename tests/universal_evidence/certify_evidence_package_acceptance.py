"""Local acceptance runner; oracle access occurs only after product output is frozen.

Run as a module with --package PATH --oracle PATH --output PATH.
Output contains customer findings; retain it only in the authorized local workspace.
"""

import argparse
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from cryptography.fernet import Fernet

parser = argparse.ArgumentParser()
parser.add_argument("--package", type=Path, required=True)
parser.add_argument("--oracle", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = args.output.resolve()
root.mkdir(parents=True, exist_ok=True)
os.environ["ENVIRONMENT"] = "development"
os.environ["NEXORA_DEMO_MODE"] = "false"
os.environ["NEXORA_UNIVERSAL_EVIDENCE_DB"] = str(root / "governance.db")
os.environ["NEXORA_PROSPECT_DATA_ROOT"] = str(root / "prospects")
os.environ["NEXORA_PROSPECT_DATA_KEY"] = Fernet.generate_key().decode()
from services.prospect_data_intake_service import load_governed_bundle  # noqa: E402
from tests.universal_evidence.test_evidence_package_application import (  # noqa: E402
    app_session,
    upload_files,
)
from universal_evidence.pilot.evidence_package import parse_package_manifest  # noqa: E402

package_dir = args.package.resolve()
manifest_bytes = (package_dir / "manifest.json").read_bytes()
manifest = parse_package_manifest(manifest_bytes)
files = (("manifest.json", manifest_bytes),) + tuple(
    (entry.filename, (package_dir / entry.filename).read_bytes()) for entry in manifest.files
)
app = upload_files(app_session(), files)
assert not app.error, [e.value for e in app.error]
result = app.session_state["evidence_package_result"]
assert len(app.dataframe) == 4
assert any(manifest.package_id in str(m.value) for m in app.markdown)
assert any("UNKNOWN" in c.value for c in app.caption)
assert not app.file_uploader
assert app.session_state["active_workspace_context"] == "PROSPECT"
facts = result.runtime.source_fact_service.repository.list_current_facts(
    result.admissions[0].scope.organization_id, result.admissions[0].scope.tenant_id
)
assert load_governed_bundle(app.session_state["prospect_tenant"].tenant_id) == files[1:]
actual = {
    "package_id": result.package_id,
    "findings": [asdict(f) for f in result.intelligence.findings],
    "coverage": asdict(result.coverage),
    "normalization_runs": len(result.normalization_runs),
    "normalized_records": sum(r.processed_count for r in result.normalization_runs),
    "sourcefacts": len(facts),
    "source_types": [s.source_type for s in result.sources],
    "source_rows": {s.source_type: len(s.rows) for s in result.sources},
    "governed_cost": str(result.intelligence.governed_cost),
    "reconciliation_proposals": len(result.runtime.reconciliation.proposals),
    "provenance": all(
        s.mapping_decision_ids and s.normalization_references for s in result.sources
    ),
    "pii_owner_domains": sorted(
        {
            str(row.get("Owner")).split("@")[-1]
            for s in result.sources
            if s.source_type == "inventory"
            for row in s.rows
            if "@" in str(row.get("Owner"))
            and not str(row.get("Owner")).startswith(("=", "+", "-", "@"))
        }
    ),
    "application_uat": "PASS_STREAMLIT_APPTEST_REAL_UPLOAD",
    "encrypted_roundtrip": "PASS",
}
frozen = root / "actual-frozen.json"
frozen.write_text(json.dumps(actual, indent=2), encoding="utf-8")
digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
(root / "actual-frozen.sha256").write_text(digest)
print("ACTUAL_FROZEN_SHA256=" + digest, flush=True)
# Acceptance boundary: the product has completed and actual output is frozen.
oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
code_map = {
    "untagged_resources": "UNTAGGED_COST_RESOURCE",
    "inventory_without_cost": "INVENTORY_RESOURCE_WITHOUT_COST",
    "cost_without_inventory": "COST_RESOURCE_NOT_IN_INVENTORY",
    "cost_account_not_in_org": "COST_ACCOUNT_NOT_IN_ORGANIZATION",
    "suspended_account_in_org": "SUSPENDED_ORGANIZATION_ACCOUNT",
    "app_mapping_unknown_account": "APPLICATION_ACCOUNT_NOT_IN_ORGANIZATION",
}
matrix = {
    key: sorted({f["source_identifier"] for f in actual["findings"] if f["code"] == code})
    == sorted(oracle[key])
    for key, code in code_map.items()
}
missing = [
    {"account": f["source_identifier"], "month": f["billing_period"]}
    for f in actual["findings"]
    if f["code"] == "MISSING_COST_PERIOD"
]
matrix["missing_cost_month"] = missing == [oracle["missing_cost_month"]]
matrix["sanitisation_flags"] = sorted(
    {f["source_identifier"] for f in actual["findings"] if f["code"] == "SANITISATION_REQUIRED"}
) == sorted(v.split(" (")[0] for v in oracle["sanitisation_flags"])
matrix["pii_notice"] = (
    any(
        f["code"] == "PERSONAL_DATA_PRESENT" and f["source_type"] == "inventory"
        for f in actual["findings"]
    )
    and all(domain in oracle["pii_notice"] for domain in actual["pii_owner_domains"])
    and bool(actual["pii_owner_domains"])
)
assert hashlib.sha256(frozen.read_bytes()).hexdigest() == digest
assert all(matrix.values()), matrix
app.run()
assert not app.exception
assert app.session_state["evidence_package_result"].package_id == result.package_id
summary = {k: v for k, v in actual.items() if k not in ("findings", "coverage")}
summary.update(
    oracle_matrix=matrix,
    oracle_matches=sum(matrix.values()),
    oracle_mismatch=0,
    oracle_missing=0,
    frozen_sha256=digest,
    coverage_summary={k: v for k, v in actual["coverage"].items() if k != "concept_coverage"},
    rendered_metrics=[{"label": m.label, "value": m.value} for m in app.metric],
)
(root / "acceptance.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2), flush=True)
