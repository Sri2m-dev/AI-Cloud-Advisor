"""Offline only: no daemon, containers, SQL, credentials or external connections."""
import hashlib,json,os,pathlib,re,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent

def validate_contract(c):
    assert set(c['services'])=={'postgres','qualification'}
    assert c['name']=='nexora-m3sq-local-20261110'
    server=c['services']['postgres']; runner=c['services']['qualification']
    assert not any(s.get('ports') for s in c['services'].values())
    assert c['networks']['private']['internal'] is True
    assert server['networks']==['private']
    assert runner['network_mode']=='service:postgres'
    assert c['volumes']['postgres_data']=={'external':True,'name':'nexora-m3sq-local-20261110_postgres_data'}
    assert runner['environment']['PGHOST']=='127.0.0.1'
    assert runner['environment']['PGSSLMODE']=='verify-full'
    assert runner['environment']['PGDATABASE']=='nexora_m2c_m3sq_20261110'
    assert runner['command']==['-X','-v','ON_ERROR_STOP=1','-f','/qualification/database/contracts/g08_m2c/qualification/install_and_test.sql']
    assert all(s['pull_policy']=='never' for s in c['services'].values())
    assert all('build' not in s for s in c['services'].values())
    assert 'include' not in c
    assert len(c['secrets'])==5
    for mount in runner['volumes']:
        if isinstance(mount,dict):
            assert mount['read_only'] and not mount['bind']['create_host_path']
    text=json.dumps(c)
    assert 'NEXORA_SUPABASE' not in text and 'docker.sock' not in text
    return True

def main():
    c=json.loads((HERE/'compose.yaml').read_text()); validate_contract(c)
    for name in ['server.sh','client.sh','driver.sh','clean-install.sh']:
        assert b'\r' not in (HERE/name).read_bytes(), 'shell wrappers require LF'
    manifest=json.loads((ROOT/'docs/release/nexora-v1-m3-2026-11-10/staging-qualification/qualification-manifest.json').read_text())
    corrections=json.loads((HERE/'qualification-corrections.json').read_text()) if (HERE/'qualification-corrections.json').exists() else {}
    for name,digest in manifest['sha256'].items():
        if name in corrections:
            fix=corrections[name]
            assert fix['original_sha256']==digest
            assert hashlib.sha256((ROOT/fix['preserved_original']).read_bytes()).hexdigest()==digest
            digest=fix['corrected_sha256']
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    installer=ROOT/'database/contracts/g08_m2c/qualification/install_and_test.sql'
    includes=[(installer.parent/name).resolve() for name in re.findall(r'^\\ir (.+)$',installer.read_text(),re.M)]
    assert len(includes)==12 and all(p.is_file() and p.is_relative_to(ROOT) for p in includes)
    migrations=[ROOT/name for name in manifest['migration_order']]
    assert [p for p in includes if p in migrations]==migrations
    sql='\n'.join(p.read_text() for p in migrations+includes)
    assert not re.search(r'CREATE\s+EXTENSION',sql,re.I)
    compose=pathlib.Path('C:/Program Files/Docker/Docker/resources/cli-plugins/docker-compose.exe')
    assert compose.is_file(),'Compose CLI unavailable'
    (ROOT/'.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sqdb-offline-',dir=ROOT/'.tmp') as temp:
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC'}}
        env.update(COMPOSE_DISABLE_ENV_FILE='1',DOCKER_CONFIG=temp,SQDB_POSTGRES_IMAGE='postgres@sha256:'+'a'*64,SQDB_SOURCE_ROOT=ROOT.as_posix())
        for name in c['secrets']:
            env['SQDB_'+name.upper()+'_FILE']=pathlib.Path(temp,name).as_posix()
        # Deliberately nonexistent synthetic file references: no credentials generated.
        result=subprocess.run([str(compose),'-p',c['name'],'-f',str(HERE/'compose.yaml'),'--profile','qualification','config','--quiet'],env=env,cwd=ROOT,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        env.update(SQDB_DRIVER_IMAGE='python@sha256:'+'b'*64,SQDB_AUTHORIZATION_REFERENCE='OFFLINE-NOT-AUTHORIZATION')
        driver=subprocess.run([str(compose),'-p',c['name'],'-f',str(HERE/'compose.yaml'),'-f',str(HERE/'compose.driver.yaml'),'--profile','driver','config','--quiet'],env=env,cwd=ROOT,capture_output=True,text=True)
        assert driver.returncode==0,driver.stderr
        clean=subprocess.run([str(compose),'-p',c['name'],'-f',str(HERE/'compose.yaml'),'-f',str(HERE/'compose.clean.yaml'),'--profile','clean','config','--quiet'],env=env,cwd=ROOT,capture_output=True,text=True)
        assert clean.returncode==0,clean.stderr
    report={'offline_contract':'PASS','compose_schema':'PASS_BASE_DRIVER_CLEAN_SYNTHETIC_REFERENCES_ONLY','retained_hashes_checked':len(manifest['sha256']),'include_paths_checked':len(includes),'migrations_ordered':len(migrations),'sql_executed':False,'containers_started':False,'image_qualified':False,'external_identity_qualified':False}
    (HERE/'offline-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__': main()
