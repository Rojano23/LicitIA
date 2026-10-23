"""One PEMEX adapter, configured areas, public SharePoint JSON continuation."""
from datetime import date
from urllib.parse import urlsplit,urlunsplit,urlencode,parse_qsl,unquote,urljoin
import re,time
import httpx
from lxml import html
from app.discovery_contract import Opportunity,PublicDocument,Batch

HOST='https://www.pemex.com'
PREFIX='/procura/procedimientos-de-contratacion/concursosabiertos'
AREAS={
 'support':{'label':'Servicios y Bienes de Soporte','page':'Pemex.aspx','list':'Concursoseinvitaciones'},
 'exploration':{'label':'Exploración y Extracción','page':'Pemex-Exploración-y-Producción.aspx','list':'ConcursosAbiertosPEP'},
 'industrial':{'label':'Procesos Industriales y Transformación Energética','page':'Pemex-Transformación-Industrial.aspx','list':'ConcursosAbiertosPTI'},
 'logistics':{'label':'Logística','page':'Pemex-Logística.aspx','list':'ConcursosAbiertosPL'},
}
MAX_RESPONSE=16*1024*1024
class AcquisitionError(ValueError):pass


def public_url(value):
    if not isinstance(value,str) or len(value)>2000:raise AcquisitionError('INVALID_PUBLIC_URL')
    absolute=urljoin(HOST,value);p=urlsplit(absolute)
    decoded=p.path
    for _ in range(3):decoded=unquote(decoded)
    if p.scheme!='https' or p.hostname not in {'www.pemex.com','pemex.com'} or p.port not in {None,443} or p.username or p.password or p.fragment:
        raise AcquisitionError('PUBLIC_HOST_POLICY')
    if not decoded.startswith(PREFIX+'/') or any(part in {'.','..'} for part in decoded.split('/')) or '\\' in decoded or any(ord(c)<32 for c in absolute):
        raise AcquisitionError('PUBLIC_PATH_POLICY')
    return absolute


def literal(value):
    if value is None:return None
    if not isinstance(value,str):raise ValueError('SOURCE_TEXT_TYPE')
    if '<' in value:
        root=html.fragment_fromstring(value,create_parent=True)
        for node in root.xpath('.//script|.//style'):node.drop_tree()
        value=root.text_content()
    return ' '.join(value.split()) or None

class PEMEXConcursosAdapter:
    source_id='PEMEX'
    version='pemex-sharepoint-v1'
    areas=AREAS
    def __init__(self,transport=None,pacing=1.0):
        self.client=httpx.Client(timeout=httpx.Timeout(30,connect=10),follow_redirects=False,transport=transport,
            headers={'Accept':'application/json;odata=verbose','User-Agent':'LicitIA-Discovery/1.0 public-metadata'})
        self.pacing=pacing;self.last_request=0.0
    def download(self,document):
        from app.discovery_downloads import download
        return download(self.client,document,public_url)
    def close(self):self.client.close()
    @staticmethod
    def capabilities():return {'public':True,'acquisition':'SHAREPOINT_PUBLIC_JSON','pagination':'ODATA_NEXT_SKIPTOKEN',
        'source_filters':['published_from','published_to','event_type','supply_type'],'documents':'METADATA_ONLY',
        'binary_download':False,'explicit_document_import':True,'snapshot_consistency':'BEST_EFFORT','max_page_size':200,'reported_total':'WHEN_PRESENT_ONLY'}
    def endpoint(self,area):
        return HOST+PREFIX+"/_api/web/GetList('"+PREFIX+'/Lists/'+AREAS[area]['list']+"')/items"
    def first_url(self,query,area):
        params={'$select':'Id,Title,descripcion,inicio,tipoevento,tiposuministro,areacontratante,AttachmentFiles/FileName,AttachmentFiles/ServerRelativeUrl',
            '$expand':'AttachmentFiles','$orderby':'Id asc','$top':str(query.page_size)}
        conditions=[]
        for key,operator,value in [('inicio','ge',query.published_from),('inicio','le',query.published_to)]:
            if value:conditions.append(f"{key} {operator} datetime'{value.isoformat()}T{'23:59:59' if operator=='le' else '00:00:00'}'")
        for key,value in [('tipoevento',query.event_type),('tiposuministro',query.supply_type)]:
            if value:conditions.append(key+" eq '"+value.replace("'","''")+"'")
        if conditions:params['$filter']=' and '.join(conditions)
        return self.endpoint(area)+'?'+urlencode(params)
    def continuation(self,value,query,area):
        url=public_url(value);parsed=urlsplit(url);expected=urlsplit(self.endpoint(area))
        if unquote(parsed.path)!=unquote(expected.path):raise AcquisitionError('UNEXPECTED_CONTINUATION_PATH')
        pairs=parse_qsl(parsed.query,keep_blank_values=True)
        if len(pairs)!=len(dict(pairs)):raise AcquisitionError('DUPLICATE_CONTINUATION_PARAMETER')
        actual=dict(pairs);initial=dict(parse_qsl(urlsplit(self.first_url(query,area)).query))
        if any(actual.get(k)!=v for k,v in initial.items()) or set(actual)-set(initial)-{'$skiptoken','$skip'}:
            raise AcquisitionError('CONTINUATION_QUERY_CHANGED')
        if '$skiptoken' not in actual and '$skip' not in actual:raise AcquisitionError('CONTINUATION_MISSING_CURSOR')
        return url
    def get_json(self,url):
        public_url(url)
        for attempt in range(3):
            delay=max(0,self.last_request+self.pacing-time.monotonic())
            if delay:time.sleep(delay)
            self.last_request=time.monotonic()
            try:
                with self.client.stream('GET',url) as response:
                    if response.status_code in {429,500,502,503,504}:
                        if attempt<2:time.sleep(attempt+1);continue
                    if response.status_code!=200:raise AcquisitionError('SOURCE_HTTP_'+str(response.status_code))
                    if 'json' not in response.headers.get('content-type','').lower():raise AcquisitionError('SOURCE_MIME_NOT_JSON')
                    chunks=[];size=0
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>MAX_RESPONSE:raise AcquisitionError('SOURCE_RESPONSE_LIMIT')
                        chunks.append(chunk)
                    import json
                    return json.loads(b''.join(chunks))
            except (httpx.TimeoutException,httpx.NetworkError) as exc:
                if attempt==2:raise AcquisitionError('SOURCE_NETWORK_UNAVAILABLE') from exc
                time.sleep(attempt+1)
        raise AcquisitionError('SOURCE_RETRY_EXHAUSTED')
    def normalize(self,row,area):
        external=literal(row.get('Title'));description=literal(row.get('descripcion'))
        if not external or not re.fullmatch(r'[\w .()/\-]{1,200}',external) or not description:raise ValueError('MISSING_OR_MALFORMED_EVENT')
        published=row.get('inicio');published=date.fromisoformat(published[:10]) if published else None
        docs=[];issues=[]
        attachments=row.get('AttachmentFiles')
        if not isinstance(attachments,dict) or not isinstance(attachments.get('results'),list):raise ValueError('DOCUMENT_METADATA_NOT_EXPANDED')
        for item in attachments['results']:
            try:
                name=literal(item.get('FileName'));url=public_url(item['ServerRelativeUrl'])
                if not name:raise ValueError('DOCUMENT_NAME_MISSING')
                docs.append(PublicDocument(external_id=url,name=name,public_url=url))
            except (ValueError,KeyError,TypeError):issues.append({'code':'UNSAFE_OR_MALFORMED_DOCUMENT','event_id':external})
        value=Opportunity(external_id=external,business_area=AREAS[area]['label'],title=description,description=description,
            contracting_area=literal(row.get('areacontratante')),published_date=published,event_type=literal(row.get('tipoevento')),supply_type=literal(row.get('tiposuministro')),
            public_url=HOST+PREFIX+'/Paginas/'+AREAS[area]['page'],documents=docs,
            raw_metadata={'list_item_id':row.get('Id'),'area_key':area,'list_name':AREAS[area]['list']})
        return value,issues
    def fetch(self,query,area,cursor):
        if area not in AREAS:raise AcquisitionError('UNSUPPORTED_AREA')
        url=self.continuation(cursor,query,area) if cursor else self.first_url(query,area)
        payload=self.get_json(url)
        if not isinstance(payload,dict) or not isinstance(payload.get('d'),dict):raise AcquisitionError('SOURCE_JSON_LAYOUT')
        data=payload['d'];raw=data.get('results')
        if not isinstance(raw,list) or len(raw)>query.page_size:raise AcquisitionError('SOURCE_BATCH_LAYOUT_OR_SIZE')
        rows=[];issues=[]
        for index,row in enumerate(raw):
            try:
                value,problems=self.normalize(row,area);rows.append(value);issues+=problems
            except (ValueError,KeyError,TypeError,AttributeError):issues.append({'code':'MALFORMED_ROW','row_index':index})
        next_url=data.get('__next')
        if next_url is not None and (not isinstance(next_url,str) or not next_url):raise AcquisitionError('INVALID_CONTINUATION')
        if next_url:next_url=self.continuation(next_url,query,area)
        total=data.get('__count');total=int(total) if total is not None else None
        if total is not None and total<0:raise AcquisitionError('INVALID_SOURCE_TOTAL')
        return Batch(rows=rows,raw_count=len(raw),next_cursor=next_url,terminal=next_url is None,source_total=total,issues=issues)
