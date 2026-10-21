"""Controlled loopback UAT lifecycle, independent of blind benchmark machinery."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import platform
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
sys.path.insert(0,str(BACKEND))
from app.local_deployment import RuntimeConfig,load_config,readiness


def run(args, *, env=None, cwd=None, stdout=None):
    return subprocess.run([str(x) for x in args],env=env,cwd=cwd,stdout=stdout,check=True)


def available(port):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',port))


def pg(config, action):
    cluster=config.directory/'postgres'
    args=['pg_ctl','-D',cluster,'-w','-t','30']
    if action=='start':
        if not (cluster/'PG_VERSION').exists():raise ValueError('INITIALIZE_FIRST')
        if (cluster/'PG_VERSION').read_text().strip()!='17':raise ValueError('POSTGRES_17_REQUIRED')
        args += ['-l',config.directory/'postgres.log','-o',shlex.join(['-h','127.0.0.1','-p',str(config.pg_port),'-k',''])]
    elif action=='stop':args += ['-m','fast']
    run([*args,action],env=config.environment(),stdout=subprocess.DEVNULL)


def private_write(path, value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(value,stream,indent=2);stream.write('\n')


def install(config, wheelhouse=None, npm_offline=False):
    if platform.system()!='Darwin' or platform.machine()!='arm64' or sys.version_info[:2]!=(3,13):
        raise ValueError('SUPPORTED_PLATFORM_MACOS_ARM64_PYTHON313')
    if config.python.exists():raise ValueError('ENVIRONMENT_ALREADY_INSTALLED_NO_IMPLICIT_REPAIR')
    run([sys.executable,'-m','venv',config.directory/'venv'])
    command=[config.python,'-m','pip','install','--require-hashes','--only-binary=:all:',
             '-r',BACKEND/'requirements-rc-macos-arm64.lock']
    if wheelhouse:command += ['--no-index','--find-links',str(Path(wheelhouse).resolve())]
    run(command)
    web=config.directory/'frontend'
    shutil.copytree(REPOSITORY/'frontend',web,ignore=shutil.ignore_patterns('node_modules','dist','.env*','*.tsbuildinfo'))
    if subprocess.check_output(['node','--version'],text=True).strip()!='v26.5.0':
        raise ValueError('NODE_26_5_0_REQUIRED')
    if subprocess.check_output(['npm','--version'],text=True).strip()!='11.17.0':
        raise ValueError('NPM_11_17_0_REQUIRED')
    run(['npm','ci',*(['--offline'] if npm_offline else []),'--no-audit','--no-fund'],cwd=web)
    run(['npm','run','build'],cwd=web)


def initialize(config):
    if not config.python.is_file():raise ValueError('INSTALL_FIRST')
    for tool in ['pg_ctl','initdb','createdb','psql']:
        if not shutil.which(tool):raise ValueError('POSTGRES_TOOL_MISSING_'+tool)
    version=subprocess.check_output(['pg_ctl','--version'],text=True)
    if ' 17.' not in version:raise ValueError('POSTGRES_17_REQUIRED')
    available(config.pg_port)
    cluster=config.directory/'postgres'
    if not cluster.exists():
        with tempfile.NamedTemporaryFile(mode='w',dir=config.directory) as password:
            password.write(config.password);password.flush()
            run(['initdb','-D',cluster,'-U','licitia','--auth-local=scram-sha-256',
                 '--auth-host=scram-sha-256','--pwfile',password.name,'--encoding=UTF8','--locale=C'],
                stdout=subprocess.DEVNULL)
    pg(config,'start')
    try:
        env=config.environment()
        found=subprocess.check_output(['psql','-d','postgres','-tAc',"SELECT 1 FROM pg_database WHERE datname='licitia_uat'"],env=env,text=True)
        if found.strip()!='1':run(['createdb','licitia_uat'],env=env)
        run([config.python,'-m','alembic','-c',BACKEND/'alembic.ini','upgrade','head'],env=env,cwd=config.directory)
        result=subprocess.run([config.python,__file__,'--config',config.directory/'runtime.json','check'],env=env)
        if result.returncode:raise ValueError('INITIALIZED_READINESS_FAILED')
    finally:pg(config,'stop')


def process_identity(pid):
    return subprocess.check_output(['ps','-p',str(pid),'-o','lstart=','-o','command='],text=True).strip()


def stop(config):
    path=config.directory/'running.json'
    if not path.exists():raise ValueError('NOT_RUNNING')
    state=json.loads(path.read_bytes())
    if (state['identity']!=process_identity(state['pid']) or 'licitia_local.py' not in state['identity']):
        raise ValueError('PROCESS_IDENTITY_MISMATCH_NO_SIGNAL_SENT')
    os.kill(state['pid'],signal.SIGTERM)
    for _ in range(60):
        if not path.exists():return
        time.sleep(.5)
    raise ValueError('STOP_TIMEOUT_DO_NOT_DELETE_STATE')


def start(config):
    if not (config.directory/'frontend/dist/index.html').is_file():raise ValueError('FRONTEND_BUILD_REQUIRED')
    for port in (config.api_port,config.web_port,config.pg_port):available(port)
    state=config.directory/'running.json';children=[];database_started=False;log=None
    if state.exists():raise ValueError('RUN_STATE_EXISTS_INSPECT_DO_NOT_OVERWRITE')
    private_write(state,dict(pid=os.getpid(),identity=process_identity(os.getpid())))
    def interrupted(*_):raise KeyboardInterrupt
    previous={sig:signal.signal(sig,interrupted) for sig in (signal.SIGTERM,signal.SIGINT)}
    try:
        pg(config,'start');database_started=True
        check=subprocess.run([config.python,__file__,'--config',config.directory/'runtime.json','check'],env=config.environment())
        if check.returncode:raise ValueError('PREFLIGHT_FAILED')
        log=(config.directory/'services.log').open('a')
        commands=[([config.python,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(config.api_port),'--no-access-log'],config.directory),
                  ([config.python,'-m','http.server',str(config.web_port),'--bind','127.0.0.1','--directory',config.directory/'frontend/dist'],config.directory)]
        for cmd,cwd in commands:children.append(subprocess.Popen([str(x) for x in cmd],cwd=cwd,env=config.environment(),stdout=log,stderr=log))
        print('LicitIA local: http://localhost:'+str(config.web_port)+' — status checks dependencies; Ctrl+C stops safely.',flush=True)
        while all(child.poll() is None for child in children):time.sleep(.5)
        raise ValueError('SERVICE_EXITED_INSPECT_LOCAL_LOG')
    except KeyboardInterrupt:pass
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                # Drain in-flight work; never silently SIGKILL a writer.
                child.wait()
        if log:log.close()
        if database_started:pg(config,'stop')
        state.unlink(missing_ok=True)


def selftest(config):
    """Generated source only: physical parser and normal import/Native/normalize API."""
    import hashlib
    import httpx
    import pymupdf
    with tempfile.TemporaryDirectory(prefix='licitia-selftest-') as directory:
        source=Path(directory)/'generated.pdf';output=Path(directory)/'proposal.json'
        with pymupdf.open() as pdf:
            page=pdf.new_page(width=600,height=400)
            xs=[30,90,330,420,510];ys=[40,90,140,190]
            for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
            for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
            rows=[('ITEM','DESCRIPTION','UNIT','QUANTITY'),('41','Supply of widgets','PZA','3'),('42','Supply of brackets','PZA','7')]
            for row,values in enumerate(rows):
                for col,value in enumerate(values):page.insert_text((xs[col]+4,ys[row]+22),value,fontsize=10)
            pdf.save(source)
        run([config.python,'-m','app.camelot_table_worker',source,'1',output],env=config.environment(),cwd=config.directory)
        tables=json.loads(output.read_bytes())
        if not any(t['row_count']==3 and t['column_count']==4 for t in tables):raise ValueError('CAMELOT_PHYSICAL_SELFTEST_FAILED')
        with httpx.Client(base_url=f'http://127.0.0.1:{config.api_port}',trust_env=False,timeout=30) as client:
            r=client.post('/tenders',json={'title':'RC-H1 generated self-test'});r.raise_for_status();tid=r.json()['id']
            with source.open('rb') as stream:r=client.post(f'/tenders/{tid}/documents/import',files=[('files',('generated.pdf',stream,'application/pdf'))])
            r.raise_for_status();did=r.json()[0]['document_id']
            for action in ['extract-pages','normalize']:
                r=client.post(f'/tenders/{tid}/documents/{did}/{action}');r.raise_for_status()
            r=client.get(f'/tenders/{tid}/documents/{did}/content');r.raise_for_status()
            if hashlib.sha256(r.content).hexdigest()!=hashlib.sha256(source.read_bytes()).hexdigest():raise ValueError('SOURCE_PERSISTENCE_FAILED')
        report=dict(status='PASS',tender_id=tid,document_id=did,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),table_shape=[3,4],providers_inferred=0)
        with (config.directory/'selftest.json').open('w') as file:json.dump(report,file,indent=2)
        print(json.dumps(report))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path.home()/'Library/Application Support/LicitiaUAT/runtime.json')
    parser.add_argument('action',choices=['configure','install','init','start','check','status','stop','restart','selftest'])
    parser.add_argument('--wheelhouse',type=Path)
    parser.add_argument('--npm-offline',action='store_true')
    parser.add_argument('--enable-llm',action='store_true')
    parser.add_argument('--pg-port',type=int,default=55432)
    parser.add_argument('--web-port',type=int,default=5173)
    args=parser.parse_args();os.umask(0o077)
    path=args.config.expanduser().absolute()
    if args.action=='configure':
        config=RuntimeConfig(root=str(path.parent.resolve()),password=secrets.token_hex(32),
                             provider_enabled=args.enable_llm,pg_port=args.pg_port,web_port=args.web_port)
        if path.parent.exists() and any(path.parent.iterdir()):
            raise ValueError('EMPTY_NEW_RUNTIME_DIRECTORY_REQUIRED')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.name!='runtime.json':raise ValueError('CONFIG_FILENAME_RUNTIME_JSON_REQUIRED')
        (path.parent/'data').mkdir(exist_ok=True,mode=0o700)
        private_write(path,asdict(config));print('Private configuration created; no services started.');return 0
    config=load_config(path)
    if args.action in {'check','status','selftest'} and Path(sys.prefix)!=config.directory/'venv':
        return subprocess.call([str(config.python),__file__,*sys.argv[1:]],env=config.environment())
    # Cross-command lock: installer/init/start cannot race or mutate a running instance.
    lock=None
    if args.action in {'install','init','start','restart'}:
        if args.action=='restart':stop(config)
        lock=(config.directory/'operation.lock').open('a')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.action=='install':install(config,args.wheelhouse,args.npm_offline)
    elif args.action=='init':initialize(config)
    elif args.action in {'start','restart'}:start(config)
    elif args.action=='stop':stop(config)
    elif args.action=='selftest':selftest(config)
    else:
        result=readiness(config,runtime=args.action=='status');print(json.dumps(result,indent=2))
        return int(result['state']=='FAILED')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        # URLs/passwords and subprocess argv must not be printed on failure.
        print('Local deployment failed: '+(str(exc) if isinstance(exc,ValueError) else type(exc).__name__),file=sys.stderr)
        raise SystemExit(1)
