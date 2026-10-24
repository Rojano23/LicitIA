import {useEffect,useRef,useState} from 'react';
import {tendersApi,tenderStatus,type Tender,type TenderDocument} from '../api/tenders';
import {Button,EmptyState,ErrorState,LoadingState,Notice,StatusBadge,TableShell} from '../ui/primitives';
import {tenderHref} from '../ui/routes';
import {TenderDocumentsView} from './TenderDocumentsView';
import './tenderDocuments.css';
const date=(v:string)=>new Date(v).toLocaleString('es-MX');
export function TenderListView({apiUrl,onOpen}:{apiUrl:string;onOpen:(id:string)=>void}){
 const [rows,setRows]=useState<Tender[]|null>(null),[error,setError]=useState(false),[loading,setLoading]=useState(false),[search,setSearch]=useState(''),[state,setState]=useState('');
 const [creating,setCreating]=useState(false),[busy,setBusy]=useState(false),[title,setTitle]=useState(''),[reference,setReference]=useState(''),[profile,setProfile]=useState(''),[createError,setCreateError]=useState(false);
 const generation=useRef(0);
 async function load(){const n=++generation.current;setLoading(true);setError(false);try{const data=await tendersApi.list(apiUrl);if(n===generation.current)setRows(data);}catch{if(n===generation.current)setError(true);}finally{if(n===generation.current)setLoading(false);}}
 useEffect(()=>{void load();return()=>{generation.current++;};},[apiUrl]);
 useEffect(()=>{const guard=(e:BeforeUnloadEvent)=>{if(title||reference||profile){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',guard);return()=>window.removeEventListener('beforeunload',guard);},[title,reference,profile]);
 const filtered=rows?.filter(t=>(!state||t.status===state)&&`${t.title} ${t.external_reference??''}`.toLocaleLowerCase('es-MX').includes(search.toLocaleLowerCase('es-MX'))).sort((a,b)=>b.updated_at.localeCompare(a.updated_at)||a.id.localeCompare(b.id));
 return <div className="tender-product"><div className="product-toolbar"><p>Expedientes guardados en este equipo.</p><div className="product-actions"><Button onClick={()=>void load()} disabled={loading}>Actualizar licitaciones</Button><Button variant="primary" onClick={()=>setCreating(true)}>Nueva licitación</Button></div></div>
 {creating&&<section className="tender-create" aria-label="Nueva licitación"><h2>Nueva licitación</h2><form onSubmit={e=>{e.preventDefault();if(busy||!title.trim())return;setBusy(true);setCreateError(false);void tendersApi.create(apiUrl,{title:title.trim(),external_reference:reference.trim()||null,institution_profile:profile.trim()||null}).then(t=>{setTitle('');setReference('');setProfile('');setCreating(false);void load();onOpen(t.id);}).catch(()=>setCreateError(true)).finally(()=>setBusy(false));}}>
 <label>Nombre de la licitación<input required maxLength={255} value={title} onChange={e=>setTitle(e.target.value)} disabled={busy}/></label>
 <details><summary>Referencia y perfil institucional opcionales</summary><label>Referencia del procedimiento<input maxLength={255} value={reference} onChange={e=>setReference(e.target.value)} disabled={busy}/></label><label>Perfil institucional<input maxLength={255} value={profile} onChange={e=>setProfile(e.target.value)} disabled={busy}/></label></details>
 {createError&&<ErrorState>No pudimos confirmar la creación. Actualiza las licitaciones y verifica si ya existe antes de volver a enviar.</ErrorState>}
 <div className="product-actions"><Button variant="primary" disabled={busy||!title.trim()} type="submit">{busy?'Creando…':'Crear licitación'}</Button><Button disabled={busy} onClick={()=>{if(!(title||reference||profile)||window.confirm('¿Descartar el borrador de la nueva licitación?')){setCreating(false);setTitle('');setReference('');setProfile('');setCreateError(false);}}}>Cancelar</Button></div></form></section>}
 <div className="document-filters"><label>Buscar referencia o nombre<input value={search} onChange={e=>setSearch(e.target.value)}/></label><label>Estado registrado<select value={state} onChange={e=>setState(e.target.value)}><option value="">Todos los estados</option>{['DRAFT','ACTIVE','ARCHIVED'].map(s=><option key={s} value={s}>{tenderStatus(s)}</option>)}</select></label></div>
 {loading&&<LoadingState/>}{error&&<ErrorState retry={()=>void load()}>No pudimos consultar las licitaciones. No se ha confirmado que la lista esté vacía.</ErrorState>}
 {rows?.length===0&&!error&&!loading?<EmptyState title="Aún no hay licitaciones." action={<><Button onClick={()=>setCreating(true)}>Nueva licitación</Button> <a href="#/discovery">Ir a Discovery</a></>}>Crea un expediente para agregar sus documentos.</EmptyState>:rows&&<><p>{filtered?.length} de {rows.length} licitaciones guardadas</p><TableShell label="Licitaciones guardadas"><table><thead><tr><th>Procedimiento / Licitación</th><th>Perfil institucional</th><th>Estado</th><th>Registro actualizado</th><th>Acción</th></tr></thead><tbody>{filtered?.map(t=><tr key={t.id}><td><strong>{t.external_reference||'Sin referencia'}</strong><br/>{t.title}</td><td>{t.institution_profile||'Sin perfil'}</td><td><StatusBadge>{tenderStatus(t.status)}</StatusBadge></td><td>{date(t.updated_at)}</td><td><a href={tenderHref(t.id)}>Abrir licitación</a></td></tr>)}</tbody></table>{!filtered?.length&&<p>Sin coincidencias. Ajusta la búsqueda o el estado.</p>}</TableShell></>}
 </div>;
}
export function TenderProductWorkspace({apiUrl,tenderId,section,onContext,active=true}:{apiUrl:string;tenderId:string;section:string;active?:boolean;onContext:(t:Tender|null)=>void}){
 const [tender,setTender]=useState<Tender|null>(null),[error,setError]=useState(false),[attempt,setAttempt]=useState(0);
 const [documents,setDocuments]=useState<TenderDocument[]>([]),[docsError,setDocsError]=useState(false),[loading,setLoading]=useState(true);
 const [documentsVisited,setDocumentsVisited]=useState(section==='documentos');
 const request=useRef(0);const mounted=useRef(true);
 async function refresh(){const n=++request.current;setLoading(true);setDocsError(false);try{const data=await tendersApi.documents(apiUrl,tenderId);if(mounted.current&&n===request.current)setDocuments(data);}catch{if(mounted.current&&n===request.current)setDocsError(true);}finally{if(mounted.current&&n===request.current)setLoading(false);}}
 useEffect(()=>{mounted.current=true;void refresh();return()=>{mounted.current=false;request.current++;};},[apiUrl,tenderId]);
 useEffect(()=>{let live=true;setError(false);void tendersApi.read(apiUrl,tenderId).then(t=>{if(live){setTender(t);onContext(t);}}).catch(()=>{if(live){setError(true);onContext(null);}});return()=>{live=false;};},[apiUrl,tenderId,attempt,onContext]);
 useEffect(()=>{if(section==='documentos')setDocumentsVisited(true);},[section]);
 if(error)return <ErrorState retry={()=>setAttempt(n=>n+1)}>No pudimos cargar esta licitación. Verifica que siga disponible en este equipo.</ErrorState>;
 if(!tender)return <LoadingState>Consultando licitación…</LoadingState>;
 const issues=documents.filter(d=>['TEXT_EXTRACTION_FAILED','TEXT_EXTRACTION_PARTIAL','NO_NATIVE_TEXT'].includes(d.processing_status??''));
 return <div className="tender-product"><section hidden={section!=='resumen'} aria-label="Resumen de licitación"><h2>Datos del registro</h2><dl className="tender-identity"><dt>Referencia</dt><dd>{tender.external_reference||'Sin referencia'}</dd><dt>Perfil institucional</dt><dd>{tender.institution_profile||'Sin perfil'}</dd><dt>Estado registrado</dt><dd>{tenderStatus(tender.status)}</dd><dt>Creado</dt><dd>{date(tender.created_at)}</dd><dt>Registro actualizado</dt><dd>{date(tender.updated_at)}</dd></dl>
 <h2>Expediente documental</h2>{loading?<LoadingState/>:docsError?<ErrorState retry={()=>void refresh()}>No pudimos consultar el expediente documental.</ErrorState>:<><p>{documents.length} revisiones registradas · {documents.filter(d=>d.is_current).length} actuales · {documents.filter(d=>!d.is_current).length} anteriores</p>{issues.length>0&&<Notice tone="warning">{issues.length} revisiones con extracción parcial, fallida o sin texto nativo. Consulta los documentos; esto no certifica ausencia de obligaciones.</Notice>}</>}
 <p><a className="ui-button ui-button--primary" href={tenderHref(tenderId,'documentos')}>Ir a Documentos</a></p><p className="ui-secondary">Las fechas pertenecen al registro, no son fechas contractuales. Los originales y la revisión humana son la autoridad.</p></section>
 {documentsVisited&&<div hidden={section!=='documentos'}><TenderDocumentsView active={active&&section==='documentos'} apiUrl={apiUrl} tenderId={tenderId} documents={documents} loading={loading} error={docsError} refresh={()=>void refresh()}/></div>}
 </div>;
}
