"""M3 offline/static and synthetic-file tests. No daemon, DB or alert execution."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.prepare_m2c_qualification import prepare
from scripts.run_m2c_verification import TESTS as M2_TESTS

REPORT = Path("docs/release/nexora-v1-m3-2026-11-10")
INTENTIONAL = {"docker-compose.production.yml", "database/db.py", "backend/main.py", "backend/celery_app.py",
               "backend/celery_tasks.py", "backend/jobs/scheduler.py", "scheduler.py", "scheduler/scheduler_manager.py"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",type=Path,default=REPORT/"offline")
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    prepare(REPORT/"staging-qualification")
    env={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","COMSPEC"}}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",PYTHON_DOTENV_DISABLED="1",PYTHONDONTWRITEBYTECODE="1",
               ENVIRONMENT="development",NEXORA_COMPLIANCE_DB="false")
    command=[sys.executable,"-m","pytest","-q","-p","no:cacheprovider","-p","scripts.m1_offline_guard",
             "--tb=short","--basetemp",str(args.output_dir/"pytest-temp"),"--junitxml",str(args.output_dir/"results.xml"),
             *M2_TESTS,"tests/operations","tests/release/test_postgres_backup_restore.py","tests/jobs/test_recommendation_tenant_scope.py"]
    result=subprocess.run(command,env=env,text=True,capture_output=True)
    (args.output_dir/"pytest.log").write_text(result.stdout+result.stderr,encoding="utf-8")
    print(result.stdout)
    if result.stderr: print(result.stderr)
    baseline=json.loads((REPORT/"preservation-baseline.json").read_text())["sha256"]
    changed=[p for p,h in baseline.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    unexpected=sorted(set(changed)-INTENTIONAL)
    sources=sorted(Path("deploy/operations").glob("*.py"))+[Path(p) for p in INTENTIONAL if p.endswith(".py")]
    sources += [Path(__file__),Path("scripts/validate_m3_compose.py"),*sorted(Path("tests/operations").glob("*.py"))]
    for p in sources: ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
    checks={"baseline_files":len(baseline),"intentional_changes":sorted(set(changed)&INTENTIONAL),
            "unexpected_changes":unexpected,"python_sources_parsed":len(sources),"postgresql_executed":False,
            "docker_containers_executed":False,"live_alerts_sent":False,"test_command":command}
    (args.output_dir/"checks.json").write_text(json.dumps(checks,indent=2)+"\n")
    files=sources+sorted(p for p in Path("deploy/operations").rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files += [Path("docker-compose.production.yml"),*sorted(REPORT.glob("*.md"))]
    (REPORT/"artifact-manifest.json").write_text(json.dumps({"sha256":{p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},indent=2)+"\n")
    print(json.dumps({k:v for k,v in checks.items() if k!="test_command"}))
    return result.returncode or bool(unexpected)


if __name__=="__main__": raise SystemExit(main())
