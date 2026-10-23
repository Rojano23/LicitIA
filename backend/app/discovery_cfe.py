"""Current CFE public form/JSON and HTML metadata. No binary acquisition."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit,urljoin,unquote,urlencode
import json,re,time
import httpx
from lxml import html
from app.discovery_contract import Opportunity,PublicDocument,Batch,fingerprint

ROOT='https://msc.cfe.mx/Aplicaciones/NCFE/Concursos/'
AREAS={'public':{'label':'CFE procedimientos públicos'}}
MAX_RESPONSE=16*1024*1024
MAX_ROWS=100000
class AcquisitionError(ValueError):pass


def public_url(value,*,document=False):
    if not isinstance(value,str) or not value or len(value)>2000 or any(ord(c)<33 for c in value):
        raise AcquisitionError('INVALID_CFE_URL')
    url=urljoin(ROOT,value);p=urlsplit(url);decoded=p.path
    for _ in range(4):decoded=unquote(decoded)
    if p.scheme!='https' or p.hostname!='msc.cfe.mx' or p.port not in {None,443} or p.username or p.password or p.fragment:
        raise AcquisitionError('CFE_HOST_POLICY')
    if '\\' in decoded or any(c in decoded for c in '\r\n\t') or any(x in {'.','..'} for x in decoded.split('/')):
        raise AcquisitionError('CFE_PATH_POLICY')
    allowed={'','Procedure/getProcBusqueda','Procedure/Details'} if not document else {
        'Procedure/GetAnexo','Procedure/DescargarPrecision','Procedure/DescargarRespuestaPrecision'}
    if decoded not in {urlsplit(ROOT).path+a for a in allowed}:raise AcquisitionError('CFE_PATH_POLICY')
    return url


def text(value):
    if value is None:return None
    if not isinstance(value,str):raise ValueError('INVALID_CFE_TEXT')
    return ' '.join(value.split()) or None


def publication(value):
    if value is None:return None
    if not isinstance(value,str):raise ValueError('INVALID_CFE_DATE')
    match=re.fullmatch(r'/Date\((-?\d+)(?:[+-]\d{4})?\)/',value)
    if not match:raise ValueError('INVALID_CFE_DATE')
    return datetime.fromtimestamp(int(match[1])/1000,timezone.utc).astimezone(ZoneInfo('America/Mexico_City')).date()


class CFEProcurementAdapter:
    source_id='CFE'
    version='cfe-public-form-v1'
    areas=AREAS
    def __init__(self,transport=None,pacing=1.0):
        self.client=httpx.Client(transport=transport,follow_redirects=False,timeout=httpx.Timeout(30,connect=10),
            headers={'User-Agent':'LicitIA-Discovery/1.0 public-metadata'})
        self.pacing=pacing;self.last_request=0.;self.tokens=None;self.snapshot=None;self.query_hash=None;self.expected_offset=0
        self.observation={'http_requests':0,'listing_requests':0,'detail_requests':0,'array_rows':None,'batch_count':0}
    def download(self,document):
        from app.discovery_downloads import download
        return download(self.client,document,lambda url:public_url(url,document=True))
    def close(self):
        self.client.close();self.tokens=None;self.snapshot=None
    @staticmethod
    def capabilities():
        return {'public':True,'automation_status':'AVAILABLE','acquisition':'PUBLIC_FORM_JSON_HTML',
            'pagination':'FULL_ARRAY_LOCAL_BATCHES','source_filters':['published_from','published_to','event_type'],'local_acquisition_filters':['supply_type'],
            'reported_total':'NOT_PUBLISHED','documents':'PUBLIC_DETAIL_HTML_REFERENCES_ONLY','detail_lookup':'PUBLIC_POST',
            'binary_download':False,'explicit_document_import':True,'max_page_size':200,'max_response_bytes':MAX_RESPONSE,'max_array_rows':MAX_ROWS,
            'requires_date_pair':True,'snapshot_consistency':'BEST_EFFORT','date_timezone':'America/Mexico_City'}
    def request(self,method,path,*,data=None,mime='html'):
        url=public_url(path)
        for attempt in range(3):
            delay=max(0,self.last_request+self.pacing-time.monotonic())
            if delay:time.sleep(delay)
            self.last_request=time.monotonic();self.observation['http_requests']+=1
            try:
                with self.client.stream(method,url,data=data) as response:
                    if response.status_code in {429,500,502,503,504} and attempt<2:
                        time.sleep(attempt+1);continue
                    if response.status_code!=200:raise AcquisitionError('CFE_HTTP_'+str(response.status_code))
                    if mime not in response.headers.get('content-type','').lower():raise AcquisitionError('CFE_RESPONSE_MIME')
                    chunks=[];size=0
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>MAX_RESPONSE:raise AcquisitionError('CFE_RESPONSE_LIMIT')
                        chunks.append(chunk)
                    return b''.join(chunks)
            except (httpx.TimeoutException,httpx.NetworkError) as exc:
                if attempt==2:raise AcquisitionError('CFE_NETWORK_UNAVAILABLE') from exc
                time.sleep(attempt+1)
        raise AcquisitionError('CFE_RETRY_EXHAUSTED')
    def prepare(self):
        page=html.fromstring(self.request('GET',ROOT))
        values=[]
        for form in ['__AjaxAntiForgeryForm','frmDetalle']:
            tokens=page.xpath('//form[@id=$form]//input[@name="__RequestVerificationToken"]/@value',form=form)
            if len(tokens)!=1 or not tokens[0]:raise AcquisitionError('CFE_PUBLIC_FORM_CHANGED')
            values.append(tokens[0])
        self.tokens=values
    def load(self,query):
        if bool(query.published_from)!=bool(query.published_to):raise AcquisitionError('CFE_REQUIRES_BOTH_DATE_BOUNDS')
        if self.tokens is None:self.prepare()
        # Literal human filter labels are not source codes. Resolve only verified mappings.
        event={'Concurso abierto':'CA','Concurso simplificado':'CS','Adjudicación directa':'AD'}
        if query.event_type and query.event_type not in event:raise AcquisitionError('UNSUPPORTED_CFE_EVENT_FILTER')
        # Supply codes are not inferred from labels: filter locally after exhaustive acquisition.
        data={'__RequestVerificationToken':self.tokens[0],'TipoProcedimientoClave':event.get(query.event_type,''),
            'TipoContratacionClave':'','IdEntidadFederativa':'0','Numero':'','Descripcion':'',
            'EstadoProcedimientoContratacionClave':'0','FechaPublicacion':'',
            'FechaPublicacionIni':query.published_from.isoformat() if query.published_from else '',
            'FechaPublicacionFin':query.published_to.isoformat() if query.published_to else '',
            'TestigoSocial':'2','idCaracterProcedimiento':'0','Modalidad':'0'}
        self.observation['listing_requests']+=1
        raw=json.loads(self.request('POST','Procedure/getProcBusqueda',data=data,mime='json'))
        if not isinstance(raw,list) or len(raw)>MAX_ROWS:raise AcquisitionError('CFE_ARRAY_LAYOUT_OR_LIMIT')
        self.observation['array_rows']=len(raw)
        # Invalid records remain in the stream so the core sees parser issues.
        self.snapshot=[r for r in raw if not isinstance(r,dict) or not query.supply_type or r.get('TipoContratacionClave')==query.supply_type]
    def detail(self,source_id,number):
        self.observation['detail_requests']+=1
        root=html.fromstring(self.request('POST','Procedure/Details',data={'id':source_id,'__RequestVerificationToken':self.tokens[1]}))
        for node in root.xpath('//script|//style'):node.drop_tree()
        numbers=root.xpath('//input[@id="txtNumeroDeConcurso"]/@value')
        if numbers!=[number]:raise AcquisitionError('CFE_DETAIL_IDENTITY_MISMATCH')
        fields={}
        for row in root.xpath('//table//tr'):
            cells=row.xpath('./td')
            if len(cells)==2:
                label=text(cells[0].text_content());value=text(cells[1].text_content())
                if label in {'Empresa','Área Contratante'}:
                    if label in fields and fields[label]!=value:raise AcquisitionError('CFE_AMBIGUOUS_DETAIL_FIELD')
                    fields[label]=value
        docs={};issues=[]
        for link in root.xpath('//a[@onclick or @href]'):
            onclick=link.get('onclick','');href=link.get('href','')
            match=re.fullmatch(r"\s*descargarAnexoConToken\('([A-Za-z0-9_!\-]+)'\)\s*;?\s*",onclick)
            candidate=None
            if 'descargarAnexoConToken' in onclick:
                if not match:issues.append({'code':'CFE_DOCUMENT_REFERENCE_CHANGED'});continue
                candidate='Procedure/GetAnexo?'+urlencode({'id':match[1]})
            elif any(name in href for name in ['GetAnexo','DescargarPrecision','DescargarRespuestaPrecision']):
                candidate=urljoin(ROOT+'Procedure/Details',href)
            if not candidate:continue
            try:
                url=public_url(candidate,document=True)
                cells=link.xpath('ancestor::tr[1]/td');name=text(cells[0].text_content()) if cells else text(link.text_content())
                if not name:raise ValueError('CFE_DOCUMENT_NAME_MISSING')
                doc=PublicDocument(external_id=url,name=name,public_url=url)
                if url in docs and docs[url]!=doc:raise ValueError('CFE_DOCUMENT_COLLISION')
                docs[url]=doc
            except (ValueError,TypeError,IndexError):issues.append({'code':'UNSAFE_OR_MALFORMED_DOCUMENT'})
        return fields,list(docs.values()),issues
    def normalize(self,row):
        if not isinstance(row,dict) or type(row.get('Id')) is not int or row['Id']<=0:raise ValueError('CFE_MISSING_ID')
        number=text(row.get('Numero'));description=text(row.get('Descripcion'))
        if not number or not description:raise ValueError('CFE_MISSING_REQUIRED_TEXT')
        published=publication(row.get('FechaPublicacion'))
        fields,docs,issues=self.detail(str(row['Id']),number)
        return Opportunity(external_id=str(row['Id']),procedure_number=number,title=description,description=description,
            business_area=fields.get('Empresa') or AREAS['public']['label'],contracting_area=fields.get('Área Contratante'),
            published_date=published,event_type=text(row.get('TipoProcedimientoClave')),supply_type=text(row.get('TipoContratacionClave')),
            source_status=text(row.get('EstadoProcedimiento')),public_url=ROOT,documents=docs,
            raw_metadata={'entity_federation':text(row.get('EntidadFederativa')),'area_key':'public',
                'detail_navigation':{'method':'POST','path':'Procedure/Details','id':str(row['Id'])},
                'document_coverage':'PUBLIC_DETAIL_HTML_REFERENCES_ONLY'}),issues
    def fetch(self,query,area,cursor):
        if area not in self.areas:raise AcquisitionError('UNSUPPORTED_CFE_AREA')
        key=fingerprint(query.model_dump(mode='json'))
        if cursor is None:
            self.snapshot=None;self.query_hash=key;self.expected_offset=0;self.load(query);offset=0
        else:
            if self.snapshot is None or key!=self.query_hash or cursor!=f'{key}:{self.expected_offset}':
                raise AcquisitionError('INVALID_CFE_CONTINUATION')
            offset=self.expected_offset
        raw=self.snapshot[offset:offset+query.page_size];rows=[];issues=[]
        for row in raw:
            try:
                value,problems=self.normalize(row);rows.append(value);issues.extend(problems)
            except AcquisitionError:issues.append({'code':'CFE_DETAIL_ACQUISITION_FAILED'})
            except (ValueError,TypeError,KeyError,OverflowError,OSError):issues.append({'code':'MALFORMED_ROW'})
        self.expected_offset=offset+len(raw);terminal=self.expected_offset>=len(self.snapshot)
        self.observation['batch_count']+=1
        return Batch(rows=rows,raw_count=len(raw),terminal=terminal,
            next_cursor=None if terminal else f'{key}:{self.expected_offset}',source_total=None,issues=issues)
