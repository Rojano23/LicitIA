"""Explicit future blind selective preflight/freeze/bind/execute. Never imports a corpus."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('preflight','freeze','bind','execute'))
    parser.add_argument('--profile',required=True,type=Path)
    parser.add_argument('--database-url',required=True)
    parser.add_argument('--data-dir',required=True,type=Path)
    parser.add_argument('--output-root',type=Path,default=ROOT/'reports/blind_selective_runs')
    parser.add_argument('--run-id')
    parser.add_argument('--tender-id')
    parser.add_argument('--authorized-freeze',action='store_true')
    parser.add_argument('--authorized-import',action='store_true')
    parser.add_argument('--authorized-execution',action='store_true')
    args=parser.parse_args(argv)
    if args.action!='preflight' and not args.run_id:
        parser.error('Explicit new/existing frozen run identity required')
    if args.action=='freeze' and not args.authorized_freeze:
        raise PermissionError('Explicit freeze authorization required')
    if args.action=='bind' and (not args.authorized_import or not args.tender_id):
        raise PermissionError('Explicit import authorization and identity required')
    if args.action=='execute' and not args.authorized_execution:
        raise PermissionError('Explicit exact-run provider execution authorization required')
    import re
    if args.run_id and not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.run_id):
        raise ValueError('Safe run identity required')
    from app.blind_environment import establish_environment
    establish_environment(database_url=args.database_url, data_dir=args.data_dir)
    from sqlalchemy.engine import make_url
    url=make_url(args.database_url)
    from app.blind_selective_profile import SelectiveProfile
    from app.blind_selective_freeze import (runtime_preflight,create_pre_execution_freeze,
        bind_import,execute_frozen_run)
    from app.document_intelligence_validation_metrics import database_identity
    from sqlalchemy import create_engine,text
    from sqlalchemy.orm import Session
    profile=SelectiveProfile.model_validate_json(args.profile.read_bytes())
    engine=create_engine(url)
    try:
        with Session(engine) as db:
            if args.action!='execute':db.execute(text('SET TRANSACTION READ ONLY'))
            identity=database_identity(db)
            if identity['revision']!=profile.alembic_revision:raise ValueError('Wrong Alembic revision')
            if args.action=='preflight':
                print(json.dumps(dict(database=identity,runtime=runtime_preflight(profile)),indent=2));return 0
            directory=args.output_root/args.run_id
            if args.action=='freeze':
                directory=create_pre_execution_freeze(db,root=ROOT.parent,output_root=args.output_root,
                    run_id=args.run_id,profile=profile,availability=runtime_preflight(profile))
                print(directory)
            elif args.action=='bind':
                print(bind_import(db,directory=directory,root=ROOT.parent,profile=profile,tender_id=args.tender_id))
            else:
                print(execute_frozen_run(db,directory=directory,root=ROOT.parent,profile=profile,authorized=True))
    finally:engine.dispose()
    return 0


if __name__=='__main__':raise SystemExit(main())
