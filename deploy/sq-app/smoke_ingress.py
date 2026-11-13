import ssl,urllib.request,urllib.error,json,pathlib
context=ssl.create_default_context(cafile='C:/Nexora-Staging/sqapp-20261110/managed/ca-v2.crt')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=context));results=[]
for path,want in [('/health',200),('/',200),('/api',404),('/api/v1/auth/login',404),('/docs',404),('/openapi.json',404),('/metrics',404),('/ready',404),('/admin',404),('/auth',404),('/realms',404)]:
 req=urllib.request.Request('https://127.0.0.1:18513'+path,headers={'Host':'localhost'})
 try:
  with opener.open(req,timeout=5) as response:status=response.status;response.read()
 except urllib.error.HTTPError as response:status=response.code
 assert status==want,(path,status)
 results.append({'path':path,'status':status,'pass':True})
report={'tls':'VERIFIED_LOCAL_CA','host':'localhost','port':18513,'tests':results}
pathlib.Path('docs/release/nexora-sqapp-phase1-2026-11-10/ingress-smoke.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
