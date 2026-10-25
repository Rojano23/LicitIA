import {DiscoveryDetail} from './DiscoveryDetail';
import {monitoringApi} from '../api/discovery';
import {useRef,useState,useEffect} from 'react';
import {Button,Notice,SourceBadge,StatusBadge,TableShell} from '../ui/primitives';
import {workflowLabels,scanLabels,matchLabel,sourceName,displayDate} from '../ui/discoveryPresentation';
import './discovery.css';
import {PeriodFilter,resolvePeriod,type Period} from './discoveryPeriods';
import {DiscoveryHelp,filterHelp} from './discoveryHelp';
import {discoveryApi,type Source,type Profile,type Page,type Scan,type SourceQuery} from '../api/discovery';
export function DiscoveryView({apiUrl,onOpenTender,view='all',opportunityId,scanId,filterRequest}:{apiUrl:string;onOpenTender?:(id:string)=>void;view?:string;opportunityId?:string;scanId?:string;scanSource?:string;filterRequest?:object}){

 const [rowFeedback,setRowFeedback]=useState<Record<string,string>>({});
 const [detailTarget,setDetailTarget]=useState<'top'|'changes'>('top');
 const returnRow=useRef<string|null>(null);
 const [scanPeriod,setScanPeriod]=useState<Period>('30'),[listPeriod,setListPeriod]=useState<Period>('all');
 const initialRange=resolvePeriod('30');
 const listGeneration=useRef(0), workCount=useRef(0);
 const applied=useRef<Record<string,string|number|boolean|undefined>>({});
 const [localEvent,setLocalEvent]=useState(''),[localSupply,setLocalSupply]=useState('');
 const [scanFrom,setScanFrom]=useState(initialRange.from),[scanTo,setScanTo]=useState(initialRange.to);
 const [detail,setDetail]=useState<string|null>(null),[following,setFollowing]=useState(false),[unread,setUnread]=useState(false);
 const [sources,setSources]=useState<Source[]>([]),[sourceId,setSource]=useState('PEMEX'),[areas,setAreas]=useState<string[]>([]);
 const [listSource,setListSource]=useState(''),[localArea,setLocalArea]=useState('');
 const [profiles,setProfiles]=useState<Profile[]>([]),[profileId,setProfile]=useState(''),[matched,setMatched]=useState(false);
 const [page,setPage]=useState<Page|null>(null),[scans,setScans]=useState<Scan[]>([]),[scan,setScan]=useState<Scan|null>(null);
 const [errorArea,setErrorArea]=useState<'query'|'results'>('results');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[search,setSearch]=useState(''),[state,setState]=useState('');
 const [dateFrom,setFrom]=useState(''),[dateTo,setTo]=useState(''),[eventType,setEvent]=useState(''),[supply,setSupply]=useState('');
 const mounted=useRef(true),pending=useRef<{id:string;source:string;query:SourceQuery}|null>(null);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const source=sources.find(s=>s.id===sourceId);
 const isRestricted=(id:string)=>sources.find(s=>s.id===id)?.capabilities?.automation_status==='DEFERRED_SOURCE_AUTOMATION_RESTRICTED';
 const restricted=isRestricted(sourceId);
 const invalidDates=!!source?.capabilities?.requires_date_pair&&!!scanFrom!==!!scanTo || !!scanFrom&&!!scanTo&&scanFrom>scanTo;
 async function run(action:()=>Promise<void>,area:'query'|'results'='results'){setErrorArea(area);workCount.current++;setBusy(true);setError('');try{await action();}catch{if(mounted.current)setError('No se pudo completar la acción. Los resultados anteriores se conservan. Revisa la consulta de la fuente o vuelve a consultar los datos locales.');}finally{workCount.current--;if(mounted.current)setBusy(workCount.current>0);}}
 async function list(offset=0,override:Record<string,string|number|boolean|undefined>={},reuse=false){
  const request=++listGeneration.current;
  const current={source:listSource||undefined,area:localArea||undefined,search:search||undefined,profile_id:profileId||undefined,matched_only:matched&&!!profileId,following,unread_only:unread,internal_state:state||undefined,published_from:dateFrom||undefined,published_to:dateTo||undefined,event_type:localEvent||undefined,supply_type:localSupply||undefined,...override};
  const params=reuse||offset>0?applied.current:current;
  const result=await discoveryApi.list(apiUrl,{...params,offset,limit:50});
  if(mounted.current&&request===listGeneration.current){applied.current=params;setPage(result);}
 }
 async function refresh(){
  const values=await Promise.allSettled([discoveryApi.sources(apiUrl),discoveryApi.profiles(apiUrl),discoveryApi.scans(apiUrl,sourceId)]);
  if(!mounted.current)return;
  if(values[0].status==='fulfilled'){setSources(values[0].value);if(!areas.length)setAreas(values[0].value.find(v=>v.id===sourceId)?.configuration.areas??[]);}
  if(values[1].status==='fulfilled')setProfiles(values[1].value);
  if(values[2].status==='fulfilled'){const history=values[2].value;setScans(history);setScan(previous=>!previous?history[0]??null:history[0]&&new Date(history[0].started_at)>new Date(previous.started_at)?history[0]:previous);}
  if(values.some(v=>v.status==='rejected'))setError('No se pudo actualizar parte de la configuración o historial. Los resultados guardados permanecen disponibles.');
 }
 useEffect(()=>{void run(async()=>{await refresh();});},[apiUrl]);
 useEffect(()=>{
  const next={internal_state:view==='new'?'NEW':view==='imported'?'IMPORTED':view==='discarded'?'DISCARDED':undefined,following:view==='following'||view==='following-changes',unread_only:view==='changes'||view==='following-changes'};
  setState(next.internal_state??'');setFollowing(next.following);setUnread(next.unread_only);
  setListSource('');setLocalArea('');setSearch('');chooseProfile('');setMatched(false);setFrom('');setTo('');setLocalEvent('');setLocalSupply('');setListPeriod('all');
  void run(()=>list(0,{...next,source:undefined,area:undefined,source_status:undefined,search:undefined,profile_id:undefined,matched_only:false,published_from:undefined,published_to:undefined,event_type:undefined,supply_type:undefined}));
 },[view,filterRequest]);
 useEffect(()=>{if(opportunityId){setDetailTarget('top');setDetail(opportunityId)};},[opportunityId]);
 function focusStep(id:string){const el=document.getElementById(id);el?.focus();el?.scrollIntoView?.({block:'start'});}
 function review(id:string,changes=false){returnRow.current=id;setDetailTarget(changes?'changes':'top');setDetail(id);}
 function back(){const id=returnRow.current;setDetail(null);requestAnimationFrame(()=>{const button=Array.from(document.querySelectorAll<HTMLButtonElement>('[data-review-id]')).find(el=>el.dataset.reviewId===id);if(button){button.focus();button.scrollIntoView?.({block:'center'});}else focusStep('opportunity-results');});}
 async function rowAction(id:string,action:()=>Promise<void>,message:string){setRowFeedback(old=>({...old,[id]:''}));try{await action();setRowFeedback(old=>({...old,[id]:message}));}catch{setRowFeedback(old=>({...old,[id]:'No se pudo completar. Revisa el estado antes de repetir.'}));}}

 useEffect(()=>{const refreshProfiles=()=>{void run(refresh);};window.addEventListener('discovery-profiles-changed',refreshProfiles);return()=>window.removeEventListener('discovery-profiles-changed',refreshProfiles);},[apiUrl,sourceId]);
 async function viewResults(){if(!scan?.source_id)return;const q=scan.query;
  const context={source:scan.source_id,published_from:q?.published_from||undefined,published_to:q?.published_to||undefined,area:undefined,event_type:undefined,supply_type:undefined,search:undefined,internal_state:undefined,following:false,unread_only:false,profile_id:profileId||undefined,matched_only:matched&&!!profileId};
  setListSource(scan.source_id);setFrom(q?.published_from??'');setTo(q?.published_to??'');setListPeriod(q?.published_from||q?.published_to?'custom':'all');setLocalArea('');setLocalEvent('');setLocalSupply('');setSearch('');setState('');setFollowing(false);setUnread(false);
  await list(0,context);focusStep('stored-filters');
 }

 useEffect(()=>{if(scanId)window.location.hash='#/configuracion/diagnostico';},[scanId]);
 function chooseProfile(id:string){setProfile(id);}
 return <section className="discovery-product" aria-label="Discovery público"><div hidden={!!detail}>
 <div className="source-strip" aria-label="Estado de fuentes">{sources.map(s=><span key={s.id}><SourceBadge name={sourceName(s.id)} restricted={isRestricted(s.id)}/>{!isRestricted(s.id)&&<small> · {s.enabled?'Disponible para consulta':'Deshabilitada'} · {scanLabels[s.last_scan_state??'']??'Sin consultas'}</small>}</span>)}</div>
 <section id="source-consultation" tabIndex={-1} className="discovery-step"><h2>1. Consultar una fuente</h2><Notice>Consultar una fuente pública requiere Internet. Los filtros de esta consulta son independientes de los filtros de la lista de oportunidades guardadas.</Notice>
 <label>Fuente para consultar<select value={sourceId} disabled={busy||!!pending.current} onChange={e=>{const id=e.target.value;setSource(id);setAreas(sources.find(s=>s.id===id)?.configuration.areas??[]);setScan(null);setScans([]);setEvent('');setSupply('');void run(async()=>{const values=await discoveryApi.scans(apiUrl,id);if(mounted.current){setScans(values);setScan(values[0]??null);}});}}>{sources.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
 <p>Fuente {source?.enabled?'habilitada':'deshabilitada'} · última consulta: {scanLabels[source?.last_scan_state??'']??'Sin consultas'}</p>
 {restricted&&<p role="status">Automatización no disponible actualmente. La fuente restringe el acceso automatizado.</p>}
 <fieldset disabled={busy||restricted}><legend>Áreas de consulta</legend>{source?.areas.map(a=><label key={a.key}><input type="checkbox" checked={areas.includes(a.key)} disabled={!source?.configuration.areas.includes(a.key)} onChange={e=>setAreas(e.target.checked?[...areas,a.key]:areas.filter(v=>v!==a.key))}/>{a.label}</label>)}</fieldset>
 {!restricted&&source&&!source.enabled&&<p>Esta fuente está deshabilitada. <a href="#/configuracion?section=sources">Configurar fuente</a></p>}
 {!restricted&&source&&source.areas.some(a=>!source.configuration.areas.includes(a.key))&&<p>Para habilitar otras áreas, <a href="#/configuracion?section=sources">configura la fuente</a>.</p>}
 {source?.capabilities?.requires_date_pair&&<p>Esta fuente requiere ambas fechas o ninguna. Usa un rango acotado para reducir la consulta pública.</p>}
 <div className="discovery-filters">
 <PeriodFilter label="Periodo de publicación" value={scanPeriod} from={scanFrom} to={scanTo} onChange={(period,range)=>{setScanPeriod(period);setScanFrom(range.from);setScanTo(range.to);}}/>
 <div className="discovery-filter-field"><label>Tipo de evento{sourceId==='CFE'?<select value={eventType} onChange={e=>setEvent(e.target.value)}><option value="">Todos</option>{['Concurso abierto','Concurso simplificado','Adjudicación directa'].map(value=><option key={value} value={value}>{value}</option>)}</select>:<input value={eventType} placeholder="Nacional" onChange={e=>setEvent(e.target.value)}/>}</label><DiscoveryHelp name="Tipo de evento de consulta">{filterHelp(sourceId,'event',true)}</DiscoveryHelp></div>
 <div className="discovery-filter-field"><label>Tipo de suministro<input value={supply} placeholder={sourceId==='CFE'?'Adquisición por Abastecimientos':'Bienes'} onChange={e=>setSupply(e.target.value)}/></label><DiscoveryHelp name="Tipo de suministro de consulta">{filterHelp(sourceId,'supply')}</DiscoveryHelp></div>
 </div>
 <p>La consulta recorre el conjunto público observado con los filtros seleccionados. Los resultados locales se conservan si la fuente falla; no se garantiza cobertura nacional ni un corte remoto inmutable.</p>
 {busy&&errorArea==='query'&&<p role="status">Consultando fuente…</p>}
 {error&&errorArea==='query'&&<p role="alert">{error}</p>}
 {!restricted&&<Button variant="primary" disabled={busy||invalidDates||!areas.length||!source?.enabled} onClick={()=>void run(async()=>{
  pending.current=pending.current??{id:crypto.randomUUID(),source:sourceId,query:{areas,published_from:scanFrom||null,published_to:scanTo||null,event_type:eventType||null,supply_type:supply||null,page_size:100}};const result=await discoveryApi.scan(apiUrl,pending.current.source,pending.current.id,pending.current.query);
  pending.current=null;if(mounted.current){setScan(result);requestAnimationFrame(()=>focusStep('scan-result'));}await refresh();await list();},'query')}>Consultar fuente</Button>}
 {pending.current&&<Button disabled={busy} onClick={()=>{pending.current=null;setError('');}}>Iniciar otra consulta independiente</Button>}
 </section>
 <section id="scan-result" tabIndex={-1} className="discovery-step" aria-label="Resultado de la consulta"><h2>2. Resultado de la consulta</h2>
 {scan?<div role="status"><strong>{scanLabels[scan.status]??'Estado por revisar'}</strong><p>{sourceName(scan.source_id??sourceId)} · {displayDate(scan.started_at)}</p><p>Periodo consultado: {scan.query?.published_from?displayDate(scan.query.published_from):'Sin inicio indicado'} — {scan.query?.published_to?displayDate(scan.query.published_to):'Sin fin indicado'}</p><p>{scan.metrics.unique_opportunities??'No disponible'} oportunidades · {scan.metrics.pages_completed??'No disponible'} lotes</p>{scan.status==='PARTIAL'&&<p>La cobertura es incompleta. Puedes revisar los resultados conservados y realizar una nueva consulta.</p>}{scan.status==='FAILED'&&<p>No se completó la consulta de esta fuente. Los datos guardados anteriores permanecen disponibles.</p>}

 <Button disabled={busy||!scan.source_id||scan.status==='RUNNING'} onClick={()=>void run(viewResults)}>Ver resultados</Button>
 </div>:<p>Aún no hay una consulta para esta fuente.</p>}
 </section>
 <section id="stored-filters" tabIndex={-1} className="discovery-step"><h2>3. Filtrar oportunidades guardadas</h2>
 <div className="discovery-filters">
 <label>Fuente de oportunidades guardadas<select value={listSource} onChange={e=>{setListSource(e.target.value);}}><option value="">Todas las fuentes</option>{sources.map(s=><option key={s.id} value={s.id}>{sourceName(s.id)}</option>)}</select></label>
 <label>Perfil de búsqueda<select value={profileId} onChange={e=>chooseProfile(e.target.value)}><option value="">Sin perfil</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}{p.active?'':' (inactivo)'}</option>)}</select></label>
 <a href="#/configuracion?section=profiles">Administrar perfiles</a>
 <label>Buscar procedimiento, descripción o área<input value={search} maxLength={200} onChange={e=>setSearch(e.target.value)}/></label>
 <PeriodFilter allowAll label="Periodo de oportunidades" value={listPeriod} from={dateFrom} to={dateTo} onChange={(period,range)=>{setListPeriod(period);setFrom(range.from);setTo(range.to);}}/>
 <label>Estado interno<select value={state} onChange={e=>setState(e.target.value)}><option value="">Todos</option>{Object.entries(workflowLabels).map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label>
 <label><input type="checkbox" checked={matched} disabled={!profileId} onChange={e=>setMatched(e.target.checked)}/>Sólo coincidencias del perfil</label>
 <label><input type="checkbox" checked={following} onChange={e=>setFollowing(e.target.checked)}/>Siguiendo</label><label><input type="checkbox" checked={unread} onChange={e=>setUnread(e.target.checked)}/>Cambios sin leer</label>
 <Button disabled={busy||!!dateFrom&&!!dateTo&&dateFrom>dateTo} onClick={()=>void run(()=>list())}>Aplicar filtros</Button>
 </div>
 <details className="secondary-controls"><summary>Más filtros</summary><div className="discovery-filters">
 <div className="discovery-filter-field"><label>Área o entidad<input value={localArea} placeholder="Área responsable indicada por la fuente" onChange={e=>setLocalArea(e.target.value)}/></label><DiscoveryHelp name="Área o entidad">Área responsable o entidad que publica o contrata. Usa el nombre que aparece en la oportunidad; no todas las fuentes lo informan de la misma forma.</DiscoveryHelp></div>
 <div className="discovery-filter-field"><label>Tipo de evento<input value={localEvent} placeholder={listSource==='CFE'?'Concurso abierto':'Nacional'} onChange={e=>setLocalEvent(e.target.value)}/></label><DiscoveryHelp name="Tipo de evento">{filterHelp(listSource,'event')}</DiscoveryHelp></div>
 <div className="discovery-filter-field"><label>Tipo de suministro<input value={localSupply} placeholder={listSource==='CFE'?'Adquisición por Abastecimientos':'Bienes'} onChange={e=>setLocalSupply(e.target.value)}/></label><DiscoveryHelp name="Tipo de suministro">{filterHelp(listSource,'supply')}</DiscoveryHelp></div>
 </div></details></section>
 <section id="opportunity-results" tabIndex={-1} className="discovery-step"><h2>4. Revisar oportunidades</h2>
 {busy&&<p role="status">Actualizando información…</p>}
 {error&&errorArea==='results'&&<div role="alert"><p>{error}</p><Button onClick={()=>void run(async()=>{await refresh();await list();})}>Volver a consultar datos locales</Button></div>}
 {page&&<><p className="ui-secondary">{page.total} oportunidades guardadas · Mostrando {page.items.length? page.offset+1:0}–{Math.min(page.offset+page.items.length,page.total)}. Resultados de los filtros aplicados. Las consultas parciales no certifican cobertura completa.</p>
 <TableShell label="Oportunidades" empty={!page.items.length}><table className="opportunities-table"><thead><tr>{['Fuente / Procedimiento','Descripción','Publicación / Área','Coincidencia','Documentos / Cambios','Estado','Acciones'].map(h=><th scope="col" key={h}>{h}</th>)}</tr></thead><tbody>
 {page.items.map(row=><tr key={row.id}><td><strong>{sourceName(row.source_id)}</strong><br/>{row.procedure_number??'Número no publicado'}</td><td><Button variant="ghost" className="description-link" disabled={isRestricted(row.source_id)} title={row.title} onClick={()=>review(row.id)}>{row.title}</Button></td><td>{displayDate(row.published_date)}<br/>{row.contracting_area??row.business_area}</td><td>{matchLabel(row.match)}</td><td className={(row.unread_changes??0)>0?"opportunity-pending-changes":undefined}>{row.document_count} referencias descubiertas<br/>{row.unread_changes??0} cambios sin leer{(row.unread_document_changes??0)>0&&<small> · {row.unread_document_changes} documentales</small>}{row.source_changes_available&&<p>Hay cambios desde la creación</p>}</td><td><StatusBadge tone={row.internal_state==='NEW'?'info':'neutral'}>{workflowLabels[row.internal_state]??'Por revisar'}</StatusBadge>{row.watching&&row.internal_state!=='FOLLOWING'&&<small>Siguiendo</small>}</td>
 <td><div className="row-actions">{row.linked_tender?.available?<Button className="row-primary-action" disabled={!onOpenTender} onClick={()=>onOpenTender?.(row.linked_tender!.id)}>Abrir licitación</Button>:<Button data-review-id={row.id} className="row-primary-action" disabled={busy||isRestricted(row.source_id)} onClick={()=>review(row.id)}>Revisar</Button>}
 <details><summary>Más acciones</summary><div className="action-list">
 <Button disabled={busy||isRestricted(row.source_id)} onClick={()=>review(row.id,!!row.unread_changes)}>{row.unread_changes?'Ver cambios':'Ver detalle / Crear licitación'}</Button>
 <Button disabled={busy||isRestricted(row.source_id)} onClick={()=>void run(()=>rowAction(row.id,async()=>{await monitoringApi.follow(apiUrl,row);await list(page.offset,{},true);},row.watching?'Dejaste de seguir esta oportunidad':'Siguiendo esta oportunidad'))}>{row.watching?'Dejar de seguir':'Seguir'}</Button>
 <label>Estado interno {row.procedure_number??row.title}<select disabled={busy||row.internal_state==='IMPORTED'||isRestricted(row.source_id)} value={row.internal_state} onChange={e=>{const next=e.target.value;void run(()=>rowAction(row.id,async()=>{await discoveryApi.state(apiUrl,row,next);await list(page.offset,{},true);},'Estado actualizado'));}}>{(row.internal_state==='IMPORTED'?['IMPORTED']:['NEW','REVIEW','FOLLOWING','DISCARDED']).map(v=><option key={v} value={v}>{workflowLabels[v]}</option>)}</select></label>
 <a href={row.public_url} target="_blank" rel="noreferrer">Abrir portal público</a>
 </div></details>{rowFeedback[row.id]&&<p role="status">{rowFeedback[row.id]}</p>}</div>{row.linked_tender&&!row.linked_tender.available&&<p>Licitación eliminada; vínculo conservado</p>}</td></tr>)}
 </tbody></table></TableShell>{!page.items.length&&sources.length>0&&sources.every(s=>!s.last_scan_state)&&scans.length===0&&page.total===0&&!Object.values(applied.current).some(Boolean)&&<p>Aún no hay oportunidades consultadas. Comienza consultando PEMEX o CFE. Consulta una fuente en el paso 1.</p>}{!page.items.length&&<p>Sin oportunidades para estos filtros. Revisa el perfil o consulta una fuente soportada; esto no confirma ausencia de procedimientos públicos.</p>}
 <div className="product-actions results-pagination"><Button disabled={busy||page.offset===0} onClick={()=>void run(()=>list(Math.max(0,page.offset-page.limit),{},true))}>Página anterior</Button><Button disabled={busy||page.offset+page.limit>=page.total} onClick={()=>void run(()=>list(page.offset+page.limit,{},true))}>Página siguiente</Button></div></>}
 </section>
 <Button variant="ghost" disabled={busy} onClick={()=>void run(refresh)}>Actualizar fuentes y perfiles locales</Button>
 </div>
 {detail&&<div className="opportunity-detail"><Button onClick={back}>← Volver a oportunidades</Button><DiscoveryDetail key={`${detail}:${profileId}`} apiUrl={apiUrl} focusTarget={detailTarget} id={detail} profileId={profileId||undefined} onOpenTender={onOpenTender} onChanged={async()=>{await list(page?.offset??0,{},true);}}/></div>}

 </section>;
}
