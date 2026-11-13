"""SQ-APP liveness only with Auth unavailable; never production activation."""
import json,os,sys
from pathlib import Path
from cryptography.fernet import Fernet
sys.path.insert(0,'/opt/nexora-ops')
from runtime import secret_environment,storage_paths_available

def validate(env):
 if env.get('NEXORA_SQAPP_SCOPE')!='nexora-sqapp-local-20261110:unauthenticated-only':raise ValueError('scope')
 if env.get('ENVIRONMENT')!='production' or env.get('AUTH_MODE')!='supabase':raise ValueError('account mode')
 if any(env.get(k) for k in ['SUPABASE_URL','SUPABASE_KEY','SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY']):raise ValueError('Auth must be absent')
 if json.loads(env.get('API_USERS_JSON','null'))!={}:raise ValueError('no accounts permitted')
 if any(env.get(k,'false').lower()!='false' for k in ['BACKGROUND_JOBS_ENABLED','NEXORA_SCHEDULED_JOBS_ENABLED','NEXORA_DEMO_MODE','PUE_PILOT_DEV_MODE']):raise ValueError('execution disabled')
 for name in ['FERNET_KEY','NEXORA_PROSPECT_DATA_KEY']:Fernet(env[name].encode())
 if env.get('NEXORA_SQAPP_ROLE')=='api' and len(env.get('JWT_SECRET',''))<32:raise ValueError('signing material')
 storage_paths_available(env)

def main():
 env=secret_environment(os.environ);env['NEXORA_SQAPP_ROLE']=sys.argv[1];validate(env)
 commands={'frontend':['streamlit','run','app_main.py','--server.address=0.0.0.0','--server.port=8501'], 'api':['uvicorn','backend.main:app','--host','0.0.0.0','--port','8000']}
 command=commands[sys.argv[1]]
 print('SQ_APP_AUTH_TARGET_UNAVAILABLE: unauthenticated liveness only; protected readiness disabled',flush=True)
 os.execvpe(command[0],command,env)
if __name__=='__main__':
 try:main()
 except Exception:
  print('SQ-APP unauthenticated scope refused',file=sys.stderr);raise SystemExit(78)
