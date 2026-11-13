"""Docker Compose CLI schema validation with synthetic inputs; no daemon action."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4

REPORT=Path("docs/release/nexora-v1-m3-2026-11-10/compose-validation")


def main():
    REPORT.mkdir(parents=True,exist_ok=True)
    temporary=Path(".tmp")/("m3-compose-"+uuid4().hex)
    temporary.mkdir(parents=True)
    configuration=temporary/"docker-config"
    configuration.mkdir()
    (configuration/"config.json").write_text("{}")
    placeholder=temporary/"synthetic-managed-placeholder"
    placeholder.write_text("SYNTHETIC_SCHEMA_CHECK_ONLY_NOT_A_SECRET")
    public=temporary/"public.env"
    public.write_text("SUPABASE_URL=https://example.invalid\n")
    paths=[Path("deploy/operations/compose.yaml"),Path("deploy/operations/compose.postgres.yaml"),
           Path("deploy/operations/compose.qualification.yaml")]
    names=set(re.findall(r"\$\{(NEXORA_[A-Z0-9_]+)","\n".join(p.read_text() for p in paths)))
    values={}
    for name in names:
        if name.endswith("_IMAGE"): value="example.invalid/inspected@sha256:"+"a"*64
        elif name.endswith("_FILE"): value=str(placeholder.resolve())
        elif name.endswith("_VOLUME"): value="nexora_synthetic_"+name.lower()
        elif name.endswith("_DIR") or name.endswith("_ROOT"): value=str(temporary.resolve())
        else: value="synthetic"
        values[name]=value
    values.update(NEXORA_PUBLIC_ENV_FILE=str(public.resolve()),NEXORA_SOURCE_ROOT=str(Path.cwd()),
                  NEXORA_PUBLIC_HOST="staging.example.invalid",NEXORA_SUPABASE_URL="https://example.invalid",
                  NEXORA_POSTGRES_DATABASE="nexora_m2c_synthetic",NEXORA_EXTERNAL_PROBES_ENABLED="false",
                  NEXORA_SCHEDULED_JOBS_ENABLED="false",NEXORA_ENABLED_PERIODIC_JOBS="")
    envfile=temporary/"compose.env"
    envfile.write_text("\n".join(f"{key}={value}" for key,value in sorted(values.items()))+"\n")
    docker_binary=shutil.which("docker")
    plugin=Path(docker_binary).parents[1]/"cli-plugins"/"docker-compose.exe" if docker_binary and os.name=="nt" else None
    prefix=[str(plugin)] if plugin and plugin.is_file() else ["docker","--config",str(configuration.resolve()),"compose"]
    command=[*prefix,"--env-file",str(envfile.resolve()),
             "-f","docker-compose.production.yml","-f","deploy/operations/compose.postgres.yaml",
             "-f","deploy/operations/compose.qualification.yaml","--profile","*","config","--format","json"]
    try:
        child_env={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","COMSPEC"}}
        child_env.update(DOCKER_CONFIG=str(configuration.resolve()),COMPOSE_DISABLE_ENV_FILE="1")
        result=subprocess.run(command,capture_output=True,text=True,timeout=45,env=child_env)
    except (OSError,subprocess.TimeoutExpired):
        metadata={"status":"CLI_UNAVAILABLE_OR_TIMEOUT","containers_executed":False}
        (REPORT/"result.json").write_text(json.dumps(metadata,indent=2)+"\n")
        print(json.dumps(metadata))
        return 1
    (REPORT/"compose-config.json").write_text(result.stdout)
    (REPORT/"stderr.log").write_text(result.stderr)
    metadata={"status":"PASS" if result.returncode==0 else "FAILED","command":command,
              "synthetic_inputs":True,"environment_sanitized":True,"docker_daemon_accessed":False,"containers_executed":False,
              "database_connections":False,"config_sha256":hashlib.sha256(result.stdout.encode()).hexdigest()}
    (REPORT/"result.json").write_text(json.dumps(metadata,indent=2)+"\n")
    print(json.dumps(metadata))
    return result.returncode


if __name__=="__main__": raise SystemExit(main())
