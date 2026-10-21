"""Immutable two-stage evidence for future authorized selective blind runs."""
from __future__ import annotations
from datetime import datetime,timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from sqlalchemy import select
from app.blind_selective_profile import SelectiveProfile,PROFILE_VERSION,TASK_POLICY_VERSION
from app.document_intelligence_blind_run import canonical_bytes,sha256,PROTECTED
from app.document_intelligence_validation_metrics import database_identity

from app.blind_schema_drift import observe_schema_drift,verify_accepted_drift
from app.blind_environment import storage_identity

FREEZE_VERSION='DI_SELECTIVE_FREEZE_003'


def exclusive_json(path,payload):
    data=canonical_bytes(payload)
    with path.open('xb') as output:
        output.write(data);output.flush();os.fsync(output.fileno())
    return sha256(data)


def read_evidence(path):
    payload=json.loads(path.read_bytes())
    if payload.get('sha256')!=sha256(canonical_bytes(payload.get('payload'))):
        raise ValueError('IMMUTABLE_EVIDENCE_HASH_MISMATCH')
    return payload['payload']


def write_evidence(path,payload):
    return exclusive_json(path,{'payload':payload,'sha256':sha256(canonical_bytes(payload))})


def runtime_preflight(profile):
    """No motor imports, inference, provider HTTP, or corpus access."""
    packages={}
    for name in ('PyMuPDF','SQLAlchemy','alembic','pydantic','pytesseract','paddleocr','paddlepaddle'):
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]=None
    binary=shutil.which('tesseract')
    binary_version=None;effective_tessdata=None;runtime_languages=[];probe_error=None
    if binary:
        try:
            version=subprocess.run([binary,'--version'],capture_output=True,text=True,timeout=5,check=True)
            match=re.search(r'tesseract\s+([\w.-]+)',version.stdout)
            binary_version=match.group(1) if match else None
            langs=subprocess.run([binary,'--list-langs'],capture_output=True,text=True,timeout=5,check=True)
            lines=(langs.stdout+'\n'+langs.stderr).strip().splitlines()
            path_match=re.search(r'"([^"]+)"',lines[0]) if lines else None
            effective_tessdata=path_match.group(1) if path_match else None
            runtime_languages=[line.strip() for line in lines[1:] if re.fullmatch(r'[a-z_]+',line.strip())]
        except (OSError,subprocess.SubprocessError) as exc:
            probe_error=type(exc).__name__
    roots=tuple(dict.fromkeys(filter(None,(effective_tessdata,os.environ.get('TESSDATA_PREFIX'),
        '/opt/homebrew/share/tessdata',str(Path(binary).resolve().parents[1]/'share/tessdata') if binary else None))))
    languages={'es+en':('spa','eng'),'es':('spa',),'en':('eng',)}[profile.ocr.language]
    packs={root:{lang:sha256((Path(root)/(lang+'.traineddata')).read_bytes())
        if (Path(root)/(lang+'.traineddata')).is_file() else None for lang in languages} for root in roots}
    manifest=Path(profile.vision.model_manifest).expanduser()
    digest=None;blobs=False
    if manifest.is_file():
        raw=manifest.read_bytes();digest=sha256(raw)
        value=json.loads(raw)
        # Ollama manifest ancestry is models/manifests/<registry>/<namespace>/<model>/<tag>.
        models=next((parent.parent for parent in manifest.parents if parent.name=='manifests'),None)
        blobs=models is not None and all((models/'blobs'/item['digest'].replace(':','-')).is_file()
            for item in (value['config'],*value['layers']))
    return dict(python=platform.python_version(),python_executable=os.sys.executable,packages=packages,
        ocr_executable=binary,tessdata_candidates=packs,tessdata_environment=os.environ.get('TESSDATA_PREFIX'),
        effective_tessdata=effective_tessdata or 'NOT_RUNTIME_CONFIRMED',
        ocr_binary_version=binary_version,ocr_runtime_languages=runtime_languages,ocr_probe_error=probe_error,
        model_manifest_sha256=digest,model_revision_matches=digest==profile.vision.model_revision,
        model_blobs_present=blobs,service_availability='NOT_PROBED',inference_calls=0,
        ocr_engine_version_declared=profile.ocr.engine_version,
        data_root=os.environ.get('LICITIA_DATA_DIR'),local_ai_enabled=os.environ.get('LICITIA_LOCAL_AI_ENABLED'))


def code_identity(root):
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    tracked=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
    prefixes=(*PROTECTED,'docs/adr/')
    status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=root,text=True).splitlines()
    dirty=[line for line in status if not line.startswith('??') or line[3:].startswith(PROTECTED)]
    if dirty:raise ValueError('CLEAN_COMMITTED_EXECUTION_CODE_REQUIRED')
    required=('docs/adr/0012-task-aware-selective-ocr.md','docs/adr/0013-task-aware-selective-vision.md',
        'docs/adr/0014-blind-selective-execution.md')
    if not all(p in tracked for p in required):raise ValueError('ACCEPTED_ADRS_MUST_BE_COMMITTED')
    hashes={p:sha256((root/p).read_bytes()) for p in tracked if p.startswith(prefixes)}
    return dict(head=head,tracked_clean=True,code_sha256=hashes,
        code_manifest_sha256=sha256(canonical_bytes(hashes)))


def implementation_versions():
    from app.selective_vision_executor import POLICY_VERSION
    from app.ollama_vision import (VISION_STRUCTURE_SCOPE_PROMPT_VERSION,VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION,
        VisionAssistModelPageResponse,VisionAssistModelDetailTranscriptionResponse,OllamaVisionAssistClient)
    from app.document_structure_orchestrator import STRUCTURE_RESOLVER_VERSION
    import inspect
    from app.structured_evidence import POLICY_VERSION as STRUCTURED_POLICY, MANIFEST_VERSION
    from app.perception_sufficiency import POLICY_VERSION as SUFFICIENCY_POLICY
    from app.native_table_relationships import POLICY_VERSION as NATIVE_TABLE_POLICY
    return dict(native_table_relationships=NATIVE_TABLE_POLICY,perception_sufficiency=SUFFICIENCY_POLICY,planner=TASK_POLICY_VERSION,ocr_fingerprint='selective-ocr-v1',vision_fingerprint=POLICY_VERSION,
        vision_task_version=1,logical_scope='scope-logical-v2',structured_evidence=STRUCTURED_POLICY,
        structured_manifest=MANIFEST_VERSION,structural_policy=STRUCTURE_RESOLVER_VERSION,
        structure_prompt=VISION_STRUCTURE_SCOPE_PROMPT_VERSION,detail_prompt=VISION_DETAIL_TRANSCRIPTION_PROMPT_VERSION,
        prompt_implementation_sha256=sha256(inspect.getsource(OllamaVisionAssistClient).encode()),
        structure_schema_sha256=sha256(canonical_bytes(VisionAssistModelPageResponse.model_json_schema())),
        detail_schema_sha256=sha256(canonical_bytes(VisionAssistModelDetailTranscriptionResponse.model_json_schema())))


def create_pre_execution_freeze(db,*,root,output_root,run_id,profile,availability):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):raise ValueError('INVALID_RUN_ID')
    storage=storage_identity()
    identity=code_identity(root)
    database=database_identity(db)
    if (database['database']!=profile.database_name or database['revision']!=profile.alembic_revision
            or database['tender_count'] or database['document_count']):
        raise ValueError('EMPTY_VALIDATION_DATABASE_REQUIRED')
    if availability.get('inference_calls')!=0 or availability!=runtime_preflight(profile):
        raise ValueError('NON_INFERENCE_PREFLIGHT_REQUIRED')
    drift=verify_accepted_drift(observe_schema_drift(db))
    payload=dict(schema_version=FREEZE_VERSION,run_id=run_id,created_at=datetime.now(timezone.utc).isoformat(),
        code=identity,profile=profile.model_dump(mode='json'),versions=implementation_versions(),
        database=database,availability=availability,schema_drift=drift,storage=storage)
    directory=output_root/run_id;directory.mkdir(parents=True,exist_ok=False)
    write_evidence(directory/'pre_execution.json',payload)
    return directory


def verify_execution_identity(directory,root,profile,*,db=None):
    frozen=read_evidence(directory/'pre_execution.json')
    if frozen.get('schema_version')!=FREEZE_VERSION or not isinstance(frozen.get('schema_drift'),dict):
        raise ValueError('CURRENT_DRIFT_FREEZE_CONTRACT_REQUIRED')
    storage=frozen.get('storage')
    if not isinstance(storage,dict) or storage!=storage_identity(expected=storage.get('canonical_data_root')):
        raise ValueError('FROZEN_STORAGE_CONTRACT_REQUIRED')
    if frozen['profile']!=profile.model_dump(mode='json') or frozen['code']!=code_identity(root):
        raise ValueError('FROZEN_CODE_OR_PROFILE_CHANGED')
    if frozen['versions']!=implementation_versions():raise ValueError('POLICY_VERSION_CHANGED')
    verify_accepted_drift(observe_schema_drift(db),frozen=frozen['schema_drift'])
    return frozen


def input_identity(db,*,tender_id):
    storage_identity()
    from app.models import Tender,TenderDocument,DocumentPage,NormalizedContent,PageOcrResult,DocumentVisionAnalysis
    if db.get(Tender,tender_id) is None:raise ValueError('IMPORTED_TENDER_REQUIRED')
    documents=db.scalars(select(TenderDocument).where(TenderDocument.tender_id==tender_id).order_by(TenderDocument.id)).all()
    from app.selective_ocr_executor import _verified_path
    identities=[]
    for document in documents:
        path=_verified_path(document)
        if path.stat().st_size!=document.file_size_bytes:raise ValueError('ORIGINAL_SIZE_MISMATCH')
        identities.append(dict(id=document.id,original_filename=document.original_filename,sha256=document.sha256,size=document.file_size_bytes,
            mime=document.mime_type,revision=document.revision_number))
    ids=[d.id for d in documents]
    pages=db.scalars(select(DocumentPage).where(DocumentPage.document_id.in_(ids)).order_by(DocumentPage.id)).all()
    page_ids=[p.id for p in pages]
    generations=dict(pages=[p.id for p in pages],
        normalized=[n.id for n in db.scalars(select(NormalizedContent).where(NormalizedContent.document_page_id.in_(page_ids)))],
        ocr=[n.id for n in db.scalars(select(PageOcrResult).where(PageOcrResult.document_page_id.in_(page_ids)))],
        vision=[n.id for n in db.scalars(select(DocumentVisionAnalysis).where(DocumentVisionAnalysis.document_id.in_(ids)))])
    return dict(tender_id=tender_id,documents=identities,generations=generations)


def bind_import(db,*,directory,root,profile,tender_id):
    frozen=verify_execution_identity(directory,root,profile,db=db)
    database=database_identity(db)
    if database['database']!=profile.database_name or database['revision']!=profile.alembic_revision or database['tender_count']!=1:
        raise ValueError('ISOLATED_IMPORTED_DATABASE_REQUIRED')
    identity=input_identity(db,tender_id=tender_id)
    if any(identity['generations'].values()):raise ValueError('BIND_BEFORE_CORPUS_EXECUTION')
    return write_evidence(directory/'input_binding.json',dict(run_id=frozen['run_id'],
        pre_execution_sha256=sha256((directory/'pre_execution.json').read_bytes()),input=identity))


def execute_frozen_run(db,*,directory,root,profile,authorized=False,**test_clients):
    if not authorized:raise PermissionError('EXACT_RUN_AUTHORIZATION_REQUIRED')
    frozen=verify_execution_identity(directory,root,profile,db=db)
    binding=read_evidence(directory/'input_binding.json')
    if binding['run_id']!=frozen['run_id'] or binding['pre_execution_sha256']!=sha256((directory/'pre_execution.json').read_bytes()):
        raise ValueError('INPUT_BINDING_MISMATCH')
    database=database_identity(db)
    if database['database']!=profile.database_name or database['revision']!=profile.alembic_revision or database['tender_count']!=1:
        raise ValueError('VALIDATION_DATABASE_CHANGED')
    if input_identity(db,tender_id=binding['input']['tender_id'])!=binding['input']:
        raise ValueError('IMPORTED_INPUT_CHANGED')
    if runtime_preflight(profile)!=frozen['availability']:
        raise ValueError('FROZEN_RUNTIME_CHANGED')
    # Exclusive start marker prohibits a second whole attempt, including failed runs.
    exclusive_json(directory/'EXECUTION_STARTED.json',dict(run_id=frozen['run_id'],started_at=datetime.now(timezone.utc).isoformat()))
    try:
        from app.blind_selective_harness import execute_selective_pipeline
        events=directory/'events';events.mkdir(exist_ok=False)
        def event_sink(event):
            write_evidence(events/(event.id+'.json'),event.model_dump(mode='json'))
        result=execute_selective_pipeline(db,tender_id=binding['input']['tender_id'],profile=profile,
            event_sink=event_sink,**test_clients)
        verify_execution_identity(directory,root,profile,db=db)
        if input_identity(db,tender_id=binding['input']['tender_id'])['documents']!=binding['input']['documents']:
            raise ValueError('ORIGINAL_INPUT_CHANGED_DURING_EXECUTION')
        evidence=dict(run_id=frozen['run_id'],pre_execution_sha256=sha256((directory/'pre_execution.json').read_bytes()),
            input_binding_sha256=sha256((directory/'input_binding.json').read_bytes()),
            snapshot=result.snapshot.model_dump(mode='json'),metrics=result.metrics,
            selective_metrics=result.perception_metrics,providers=[p.model_dump(mode='json') for p in result.providers],
            ended_at=datetime.now(timezone.utc).isoformat())
        digest=write_evidence(directory/'first_pass.json',evidence)
        summary=('# Selective blind first pass '+frozen['run_id']+'\n\nHEAD: '+frozen['code']['head']+
            '\n\nSemantic correctness remains unadjudicated.\n\n```json\n'+
            json.dumps(result.perception_metrics,sort_keys=True,indent=2)+'\n```\n')
        with (directory/'first_pass.md').open('x') as output:output.write(summary)
        exclusive_json(directory/'FROZEN.json',dict(run_id=frozen['run_id'],first_pass_sha256=digest,
            summary_sha256=sha256(summary.encode()),status='FROZEN'))
        return digest
    except BaseException as exc:
        # Never rerun, repair or recertify the same identity. Preserve partial DB/receipts.
        exclusive_json(directory/'BLOCKED.json',dict(run_id=frozen['run_id'],error=type(exc).__name__,detail=str(exc)))
        raise
