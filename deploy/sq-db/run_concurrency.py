"""Live, explicitly authorized SQ-DB only. Not part of offline validation."""
import json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/release/nexora-sqdb-2026-11-10'
BASE=['docker','--context','desktop-linux','compose','--env-file','C:/Nexora-Staging/m3sq-20261110/sqdb.env','-p','nexora-m3sq-local-20261110','-f','deploy/sq-db/compose.yaml','--profile','qualification']
def cmd(name,sql):
 return BASE+['run','--name',name,'--no-deps','qualification','-X','-v','ON_ERROR_STOP=1','-f','/qualification/database/contracts/g08_m2c/qualification/'+sql]
def run():
 setup=subprocess.run(cmd('nexora-m3sq-db-race-setup','race_setup.sql'),capture_output=True,text=True,cwd=ROOT)
 (OUT/'race-setup.log').write_text(setup.stdout+setup.stderr)
 if setup.returncode: raise RuntimeError('race setup failed; no automatic retry')
 with (OUT/'race-a.log').open('w') as f:
  a=subprocess.Popen(cmd('nexora-m3sq-db-race-a','race_a.sql'),stdout=f,stderr=subprocess.STDOUT,cwd=ROOT)
  # Observe the actual granted advisory lock before starting B, not a guessed delay.
  locked=False
  for _ in range(30):
   if a.poll() is not None: break
   query=subprocess.run(['docker','--context','desktop-linux','exec','nexora-m3sq-local-20261110-postgres-1','psql','-U','postgres','-d','nexora_m2c_m3sq_20261110','-Atc',"SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND granted)"],capture_output=True,text=True)
   if query.returncode==0 and query.stdout.strip()=='t': locked=True; break
   time.sleep(.1)
  if not locked:
   a.wait(); raise RuntimeError('overlap not established')
  b=subprocess.run(cmd('nexora-m3sq-db-race-b','race_b.sql'),capture_output=True,text=True,cwd=ROOT)
  (OUT/'race-b.log').write_text(b.stdout+b.stderr)
  acode=a.wait()
 result={'setup_exit':setup.returncode,'lock_observed':locked,'a_exit':acode,'b_exit':b.returncode,'pass':acode==0 and b.returncode==0}
 (OUT/'concurrency.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
 if not result['pass']: raise SystemExit(1)
if __name__=='__main__':run()
