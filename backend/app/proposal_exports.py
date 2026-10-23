"""Version-bound local proposal outputs. Filesystem receipts, no new canonical authority."""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID
from io import BytesIO
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED,BadZipFile
import fcntl,hashlib,json,os,re,shutil,tempfile,unicodedata
from fastapi import HTTPException
from app import proposal_versions as versions
from app.proposal_composition import _stored,_sections,canonical_rows,composition_hash
from app.proposal_readiness import digest,canonical_bytes
from app.proposal_export_contract import ExportContent,ExportSection,ExportRow,ExportColumn,EXPORT_CONTRACT
from app.proposal_export_renderers import RENDERERS
from app.local_recovery import fsync_dir

MAX_FILE=128*1024*1024
MAX_META=80*1024*1024
MAX_PACKAGE=384*1024*1024
FILES={'DOCX':'proposal.docx','XLSX':'proposal.xlsx','PDF':'proposal.pdf'}
MIMES={'DOCX':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
       'XLSX':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','PDF':'application/pdf','ZIP':'application/zip'}
TITLES={'IDENTIFICATION':'Identificación','TECHNICAL_SCOPE':'Alcance técnico','REQUIREMENTS':'Requisitos',
 'REQUESTED_EVIDENCE':'Evidencias solicitadas','ECONOMIC':'Propuesta económica','CLARIFICATIONS':'Aclaraciones',
 'ANNEX_REFERENCES':'Referencias de anexos','NOTES':'Notas'}
COLUMNS={
 'IDENTIFICATION':[('field','Campo'),('value','Valor')],
 'TECHNICAL_SCOPE':[('item','Partida'),('description','Descripción canónica'),('quantity','Cantidad'),('unit','Unidad'),
                    ('offered','Descripción ofrecida'),('status','Declaración'),('comment','Comentario'),('clarification','Aclaración')],
 'REQUIREMENTS':[('reference','Referencia'),('text','Requisito'),('status','Declaración'),('response','Respuesta'),
                 ('comment','Comentario'),('evidence','Evidencia/referencia'),('clarification','Aclaración')],
 'REQUESTED_EVIDENCE':[('reference','Referencia'),('text','Evidencia solicitada'),('status','Declaración'),
                        ('response','Respuesta'),('evidence','Documento/referencia'),('comment','Comentario')],
 'ECONOMIC':[('item','Partida'),('description','Descripción'),('quantity','Cantidad'),('unit','Unidad'),
              ('unit_price','Precio unitario ofertado'),('total','Importe ofertado'),('currency','Moneda')],
 'CLARIFICATIONS':[('kind','Tipo'),('text','Contenido'),('reference','Referencia')],
 'ANNEX_REFERENCES':[('kind','Tipo'),('text','Anexo'),('reference','Referencia')],
 'NOTES':[('text','Nota')],
}


def _string(value):return '' if value is None else str(value)


def stable_content(db,tender_id,version_id,request):
    row=versions._row(db,tender_id,version_id);snapshot=versions._verified(db,row);stored,overlay=_stored(db,row)
    if row.state=='DRAFT':
        if not request.allow_draft:raise HTTPException(409,'FROZEN_PROPOSAL_REQUIRED_OR_EXPLICIT_DRAFT')
        if request.expected_edit_revision!=row.edit_revision or request.expected_composition_revision!=stored.revision:
            raise HTTPException(409,'EXPORT_DRAFT_REVISION_STALE')
    elif request.expected_composition_revision is not None and request.expected_composition_revision!=stored.revision:
        raise HTTPException(409,'EXPORT_COMPOSITION_REVISION_STALE')
    rows=canonical_rows(snapshot,overlay);config=versions.ProposalConfig.model_validate(row.configuration)
    sections=[]
    for setting in _sections(row,overlay):
        if not setting['included']:continue
        kind=setting['type'];items=[]
        for key,source in rows.items():
            if source['section']!=kind:continue
            response=overlay.responses[key].response if key in overlay.responses else None
            if response and not response.included:continue
            c=source['canonical'];r=response.model_dump(mode='json') if response else {}
            values={};group=None;references=[]
            comment='\n'.join(filter(None,[r.get('comment'),('Nota: '+r['note']) if r.get('note') else None]))
            response_text='\n'.join(filter(None,[r.get('text'),('Descripción propuesta: '+r['offered_description']) if r.get('offered_description') else None]))
            association=r.get('external_reference') or ('Documento asociado; referencia en manifiesto' if r.get('document_id') else '')
            if kind=='TECHNICAL_SCOPE':
                values={'item':c['item_reference'],'description':c['description'],'quantity':c['quantity'],'unit':c['unit'],
                    'offered':r.get('offered_description'),'status':r.get('status','PENDING'),
                    'comment':'\n'.join(filter(None,[r.get('text'),comment,association])),
                    'clarification':'\n'.join(filter(None,[r.get('clarification'),r.get('reason')]))}
                references=[c['source'],c['quantity_source']]
            elif kind=='ECONOMIC':
                # Explicit external allowlist. Never serialize the economic response/note or internal pricing inputs.
                values={'item':c['item_reference'],'description':c['description'],'quantity':c['quantity'],'unit':c['unit'],
                    'unit_price':c['offered_unit_price'],'total':c['offered_total'],'currency':c['currency']}
                group=c['currency'];references=[c['source'],c['quantity_source']]
            elif kind in {'REQUIREMENTS','REQUESTED_EVIDENCE'}:
                if c.get('text_state')!='MATERIALIZED':raise HTTPException(409,'SOURCE_LITERAL_UNAVAILABLE_CREATE_NEW_REVISION')
                references=c['materialized_source']['references']
                pages=sorted({ref['page'] for ref in references if ref.get('page') is not None})
                reference='Página '+', '.join(str(p) for p in pages) if pages else 'Referencia en manifiesto'
                values={'reference':reference,'text':c['display_text'],'status':r.get('status','PENDING'),'response':response_text,
                    'comment':comment,'evidence':association,
                    'clarification':'\n'.join(filter(None,[r.get('clarification'),r.get('reason')]))}
                if kind=='REQUESTED_EVIDENCE':values['comment']='\n'.join(filter(None,[comment,r.get('clarification'),r.get('reason')]))
            if values:items.append(ExportRow(key=key,values={k:_string(v) for k,v in values.items()},group=group,
                document_id=r.get('document_id') if kind!='ECONOMIC' else None,source_references=[ref for ref in references if ref]))
        if kind=='IDENTIFICATION':
            pairs=[('TENDER_TITLE','Título del procedimiento',snapshot.payload.projection.tender_title),
                ('PROPOSAL_TITLE','Título de propuesta',config.title),('BIDDER','Participante',config.bidder_name),
                ('BIDDER_REFERENCE','Referencia del participante',config.bidder_reference),('REVISION','Revisión',row.version),
                ('SNAPSHOT_DATE','Base documental al',snapshot.payload.created_at.date().isoformat())]
            items=[ExportRow(key='IDENTIFICATION:'+key,values={'field':label,'value':_string(value)}) for key,label,value in pairs if value is not None]
        for item in overlay.items:
            target='ANNEX_REFERENCES' if item.kind=='ANNEX_REFERENCE' else 'NOTES' if item.kind=='NOTE' else 'CLARIFICATIONS'
            if target==kind:items.append(ExportRow(key='HUMAN:'+str(item.id),values={'kind':item.kind,'text':item.text,
                'reference':item.external_reference or ('Documento asociado; referencia en manifiesto' if item.document_id else '')},
                document_id=str(item.document_id) if item.document_id else None))
        if kind=='NOTES' and config.notes:items.insert(0,ExportRow(key='CONFIGURATION:NOTES',values={'text':config.notes}))
        if kind=='ECONOMIC':items.sort(key=lambda item:(item.group,item.key))
        sections.append(ExportSection(id=setting['id'],title=TITLES[kind],columns=[ExportColumn(key=k,label=label,
            numeric=k in {'quantity','unit_price','total'}) for k,label in COLUMNS[kind]],rows=items))
    for text in [config.title or '',config.bidder_name or '',*[v for section in sections for item in section.rows for v in item.values.values()]]:
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',text):raise HTTPException(422,'EXPORT_UNSUPPORTED_CONTROL_CHARACTER')
    if sum(len(s.rows) for s in sections)>10000:raise HTTPException(422,'EXPORT_ROW_LIMIT')
    receipt=row.freeze_acknowledgements or {}
    content=ExportContent(composition_contract=stored.contract_version,tender_id=tender_id,proposal_id=row.proposal_id,
        version_id=row.id,proposal_version=row.version,proposal_state=row.state,snapshot_id=row.snapshot_id,
        snapshot_sha256=row.snapshot_sha256,composition_sha256=composition_hash(stored),composition_revision=stored.revision,
        frozen_sha256=row.frozen_sha256,proposal_title=config.title or 'Propuesta',bidder_name=config.bidder_name,
        warnings_acknowledged=bool(receipt.get('warnings') and snapshot.payload.projection.warnings),source_state_at_freeze=receipt.get('source_state'),sections=sections)
    if len(canonical_bytes(content.model_dump(mode='json')))>64*1024*1024:raise HTTPException(422,'EXPORT_CONTENT_LIMIT')
    return content


def safe_name(title,revision,extension):
    normalized=unicodedata.normalize('NFKD',title).encode('ascii','ignore').decode()
    slug=re.sub(r'[^A-Za-z0-9_-]+','_',normalized).strip('_-')[:60] or 'Propuesta'
    return f'Proposal_{slug}_r{revision}.{extension}'


def _uuid(value):
    try:return str(UUID(str(value)))
    except (ValueError,TypeError,AttributeError) as exc:raise HTTPException(422,'INVALID_EXPORT_ID') from exc


def _base(tender_id,version_id,create=False):
    from app.main import get_licitia_data_root
    root=get_licitia_data_root().resolve();path=root
    if not root.is_dir():raise HTTPException(503,'EXPORT_STORAGE_UNAVAILABLE')
    for part in ['storage','proposal-exports-v1',_uuid(tender_id),_uuid(version_id)]:
        path=path/part
        if path.is_symlink() or path.exists() and not path.is_dir():raise HTTPException(409,'UNSAFE_EXPORT_STORAGE')
        if create:
            try:path.mkdir(mode=0o700,exist_ok=True)
            except OSError as exc:raise HTTPException(503,'EXPORT_STORAGE_UNAVAILABLE') from exc
    if not path.resolve().is_relative_to(root):raise HTTPException(409,'EXPORT_PATH_ESCAPE')
    return path


def _file(directory,name):
    path=directory/name
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):raise HTTPException(409,'EXPORT_PATH_ESCAPE')
    return path


def _bytes(path,limit=MAX_FILE):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:raise ValueError('EXPORT_FILE_MISSING_OR_OVERSIZE')
    return path.read_bytes()


def _hash(data):return hashlib.sha256(data).hexdigest()


def _envelope(payload):return canonical_bytes({'payload':payload,'sha256':digest(payload)})


def _decode(data):
    value=json.loads(data)
    if set(value)!={'payload','sha256'} or digest(value['payload'])!=value['sha256']:raise ValueError('EXPORT_MANIFEST_CHECKSUM_MISMATCH')
    return value['payload']


def _write(path,data):
    if len(data)>MAX_PACKAGE:raise ValueError('EXPORT_SIZE_LIMIT')
    with path.open('xb') as handle:
        os.chmod(path,0o600);handle.write(data);handle.flush();os.fsync(handle.fileno())


def _receipt(base,request_id):
    directory=_file(base,_uuid(request_id))
    if not directory.is_dir():raise HTTPException(404,'EXPORT_NOT_FOUND')
    try:
        payload=_decode(_bytes(_file(directory,'receipt.json'),MAX_META))
        if payload['request_id']!=_uuid(request_id) or payload['tender_id']!=base.parent.name or payload['version_id']!=base.name or payload['contract_version']!=EXPORT_CONTRACT:
            raise ValueError('EXPORT_IDENTITY_MISMATCH')
        names=[];types=[]
        for artifact in payload['artifacts']:
            kind=artifact['type'];name=artifact['name']
            if kind=='ZIP':
                if not re.fullmatch(r'Proposal_[A-Za-z0-9_-]{1,60}_r[1-9][0-9]*\.zip',name):raise ValueError('UNSAFE_PACKAGE_NAME')
            elif kind not in FILES or FILES[kind]!=name:raise ValueError('UNSAFE_ARTIFACT_NAME')
            names.append(name);types.append(kind)
        if len(set(names))!=len(names) or len(set(types))!=len(types):raise ValueError('DUPLICATE_EXPORT_ARTIFACT')
        return directory,payload
    except (ValueError,KeyError,TypeError,OSError) as exc:raise HTTPException(409,'EXPORT_RECEIPT_INTEGRITY_FAILURE') from exc


def verify_package(data):
    """Independent archive verification; never extracts files or fetches references."""
    if len(data)>MAX_PACKAGE:raise ValueError('EXPORT_PACKAGE_SIZE_LIMIT')
    with ZipFile(BytesIO(data)) as archive:
        entries=archive.infolist();names=[e.filename for e in entries]
        if len(names)!=len(set(names)) or sum(e.file_size for e in entries)>MAX_PACKAGE:raise ValueError('EXPORT_PACKAGE_INVENTORY')
        if 'manifest.json' not in names:raise ValueError('EXPORT_MANIFEST_MISSING')
        manifest_info=archive.getinfo('manifest.json')
        if manifest_info.file_size>MAX_META:raise ValueError('EXPORT_MANIFEST_SIZE_LIMIT')
        manifest=_decode(archive.read('manifest.json'))
        content=ExportContent.model_validate(manifest['content'])
        if content.semantic_sha256!=manifest['semantic_sha256']:raise ValueError('EXPORT_SEMANTIC_HASH_MISMATCH')
        expected={'manifest.json'}
        kinds=[a['type'] for a in manifest['artifacts']]
        if not kinds or len(kinds)!=len(set(kinds)):raise ValueError('EXPORT_ARTIFACT_INVENTORY')
        for key in ['version_id','tender_id','snapshot_id','composition_sha256']:
            if manifest[key]!=getattr(content,key):raise ValueError('EXPORT_CONTENT_BINDING_MISMATCH')
        for artifact in manifest['artifacts']:
            kind=artifact['type'];name=artifact['name']
            if kind not in FILES or name!=FILES[kind]:raise ValueError('UNSAFE_PACKAGE_MEMBER')
            info=archive.getinfo(name)
            if info.file_size>MAX_FILE or info.file_size!=artifact['size']:raise ValueError('EXPORT_PACKAGE_MEMBER_SIZE')
            if _hash(archive.read(name))!=artifact['sha256']:raise ValueError('EXPORT_ARTIFACT_HASH_MISMATCH')
            expected.add(name)
        if set(names)!=expected:raise ValueError('EXPORT_PACKAGE_UNEXPECTED_MEMBER')
        return manifest


def _verify(directory,payload):
    try:
        manifest_bytes=_bytes(_file(directory,'manifest.json'),MAX_META)
        if _hash(manifest_bytes)!=payload['manifest_sha256']:raise ValueError('EXPORT_MANIFEST_HASH_MISMATCH')
        manifest=_decode(manifest_bytes);content=ExportContent.model_validate(manifest['content'])
        for key in ['version_id','tender_id','snapshot_id','composition_sha256','semantic_sha256']:
            if manifest[key]!=payload[key]:raise ValueError('EXPORT_BINDING_MISMATCH')
        if content.semantic_sha256!=payload['semantic_sha256']:raise ValueError('EXPORT_SEMANTIC_HASH_MISMATCH')
        for key in ['version_id','tender_id','snapshot_id','composition_sha256']:
            if manifest[key]!=getattr(content,key):raise ValueError('EXPORT_CONTENT_BINDING_MISMATCH')
        expected={'manifest.json','receipt.json'}
        for artifact in payload['artifacts']:
            data=_bytes(_file(directory,artifact['name']),MAX_PACKAGE if artifact['type']=='ZIP' else MAX_FILE)
            if len(data)!=artifact['size'] or _hash(data)!=artifact['sha256']:raise ValueError('EXPORT_ARTIFACT_HASH_MISMATCH')
            expected.add(artifact['name'])
            if artifact['type']=='ZIP':
                packaged=verify_package(data)
                if packaged!=manifest:raise ValueError('EXPORT_PACKAGE_MANIFEST_MISMATCH')
        if {p.name for p in directory.iterdir()}!=expected:raise ValueError('EXPORT_UNEXPECTED_FILE')
        return manifest
    except (ValueError,KeyError,TypeError,OSError,BadZipFile) as exc:raise HTTPException(409,'EXPORT_INTEGRITY_FAILURE') from exc


def create_export(db,tender_id,version_id,request):
    tender_id=_uuid(tender_id);version_id=_uuid(version_id);request_id=str(request.request_id)
    versions._verified(db,versions._row(db,tender_id,version_id))
    base=_base(tender_id,version_id,create=True);request_hash=digest(request.model_dump(mode='json'))
    lock=_file(base,'.export.lock')
    with lock.open('a+b') as handle:
        os.chmod(lock,0o600)
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise HTTPException(409,'EXPORT_IN_PROGRESS_RETRY_SAME_REQUEST') from exc
        final=_file(base,request_id)
        if final.exists():
            directory,existing=_receipt(base,request_id)
            if existing['request_sha256']!=request_hash:raise HTTPException(409,'EXPORT_REQUEST_REUSED')
            _verify(directory,existing);return existing
        content=stable_content(db,tender_id,version_id,request);created_at=datetime.now(timezone.utc)
        folder=Path(tempfile.mkdtemp(prefix='.tmp-',dir=base))
        try:
            artifacts=[]
            for kind in request.formats:
                data=RENDERERS[kind](content,created_at)
                if len(data)>MAX_FILE:raise ValueError('EXPORT_FILE_SIZE_LIMIT')
                name=FILES[kind];_write(folder/name,data)
                artifacts.append({'type':kind,'name':name,'sha256':_hash(data),'size':len(data),'created_at':created_at.isoformat()})
            manifest={'contract_version':EXPORT_CONTRACT,'request_id':request_id,'tender_id':tender_id,'proposal_id':content.proposal_id,
                'version_id':version_id,'snapshot_id':content.snapshot_id,'snapshot_sha256':content.snapshot_sha256,
                'composition_contract':content.composition_contract,'composition_sha256':content.composition_sha256,
                'proposal_state':content.proposal_state,'semantic_sha256':content.semantic_sha256,'created_at':created_at.isoformat(),
                'current_source_status':'NOT_REEVALUATED_INPUTS_REMAIN_PINNED','warnings_acknowledged':content.warnings_acknowledged,
                'artifacts':artifacts.copy(),'content':content.model_dump(mode='json')}
            manifest_bytes=_envelope(manifest);_write(folder/'manifest.json',manifest_bytes)
            if request.include_package:
                package=BytesIO()
                with ZipFile(package,'w',compression=ZIP_DEFLATED) as archive:
                    for name in [a['name'] for a in artifacts]+['manifest.json']:
                        info=ZipInfo(name,date_time=(2020,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=0o600<<16
                        archive.writestr(info,_bytes(folder/name,MAX_META if name=='manifest.json' else MAX_FILE))
                data=package.getvalue();verify_package(data)
                name=safe_name(content.proposal_title,content.proposal_version,'zip');_write(folder/name,data)
                artifacts.append({'type':'ZIP','name':name,'sha256':_hash(data),'size':len(data),'created_at':created_at.isoformat()})
            receipt={key:manifest[key] for key in ['contract_version','request_id','tender_id','proposal_id','version_id','snapshot_id',
                'snapshot_sha256','composition_sha256','proposal_state','semantic_sha256','created_at']}
            receipt.update(request_sha256=request_hash,manifest_sha256=_hash(manifest_bytes),artifacts=artifacts,
                           actor_label=request.actor_label,verification_status='VERIFIED_AT_CREATION')
            _write(folder/'receipt.json',_envelope(receipt));_verify(folder,receipt);fsync_dir(folder)
            os.replace(folder,final);fsync_dir(base)
            return receipt
        except OSError as exc:
            raise HTTPException(507,'EXPORT_STORAGE_WRITE_FAILED') from exc
        except ModuleNotFoundError as exc:
            raise HTTPException(503,'EXPORT_LIBRARY_UNAVAILABLE') from exc
        except ValueError as exc:
            raise HTTPException(422,'EXPORT_RENDER_FAILED:'+str(exc)[:120]) from exc
        finally:
            if folder.exists():shutil.rmtree(folder)


def export_metadata(db,tender_id,version_id,request_id):
    versions._verified(db,versions._row(db,tender_id,version_id))
    _,receipt=_receipt(_base(tender_id,version_id),request_id)
    return receipt


def list_exports(db,tender_id,version_id,*,limit=20,before_id=None):
    if not 1<=limit<=50:raise HTTPException(422,'INVALID_EXPORT_PAGE')
    versions._verified(db,versions._row(db,tender_id,version_id));base=_base(tender_id,version_id)
    if not base.exists():return {'items':[],'next_before_id':None}
    values=[]
    for path in base.iterdir():
        if path.name.startswith('.'):continue
        try:identity=str(UUID(path.name))
        except ValueError:continue
        if path.is_symlink():raise HTTPException(409,'UNSAFE_EXPORT_STORAGE')
        if path.is_dir():values.append(_receipt(base,identity)[1])
    values.sort(key=lambda value:(value['created_at'],value['request_id']),reverse=True)
    if before_id:
        _,before=_receipt(base,before_id)
        values=[v for v in values if (v['created_at'],v['request_id'])<(before['created_at'],before['request_id'])]
    return {'items':values[:limit],'next_before_id':values[limit-1]['request_id'] if len(values)>limit else None}


def verify_export(db,tender_id,version_id,request_id):
    versions._verified(db,versions._row(db,tender_id,version_id));directory,receipt=_receipt(_base(tender_id,version_id),request_id)
    _verify(directory,receipt)
    return {'request_id':receipt['request_id'],'verification_status':'VERIFIED','semantic_sha256':receipt['semantic_sha256']}


def artifact_file(db,tender_id,version_id,request_id,kind):
    if kind not in MIMES:raise HTTPException(422,'INVALID_ARTIFACT_TYPE')
    versions._verified(db,versions._row(db,tender_id,version_id));directory,receipt=_receipt(_base(tender_id,version_id),request_id)
    _verify(directory,receipt)
    artifact=next((a for a in receipt['artifacts'] if a['type']==kind),None)
    if artifact is None:raise HTTPException(404,'EXPORT_ARTIFACT_NOT_FOUND')
    return _file(directory,artifact['name']),artifact['name'],MIMES[kind]
