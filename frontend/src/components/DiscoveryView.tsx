import {DiscoveryDetail} from './DiscoveryDetail';
import {monitoringApi} from '../api/discovery';
import {useRef,useState,useEffect} from 'react';
import {Button,Notice,SourceBadge,StatusBadge,TableShell} from '../ui/primitives';
import {workflowLabels,scanLabels,matchLabel,sourceName,displayDate} from '../ui/discoveryPresentation';
import './discovery.css';
import {discoveryApi,type Source,type Profile,type Page,type Scan,type SourceQuery} from '../api/discovery';
export function DiscoveryView({apiUrl,onOpenTender,view='all',opportunityId,scanId,scanSource,filterRequest}:{apiUrl:string;onOpenTender?:(id:string)=>void;view?:string;opportunityId?:string;scanId?:string;scanSource?:string;filterRequest?:object}){
 const [showScan,setShowScan]=useState(false);
 const listGeneration=useRef(0), workCount=useRef(0);
 const applied=useRef<Record<string,string|number|boolean|undefined>>({});
 const [localEvent,setLocalEvent]=useState(''),[localSupply,setLocalSupply]=useState('');
 const [scanFrom,setScanFrom]=useState(''),[scanTo,setScanTo]=useState('');
 const [detail,setDetail]=useState<string|null>(null),[following,setFollowing]=useState(false),[unread,setUnread]=useState(false);
 const [sources,setSources]=useState<Source[]>([]),[sourceId,setSource]=useState('PEMEX'),[areas,setAreas]=useState<string[]>([]);
 const [listSource,setListSource]=useState(''),[localArea,setLocalArea]=useState(''),[sourceStatus,setSourceStatus]=useState('');
 const [profiles,setProfiles]=useState<Profile[]>([]),[profileId,setProfile]=useState(''),[matched,setMatched]=useState(false);
 const [page,setPage]=useState<Page|null>(null),[scans,setScans]=useState<Scan[]>([]),[scan,setScan]=useState<Scan|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[search,setSearch]=useState(''),[state,setState]=useState('');
 const [dateFrom,setFrom]=useState(''),[dateTo,setTo]=useState(''),[eventType,setEvent]=useState(''),[supply,setSupply]=useState('');
 const [name,setName]=useState(''),[include,setInclude]=useState(''),[exclude,setExclude]=useState(''),[synonyms,setSynonyms]=useState('');
 const [profileAreas,setProfileAreas]=useState(''),[profileSources,setProfileSources]=useState<string[]>([]);
 const [active,setActive]=useState(true);
 const mounted=useRef(true),pending=useRef<{id:string;source:string;query:SourceQuery}|null>(null);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const source=sources.find(s=>s.id===sourceId);
 const isRestricted=(id:string)=>sources.find(s=>s.id===id)?.capabilities?.automation_status==='DEFERRED_SOURCE_AUTOMATION_RESTRICTED';
 const restricted=isRestricted(sourceId);
 const invalidDates=!!source?.capabilities?.requires_date_pair&&!!scanFrom!==!!scanTo || !!scanFrom&&!!scanTo&&scanFrom>scanTo;
 async function run(action:()=>Promise<void>){workCount.current++;setBusy(true);setError('');try{await action();}catch{if(mounted.current)setError('No se pudo completar la acción. Los resultados anteriores se conservan. Revisa la consulta de la fuente o vuelve a consultar los datos locales.');}finally{workCount.current--;if(mounted.current)setBusy(workCount.current>0);}}
 async function list(offset=0,override:Record<string,string|number|boolean|undefined>={},reuse=false){
  const request=++listGeneration.current;
  const current={source:listSource||undefined,area:localArea||undefined,source_status:sourceStatus||undefined,search:search||undefined,profile_id:profileId||undefined,matched_only:matched&&!!profileId,following,unread_only:unread,internal_state:state||undefined,published_from:dateFrom||undefined,published_to:dateTo||undefined,event_type:localEvent||undefined,supply_type:localSupply||undefined,...override};
  const params=reuse||offset>0?applied.current:current;
  const result=await discoveryApi.list(apiUrl,{...params,offset,limit:50});
  if(mounted.current&&request===listGeneration.current){applied.current=params;setPage(result);}
 }
 async function refresh(){
  const values=await Promise.allSettled([discoveryApi.sources(apiUrl),discoveryApi.profiles(apiUrl),discoveryApi.scans(apiUrl,sourceId)]);
  if(!mounted.current)return;
  if(values[0].status==='fulfilled'){setSources(values[0].value);if(!areas.length)setAreas(values[0].value.find(v=>v.id===sourceId)?.configuration.areas??[]);}
  if(values[1].status==='fulfilled')setProfiles(values[1].value);
  if(values[2].status==='fulfilled')setScans(values[2].value);
  if(values.some(v=>v.status==='rejected'))setError('No se pudo actualizar parte de la configuración o historial. Los resultados guardados permanecen disponibles.');
 }
 useEffect(()=>{void run(async()=>{await refresh();});},[apiUrl]);
 useEffect(()=>{
  const next={internal_state:view==='new'?'NEW':view==='imported'?'IMPORTED':view==='discarded'?'DISCARDED':undefined,following:view==='following'||view==='following-changes',unread_only:view==='changes'||view==='following-changes'};
  setState(next.internal_state??'');setFollowing(next.following);setUnread(next.unread_only);
  setListSource('');setLocalArea('');setSearch('');chooseProfile('');setMatched(false);setFrom('');setTo('');setLocalEvent('');setLocalSupply('');setSourceStatus('');
  void run(()=>list(0,{...next,source:undefined,area:undefined,source_status:undefined,search:undefined,profile_id:undefined,matched_only:false,published_from:undefined,published_to:undefined,event_type:undefined,supply_type:undefined}));
 },[view,filterRequest]);
 useEffect(()=>{if(opportunityId)setDetail(opportunityId);},[opportunityId]);
 useEffect(()=>{if(showScan)document.getElementById('source-consultation')?.scrollIntoView?.({block:'start'});},[showScan]);
 useEffect(()=>{if(scanId){setShowScan(true);void run(async()=>{const value=await discoveryApi.getScan(apiUrl,scanId);if(mounted.current){setScan(value);if(scanSource)setSource(scanSource);}});}},[scanId,scanSource]);
 function chooseProfile(id:string){setProfile(id);const p=profiles.find(p=>p.id===id);setName(p?.name??'');setInclude(p?.include_keywords.join('\n')??'');setExclude(p?.exclude_keywords.join('\n')??'');setSynonyms(Object.entries(p?.synonyms??{}).map(([key,values])=>`${key}=${values.join('|')}`).join('\n'));setActive(p?.active??true);setProfileSources(p?.source_ids??[]);setProfileAreas(p?.business_areas.join('\n')??'');}
 return <section className="discovery-product" aria-label="Discovery público">
 <div className="product-toolbar"><p>Oportunidades públicas guardadas en este equipo. Los perfiles se evalúan localmente; consultar no crea ni analiza una licitación.</p><Button variant="primary" onClick={()=>setShowScan(v=>!v)} aria-expanded={showScan} aria-controls="source-consultation">Buscar actualizaciones</Button></div>
 <div className="source-strip" aria-label="Estado de fuentes">{sources.map(s=><span key={s.id}><SourceBadge name={sourceName(s.id)} restricted={isRestricted(s.id)}/>{!isRestricted(s.id)&&<small>{s.enabled?'Disponible para consulta':'Deshabilitada'} · {scanLabels[s.last_scan_state??'']??'Sin consultas'}</small>}</span>)}</div>
 <div className="discovery-filters">
 <label>Vista de oportunidades<select value={following&&unread?'following-changes':following?'following':unread?'changes':state==='NEW'?'new':state==='IMPORTED'?'imported':state==='DISCARDED'?'discarded':'all'} onChange={e=>{const v=e.target.value;const next={internal_state:v==='new'?'NEW':v==='imported'?'IMPORTED':v==='discarded'?'DISCARDED':undefined,following:v==='following'||v==='following-changes',unread_only:v==='changes'||v==='following-changes'};setState(next.internal_state??'');setFollowing(next.following);setUnread(next.unread_only);void run(()=>list(0,next));}}><option value="all">Todas</option><option value="new">Nuevas</option><option value="following">Siguiendo</option><option value="changes">Con cambios</option><option value="following-changes">Siguiendo con cambios</option><option value="imported">Licitaciones creadas</option><option value="discarded">Descartadas</option></select></label>
 <label>Fuente de oportunidades locales<select value={listSource} onChange={e=>{setListSource(e.target.value);}}><option value="">Todas las fuentes</option>{sources.map(s=><option key={s.id} value={s.id}>{sourceName(s.id)}</option>)}</select></label>
 <label>Perfil de búsqueda<select value={profileId} onChange={e=>chooseProfile(e.target.value)}><option value="">Sin perfil</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}{p.active?'':' (inactivo)'}</option>)}</select></label>
 <label>Buscar procedimiento, descripción o área<input value={search} maxLength={200} onChange={e=>setSearch(e.target.value)}/></label>
 <Button disabled={busy||!!dateFrom&&!!dateTo&&dateFrom>dateTo} onClick={()=>void run(()=>list())}>Aplicar filtros</Button>
 </div>
 <details className="secondary-controls"><summary>Más filtros</summary><div className="discovery-filters">
 <label>Área o entidad (valor exacto)<input value={localArea} onChange={e=>setLocalArea(e.target.value)}/></label>
 <label>Publicado desde<input type="date" value={dateFrom} onChange={e=>setFrom(e.target.value)}/></label><label>Publicado hasta<input type="date" value={dateTo} onChange={e=>setTo(e.target.value)}/></label>
 <label>Tipo de evento local<input value={localEvent} onChange={e=>setLocalEvent(e.target.value)}/></label><label>Tipo de suministro local<input value={localSupply} onChange={e=>setLocalSupply(e.target.value)}/></label>
 <label>Estado fuente (valor literal)<input value={sourceStatus} onChange={e=>setSourceStatus(e.target.value)}/></label>
 <label>Estado interno<select value={state} onChange={e=>setState(e.target.value)}><option value="">Todos</option>{Object.entries(workflowLabels).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label>
 <label><input type="checkbox" checked={matched} disabled={!profileId} onChange={e=>setMatched(e.target.checked)}/>Sólo coincidencias del perfil</label>
 <label><input type="checkbox" checked={following} onChange={e=>setFollowing(e.target.checked)}/>Siguiendo</label><label><input type="checkbox" checked={unread} onChange={e=>setUnread(e.target.checked)}/>Cambios sin leer</label>
 </div></details>
 {busy&&<p role="status">Consultando información{showScan&&source?` de ${sourceName(source.id)}`:''}…</p>}
 {error&&<div role="alert"><p>{error}</p><Button onClick={()=>void run(async()=>{await refresh();await list();})}>Volver a consultar datos locales</Button></div>}
 {page&&<><p className="ui-secondary">{page.total} oportunidades locales · Mostrando {page.items.length? page.offset+1:0}–{Math.min(page.offset+page.items.length,page.total)}. Resultados de los filtros aplicados. Las consultas parciales no certifican cobertura completa.</p>
 <TableShell label="Oportunidades" empty={!page.items.length}><table className="opportunities-table"><thead><tr>{['Fuente / Procedimiento','Descripción','Publicación / Área','Coincidencia','Documentos / Cambios','Estado','Acciones'].map(h=><th scope="col" key={h}>{h}</th>)}</tr></thead><tbody>
 {page.items.map(row=><tr key={row.id}><td><strong>{sourceName(row.source_id)}</strong><br/>{row.procedure_number??row.external_id}</td><td><Button variant="ghost" className="description-link" disabled={isRestricted(row.source_id)} title={row.title} onClick={()=>setDetail(row.id)}>{row.title}</Button></td><td>{displayDate(row.published_date)}<br/>{row.contracting_area??row.business_area}</td><td>{matchLabel(row.match)}</td><td className={(row.unread_changes??0)>0?"opportunity-pending-changes":undefined}>{row.document_count} referencias descubiertas<br/>{row.unread_changes??0} cambios sin leer{(row.unread_document_changes??0)>0&&<small> · {row.unread_document_changes} documentales</small>}{row.source_changes_available&&<p>Hay cambios desde la creación</p>}</td><td><StatusBadge tone={row.internal_state==='NEW'?'info':'neutral'}>{workflowLabels[row.internal_state]??'Por revisar'}</StatusBadge>{row.watching&&row.internal_state!=='FOLLOWING'&&<small>Siguiendo</small>}</td>
 <td><div className="row-actions">{row.linked_tender?.available?<Button className="row-primary-action" disabled={!onOpenTender} onClick={()=>onOpenTender?.(row.linked_tender!.id)}>Abrir licitación</Button>:<Button className="row-primary-action" disabled={busy||isRestricted(row.source_id)} onClick={()=>setDetail(row.id)}>Revisar</Button>}
 <details><summary>Más acciones</summary><div className="action-list">
 <Button disabled={busy||isRestricted(row.source_id)} onClick={()=>setDetail(row.id)}>{row.unread_changes?'Ver cambios':'Ver detalle / Crear licitación'}</Button>
 <Button disabled={busy||isRestricted(row.source_id)} onClick={()=>void run(async()=>{await monitoringApi.follow(apiUrl,row);await list(page.offset,{},true);})}>{row.watching?'Dejar de seguir':'Seguir'}</Button>
 <label>Estado interno {row.external_id}<select disabled={busy||row.internal_state==='IMPORTED'||isRestricted(row.source_id)} value={row.internal_state} onChange={e=>{const next=e.target.value;void run(async()=>{await discoveryApi.state(apiUrl,row,next);await list(page.offset,{},true);});}}>{(row.internal_state==='IMPORTED'?['IMPORTED']:['NEW','REVIEW','FOLLOWING','DISCARDED']).map(v=><option key={v} value={v}>{workflowLabels[v]}</option>)}</select></label>
 <a href={row.public_url} target="_blank" rel="noreferrer">Abrir portal público</a>
 </div></details></div>{row.linked_tender&&!row.linked_tender.available&&<p>Licitación eliminada; vínculo conservado</p>}</td></tr>)}
 </tbody></table></TableShell>{!page.items.length&&<p>Sin oportunidades para estos filtros. Revisa el perfil o consulta una fuente soportada; esto no confirma ausencia de procedimientos públicos.</p>}
 <div className="product-actions results-pagination"><Button disabled={busy||page.offset===0} onClick={()=>void run(()=>list(Math.max(0,page.offset-page.limit),{},true))}>Página anterior</Button><Button disabled={busy||page.offset+page.limit>=page.total} onClick={()=>void run(()=>list(page.offset+page.limit,{},true))}>Página siguiente</Button></div></>}
 {detail&&<div className="opportunity-detail"><Button onClick={()=>setDetail(null)}>Cerrar detalle</Button><DiscoveryDetail key={`${detail}:${profileId}`} apiUrl={apiUrl} id={detail} profileId={profileId||undefined} onOpenTender={onOpenTender} onChanged={async()=>{await list(page?.offset??0,{},true);}}/></div>}
 <details id="source-consultation" className="secondary-controls" open={showScan} onToggle={e=>setShowScan(e.currentTarget.open)}><summary>Consultas de fuentes e historial</summary><Notice>Consultar una fuente pública requiere Internet. Los filtros de esta consulta son independientes de los filtros de la lista local.</Notice>
 <label>Fuente para consultar<select value={sourceId} disabled={busy||!!pending.current} onChange={e=>{const id=e.target.value;setSource(id);setAreas(sources.find(s=>s.id===id)?.configuration.areas??[]);setScan(null);setScans([]);setEvent('');setSupply('');void run(async()=>{const values=await discoveryApi.scans(apiUrl,id);if(mounted.current)setScans(values);});}}>{sources.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
 <p>Fuente {source?.enabled?'habilitada':'deshabilitada'} · última consulta: {scanLabels[source?.last_scan_state??'']??'Sin consultas'}</p>
 {restricted&&<p role="status">Automatización no disponible actualmente. La fuente restringe el acceso automatizado.</p>}
 <fieldset disabled={busy||restricted}><legend>Áreas de consulta</legend>{source?.areas.map(a=><label key={a.key}><input type="checkbox" checked={areas.includes(a.key)} onChange={e=>setAreas(e.target.checked?[...areas,a.key]:areas.filter(v=>v!==a.key))}/>{a.label}</label>)}</fieldset>
 <Button disabled={busy||restricted||!areas.length} onClick={()=>void run(async()=>{await discoveryApi.configure(apiUrl,sourceId,{enabled:!source?.enabled,areas});await refresh();})}>{source?.enabled?'Deshabilitar':'Habilitar'} fuente con áreas seleccionadas</Button>
 {source?.capabilities?.requires_date_pair&&<p>Esta fuente requiere ambas fechas o ninguna. Usa un rango acotado para reducir la consulta pública.</p>}
 <label>Consultar publicación desde<input type="date" value={scanFrom} onChange={e=>setScanFrom(e.target.value)}/></label>
 <label>Consultar publicación hasta<input type="date" value={scanTo} onChange={e=>setScanTo(e.target.value)}/></label>
 <label>Tipo de evento<input value={eventType} onChange={e=>setEvent(e.target.value)}/></label>
 <label>Tipo de suministro<input value={supply} onChange={e=>setSupply(e.target.value)}/></label>
 <p>La consulta recorre el conjunto público observado con los filtros seleccionados. Los resultados locales se conservan si la fuente falla; no se garantiza cobertura nacional ni un corte remoto inmutable.</p>
 {!restricted&&<Button variant="primary" disabled={busy||invalidDates||!areas.length||!source?.enabled} onClick={()=>void run(async()=>{
  pending.current=pending.current??{id:crypto.randomUUID(),source:sourceId,query:{areas,published_from:scanFrom||null,published_to:scanTo||null,event_type:eventType||null,supply_type:supply||null,page_size:100}};const result=await discoveryApi.scan(apiUrl,pending.current.source,pending.current.id,pending.current.query);
  pending.current=null;if(mounted.current)setScan(result);await refresh();await list();})}>Consultar fuente ahora</Button>}
 {pending.current&&<Button disabled={busy} onClick={()=>{pending.current=null;setError('');}}>Iniciar otra consulta independiente</Button>}
 <Button disabled={busy} onClick={()=>void run(async()=>{await refresh();})}>Actualizar historial de consultas</Button>
 {scan&&<div role="status"><strong>{scanLabels[scan.status]??'Estado por revisar'}</strong><p>Resultados observados: {scan.metrics.unique_opportunities??'No disponible'} oportunidades únicas · {scan.metrics.rows_retrieved??'No disponible'} filas · {scan.metrics.pages_completed??'No disponible'} páginas o lotes completados.</p>{scan.status==='PARTIAL'&&<p>La cobertura es incompleta. Puedes revisar los resultados conservados y realizar una nueva consulta.</p>}{scan.status==='FAILED'&&<p>No se completó la consulta de esta fuente. Los datos locales anteriores permanecen disponibles.</p>}<details><summary>Diagnóstico de la consulta</summary><p>Páginas o lotes intentados: {scan.metrics.pages_attempted??'No disponible'}</p>{scan.metrics.diagnostics?.map((d,i)=><p key={i}>{d.area}: {d.code}{d.page?` · página ${d.page}`:''}</p>)}</details></div>}
 {scans.map(s=><Button key={s.id} disabled={busy} onClick={()=>setScan(s)}>{displayDate(s.started_at)} · {scanLabels[s.status]??'Estado por revisar'}</Button>)}
 </details>
 <details className="secondary-controls"><summary>Administrar perfiles de búsqueda</summary> <fieldset disabled={busy}><legend>Perfil de interés local</legend>
 <label>Editar perfil<select value={profileId} onChange={e=>chooseProfile(e.target.value)}><option value="">Sin perfil / nuevo</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}{p.active?'':' (inactivo)'}</option>)}</select></label>
 <label>Nombre del perfil<input value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>Incluir cualquiera de estos términos (uno por línea)<textarea value={include} onChange={e=>setInclude(e.target.value)}/></label>
 <label>Excluir (precedencia sobre incluir)<textarea value={exclude} onChange={e=>setExclude(e.target.value)}/></label>
 <label>Sinónimos (PLC=controlador lógico programable|otro)<textarea value={synonyms} onChange={e=>setSynonyms(e.target.value)}/></label>
 <label><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Perfil activo</label>
 <p>Fuentes del perfil: sin selección incluye todas.</p>{sources.map(s=><label key={s.id}><input type="checkbox" checked={profileSources.includes(s.id)} onChange={e=>setProfileSources(e.target.checked?[...profileSources,s.id]:profileSources.filter(id=>id!==s.id))}/>Restringir perfil a {s.id}</label>)}
 <label>Áreas de negocio/empresas del perfil (valores exactos, una por línea)<textarea value={profileAreas} onChange={e=>setProfileAreas(e.target.value)}/></label>
 <Button disabled={!name.trim()} onClick={()=>void run(async()=>{
  const split=(s:string)=>s.split('\n').map(v=>v.trim()).filter(Boolean);const groups:Record<string,string[]>={};
  for(const line of split(synonyms)){const [term,...parts]=line.split('=');if(!term||parts.length!==1)throw new Error('Formato sinónimo');groups[term.trim()]=parts[0].split('|').map(t=>t.trim());}
  const saved=await discoveryApi.saveProfile(apiUrl,{name,include_keywords:split(include),exclude_keywords:split(exclude),synonyms:groups,source_ids:profileSources,business_areas:split(profileAreas),active},profileId||undefined,profiles.find(p=>p.id===profileId)?.revision);
  await refresh();if(mounted.current)setProfile(saved.id);})}>Guardar perfil</Button>
 </fieldset>
</details>
 <Button variant="ghost" disabled={busy} onClick={()=>void run(refresh)}>Actualizar fuentes y perfiles locales</Button>
 </section>;
}
