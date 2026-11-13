"""Validate nonsecret references without opening managed secret files."""
import json,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
def check(path):
    values={}
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        key,sep,value=line.partition('=')
        if not sep or key in values: raise ValueError('invalid/duplicate reference')
        values[key]=value
    allowed={'COMPOSE_PROJECT_NAME','DOCKER_CONTEXT','SQDB_SOURCE_ROOT','SQDB_POSTGRES_IMAGE'}|{'SQDB_'+n+'_FILE' for n in ['PASSWORD','SERVER_CERT','SERVER_KEY','CLIENT_CA','PGPASS']}
    allowed |= {'SQDB_DRIVER_IMAGE','SQDB_AUTHORIZATION_REFERENCE'}
    if set(values)-allowed: raise ValueError('unexpected configuration key')
    assert values.get('COMPOSE_PROJECT_NAME')=='nexora-m3sq-local-20261110'
    assert values.get('DOCKER_CONTEXT')=='desktop-linux'
    assert pathlib.Path(values['SQDB_SOURCE_ROOT']).resolve()==ROOT
    assert re.fullmatch(r'[a-z0-9./:_-]+@sha256:[0-9a-f]{64}',values['SQDB_POSTGRES_IMAGE'])
    paths=[]
    for key in sorted(k for k in allowed if k.endswith('_FILE')):
        f=pathlib.Path(values[key])
        assert f.is_absolute() and f.is_file() and not f.is_symlink()
        assert not f.resolve().is_relative_to(ROOT)
        paths.append(f.resolve())
    assert len(set(paths))==5
    return {'references':'PASS_EXISTENCE_ONLY','secret_contents_read':False,'image_qualification':'SEPARATE_EVIDENCE_REQUIRED','tls_and_credentials':'SEPARATE_VERIFICATION_REQUIRED'}
if __name__=='__main__':
    try: print(json.dumps(check(pathlib.Path(sys.argv[1]))))
    except Exception:
        print(json.dumps({'references':'FAIL_MISSING_OR_INVALID_REFERENCE'})); sys.exit(1)
