import hashlib,json,pathlib,subprocess,tarfile,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.audit_release_packaging import sensitive_path,check_content
OUT=ROOT/'docs/release/nexora-sqapp-phase1-2026-11-10'
image='sha256:325b99b9c42d37b4e61b3cc7d22b64d53a36f218452e8450a55396f3b02f8ce3'
base=['docker','--context','desktop-linux']
existing=subprocess.run(base+['inspect','nexora-sqapp-image-inspection-20261110-r4','--format','{{.Image}} {{.State.Status}}'],capture_output=True,text=True)
if existing.returncode==0:
 assert existing.stdout.strip()==image+' created'
 created=subprocess.CompletedProcess([],0,'nexora-sqapp-image-inspection-20261110-r4')
else:
 created=subprocess.run(base+['create','--name','nexora-sqapp-image-inspection-20261110-r4','--network','none','--read-only',image],capture_output=True,text=True,check=True)
process=subprocess.Popen(base+['export',created.stdout.strip()],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
files={}
with tarfile.open(fileobj=process.stdout,mode='r|*') as archive:
 for entry in archive:
  name=entry.name.removeprefix('./')
  if not name.startswith('app/'):continue
  rel=name[4:]
  if not rel:continue
  assert not entry.issym() and not entry.islnk(),'linked app payload'
  assert not sensitive_path(rel),'sensitive app path'
  if entry.isfile():
   payload=archive.extractfile(entry).read();check_content(payload);files[rel]=hashlib.sha256(payload).hexdigest()
assert process.wait()==0
manifest=json.loads((OUT/'candidate-source-manifest-r4.json').read_text())
expected={r['path']:r['sha256'] for r in manifest['files']}
expected['Dockerfile.frontend']=hashlib.sha256((ROOT/'deploy/sq-app/Dockerfile.candidate').read_bytes()).hexdigest()
mismatch=[n for n in files if n not in expected or files[n]!=expected[n]]
missing=sorted(set(expected)-set(files))
assert not mismatch,mismatch
# Docker builder may omit its own build control files from COPY.
assert all(n.startswith('Dockerfile.') for n in missing),missing
for name in ['nexora-dependency-install.json','nexora-dependency-lock.txt']:
 subprocess.run(base+['cp','nexora-sqapp-image-inspection-20261110-r4:/opt/'+name,str(OUT/name)],check=True,capture_output=True)
report=json.loads((OUT/'nexora-dependency-install.json').read_text(encoding='utf-8'))
lock=[]
for package in report['install']:
 h=package['download_info']['archive_info']['hashes']['sha256']
 lock.append(package['metadata']['name']+'=='+package['metadata']['version']+' --hash=sha256:'+h)
(OUT/'requirements-resolved-hashes.txt').write_text('\n'.join(sorted(lock))+'\n')
result={'image':image,'actual_app_files_scanned':len(files),'matching_source_hashes':True,'sensitive_path_or_content_findings':0,'builder_control_files_omitted':missing,'dependency_distributions':len(lock),'inspection_container_started':False,'scope':'bounded path/content credential detection, not proof against every secret encoding'}
(OUT/'image-qualification-r4.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
