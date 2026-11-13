"""Authorized SQ-APP first startup only; refuses existing project resources."""
import json,pathlib,socket,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=ROOT/'docs/release/nexora-sqapp-phase1-2026-11-10'
BASE=['docker','--context','desktop-linux'];PROJECT='nexora-sqapp-local-20261110'
def run(args):return subprocess.run(BASE+args,capture_output=True,text=True,check=True).stdout.strip()
assert run(['context','show'])=='desktop-linux'
assert not run(['ps','-a','--filter','label=com.docker.compose.project='+PROJECT,'--format','{{.Names}}'])
assert not run(['network','ls','--filter','name=^'+PROJECT+'_private$','--format','{{.Name}}'])
c=json.loads((ROOT/'deploy/sq-app/compose.unauthenticated.yaml').read_text())
assert c['networks']['private']['internal']
volumes=[v['name'] for v in c['volumes'].values()]
for name in volumes:
 assert not run(['volume','ls','--filter','name=^'+name+'$','--format','{{.Name}}']), 'existing volume refused'
with socket.socket() as probe:probe.bind(('127.0.0.1',18513))
compose=BASE+['compose','--env-file','C:/Nexora-Staging/sqapp-20261110/references.env','-p',PROJECT,'-f','deploy/sq-app/compose.unauthenticated.yaml']
subprocess.run(compose+['config','--quiet'],cwd=ROOT,check=True)
for name in volumes:
 assert run(['volume','create','--label','nexora.scope=sqapp-synthetic-disposable',name])==name
(OUT/'startup-preflight.json').write_text(json.dumps({'context':'desktop-linux','project':PROJECT,'fresh_volumes':volumes,'network':'nexora-sqapp-local-20261110_private','port':18513,'auth_dependency':'SQ_APP_AUTH_TARGET_UNAVAILABLE','accounts':0,'external_egress':False,'sqdb_resources_reused':False},indent=2)+'\n')
with (OUT/'startup.log').open('w',encoding='utf-8') as log:
 result=subprocess.run(compose+['up','-d','--no-build','--pull','never','--wait','--wait-timeout','90'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
(OUT/'startup-result.json').write_text(json.dumps({'exit':result.returncode,'auth':'UNAVAILABLE','protected_execution':'DISABLED'})+'\n')
print(json.dumps({'startup_exit':result.returncode}))
raise SystemExit(result.returncode)
