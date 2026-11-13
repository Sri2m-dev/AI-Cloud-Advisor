import json,urllib.request,urllib.error
results=[]
def request(name,path,expected,method='GET',body=None,headers=None):
 data=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request('http://api:8000'+path,data=data,method=method,headers={'Content-Type':'application/json',**(headers or {})})
 try:
  with urllib.request.urlopen(req,timeout=5) as response:status=response.status;payload=response.read()
 except urllib.error.HTTPError as response:status=response.code;payload=response.read()
 assert status==expected,(name,status)
 results.append({'test':name,'status':status,'expected':expected,'pass':True})
 if name=='readiness':assert json.loads(payload)=={'infrastructure_ready':False,'protected_execution_enabled':False}
request('api_liveness','/health',200)
request('readiness','/ready',503)
request('deferred_cost_route_unavailable','/api/v1/cost',404)
request('empty_account_store_login','/api/v1/auth/login',401,method='POST',body={'username':'not-an-account','password':'not-a-credential','tenant_id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'})
request('protected_approval_without_identity','/api/v1/approvals/list',401)
request('owner_execution_without_identity','/api/v1/auth/owner-operations/execute',401,method='POST',body={})
with urllib.request.urlopen('http://frontend:8501/_stcore/health',timeout=5) as response:assert response.status==200
results.append({'test':'private_frontend_connectivity','status':200,'pass':True})
from services.supabase_client import create_user_auth_client
try:create_user_auth_client();raise AssertionError('Auth unavailable but client created')
except RuntimeError:results.append({'test':'missing_auth_provider_denied','pass':True})
from auth.authenticated_tenant import require_protected_workflow,ProtectedWorkflowUnavailable
try:require_protected_workflow('commit-reconciliation');raise AssertionError('unqualified protected path enabled')
except ProtectedWorkflowUnavailable:results.append({'test':'unqualified_application_reconciliation_denied','pass':True})
print(json.dumps({'scope':'unauthenticated real HTTP and fail-closed imports; not authenticated tenant isolation','status':'PASS','tests':results,'authenticated_users':0,'auth_dependency':'SQ_APP_AUTH_TARGET_UNAVAILABLE'}))
