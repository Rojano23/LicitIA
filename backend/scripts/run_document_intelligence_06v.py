"""Prepare identity/DB checks or freeze an already-authorized production run. No pipeline/provider execution."""
from __future__ import annotations
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.document_intelligence_blind_run import capture_code_identity, FirstPass, ExecutionLog, freeze_first_pass, load_config, canonical_bytes, sha256
from app.document_intelligence_validation_metrics import database_identity, snapshot_tender, collect_metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'evals/document_intelligence_06v_config_v1.json')
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--authorized-import', action='store_true')
    parser.add_argument('--tender-id')
    parser.add_argument('--run-id')
    parser.add_argument('--started-at', help='Actual pipeline start timestamp, ISO8601 with timezone')
    parser.add_argument('--ended-at', help='Actual pipeline end timestamp, ISO8601 with timezone')
    parser.add_argument('--start-identity', type=Path, help='Clean pre-import preflight output captured before corpus opening')
    parser.add_argument('--execution-log', type=Path, help='Actual first-pass operational ledger, including failed attempts without persisted artifacts')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'reports/blind_runs')
    args = parser.parse_args(argv)
    if not args.preflight and (not args.authorized_import or not all((args.tender_id, args.run_id,
            args.started_at, args.ended_at, args.start_identity, args.execution_log))):
        raise PermissionError('Explicit future authorized import and actual run metadata required before database access')
    config = load_config(args.config)
    url = make_url(args.database_url)
    if url.database != config.database_name or url.host not in {None, 'localhost', '127.0.0.1'}:
        raise ValueError('Dedicated local validation DB required')
    identity = capture_code_identity(ROOT.parent, args.config, require_clean=not args.preflight)
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            database = database_identity(db)
            if database['revision'] != config.alembic_revision:
                raise ValueError('Wrong database revision')
            if args.preflight:
                if args.tender_id or database['tender_count'] or database['document_count']:
                    raise ValueError('Preflight requires empty database; no corpus inspection allowed')
                print(json.dumps({'code': identity, 'database': database, 'provider_calls': 0}, indent=2))
                return 0
            start = json.loads(args.start_identity.read_bytes())
            if start['code']['protected_dirty'] or start['database']['tender_count'] or start['database']['document_count']:
                raise ValueError('Pre-import identity must record clean code and empty validation DB')
            for key in ('commit','config_sha256','code_manifest_sha256','alembic_revision'):
                if start['code'][key] != identity[key]:
                    raise ValueError('Code/config changed after pre-import freeze')
            if start['database']['database'] != config.database_name or start['database']['revision'] != config.alembic_revision:
                raise ValueError('Pre-import database identity mismatch')
            snapshot = snapshot_tender(db, args.tender_id, authorized_import=True)
            ledger = ExecutionLog.model_validate_json(args.execution_log.read_bytes())
            if ledger.run_id != args.run_id or ledger.started_at != datetime.fromisoformat(args.started_at) or ledger.ended_at != datetime.fromisoformat(args.ended_at):
                raise ValueError('Execution ledger identity/timestamps mismatch')
            snapshot = snapshot.__class__.model_validate({**snapshot.model_dump(),
                'providers':(*snapshot.providers,*ledger.providers), 'errors':(*snapshot.errors,*ledger.errors)})
            artifact_hashes = {f'provider:{p.id}': sha256(canonical_bytes(p)) for p in snapshot.providers}
            artifact_hashes['execution_log'] = sha256(args.execution_log.read_bytes())
            artifact_hashes['pre_import_identity'] = sha256(args.start_identity.read_bytes())
            artifact_hashes.update({f'document:{r.id}': r.provenance['sha256'] for r in snapshot.records if r.domain == 'DOCUMENTS'})
            violations = tuple(f'UNAUTHORIZED_PROVIDER_CALL:{p.id}' for p in ledger.providers
                if p.source_method in {'OCR','VISION'} and p.calls)
            report = FirstPass(run_id=args.run_id, started_at=datetime.fromisoformat(args.started_at), ended_at=datetime.fromisoformat(args.ended_at),
                code_identity=identity, database_identity=database, snapshot=snapshot, metrics=collect_metrics(snapshot), errors=snapshot.errors,
                artifact_hashes=artifact_hashes, execution_plan_violations=violations)
            print(json.dumps(freeze_first_pass(report, args.output_root), indent=2))
    finally:
        engine.dispose()
    return 0

if __name__ == '__main__': raise SystemExit(main())
