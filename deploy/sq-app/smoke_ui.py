import os,json,sys
from pathlib import Path
sys.path.insert(0,'/opt/nexora-ops')
from runtime import secret_environment
os.environ.update(secret_environment(os.environ))
from streamlit.testing.v1 import AppTest
app=AppTest.from_file('/app/app_main.py').run(timeout=30)
errors=[str(e.value)[:400] for e in app.exception]
print(json.dumps({'scope':'Streamlit AppTest script execution, NOT browser/authenticated journey','exceptions':errors,'exception_count':len(errors),'titles':[str(x.value) for x in app.title],'buttons':[str(x.label) for x in app.button],'authenticated':bool(app.session_state.filtered_state.get('authenticated',False))}))
raise SystemExit(1 if errors else 0)
