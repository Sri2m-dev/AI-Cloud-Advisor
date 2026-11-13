import copy,importlib.util,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'deploy/operations'))
spec=importlib.util.spec_from_file_location('sqapp_smoke',ROOT/'deploy/sq-app/unauthenticated_smoke.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DenialTests(unittest.TestCase):
 def setUp(self):
  self.c=json.loads((ROOT/'deploy/sq-app/compose.unauthenticated.yaml').read_text())
  self.env=dict(self.c['services']['frontend']['environment'])
 def denied(self,key,value):
  self.env[key]=value
  with self.assertRaises(ValueError):m.validate(self.env)
 def test_provider_cannot_be_activated(self):self.denied('SUPABASE_URL','https://not-an-authorized-endpoint.invalid')
 def test_key_cannot_be_injected(self):self.denied('SUPABASE_ANON_KEY','unapproved')
 def test_no_accounts(self):self.denied('API_USERS_JSON','{"user":{}}')
 def test_no_development_mode(self):self.denied('ENVIRONMENT','development')
 def test_no_mock_auth(self):self.denied('AUTH_MODE','mock')
 def test_no_jobs(self):self.denied('NEXORA_SCHEDULED_JOBS_ENABLED','true')
 def test_scope_required(self):self.denied('NEXORA_SQAPP_SCOPE','other')
 def test_disabled_scheduler_does_not_import_legacy_tasks(self):
  import subprocess
  code="import os,sys; os.environ['ENVIRONMENT']='production'; import backend.jobs.scheduler as s; assert 'backend.jobs.tasks' not in sys.modules;\ntry: s.start_scheduler()\nexcept RuntimeError: pass\nelse: raise AssertionError('production scheduler enabled')\nassert 'backend.jobs.tasks' not in sys.modules"
  subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-B','-c',code],cwd=ROOT,check=True,capture_output=True)
 def test_private_network_only(self):
  self.assertTrue(self.c['networks']['private']['internal'])
  for name in ['frontend','api','redis']: self.assertEqual(self.c['services'][name]['networks'],['private'])
  self.assertEqual(self.c['services']['nginx']['networks'],['private','ingress'])
  for name,s in self.c['services'].items():
   if name!='nginx':self.assertNotIn('ports',s)
  self.assertEqual(self.c['services']['nginx']['ports'],['127.0.0.1:18513:8443'])
 def test_no_sqdb_or_auth_endpoint(self):
  self.assertNotIn('postgres',self.c['services'])
  self.assertNotIn('supabase',self.c['services'])
  self.assertTrue(all(v['name'].startswith('nexora-sqapp-local-20261110_') for v in self.c['volumes'].values()))
if __name__=='__main__':unittest.main()
