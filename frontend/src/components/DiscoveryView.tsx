import {useRef,useState,useEffect} from 'react';
import {discoveryApi,type Source,type Profile,type Page,type Scan,type SourceQuery} from '../api/discovery';
export function DiscoveryView({apiUrl}:{apiUrl:string}){
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
 const restricted=source?.capabilities?.automation_status==='DEFERRED_SOURCE_AUTOMATION_RESTRICTED';
 const invalidDates=!!source?.capabilities?.requires_date_pair&&!!dateFrom!==!!dateTo;
 async function run(action:()=>Promise<void>){setBusy(true);setError('');try{await action();}catch{if(mounted.current)setError('No se pudo completar la acción. Revisa el estado de la fuente y los diagnósticos; no se creó ningún Tender.');}finally{if(mounted.current)setBusy(false);}}
 async function list(offset=0){const result=await discoveryApi.list(apiUrl,{source:listSource||undefined,area:localArea||undefined,source_status:sourceStatus||undefined,
  search:search||undefined,profile_id:profileId||undefined,matched_only:matched&&!!profileId,internal_state:state||undefined,
  published_from:dateFrom||undefined,published_to:dateTo||undefined,event_type:eventType||undefined,supply_type:supply||undefined,offset,limit:50});if(mounted.current)setPage(result);}
 async function refresh(){const [s,p,r]=await Promise.all([discoveryApi.sources(apiUrl),discoveryApi.profiles(apiUrl),discoveryApi.scans(apiUrl,sourceId)]);if(mounted.current){setSources(s);setProfiles(p);setScans(r);if(!areas.length)setAreas(s.find(v=>v.id===sourceId)?.configuration.areas??[]);}}
 function chooseProfile(id:string){setProfile(id);const p=profiles.find(p=>p.id===id);setName(p?.name??'');setInclude(p?.include_keywords.join('\n')??'');setExclude(p?.exclude_keywords.join('\n')??'');setSynonyms(Object.entries(p?.synonyms??{}).map(([key,values])=>`${key}=${values.join('|')}`).join('\n'));setActive(p?.active??true);setProfileSources(p?.source_ids??[]);setProfileAreas(p?.business_areas.join('\n')??'');}
 return <section aria-label="Discovery público"><h2>Discovery público — opcional</h2>
 <p>Consulta oportunidades públicas sin crear ni analizar un Tender. Los perfiles se evalúan localmente y no se envían al portal.</p>
 <button disabled={busy} onClick={()=>void run(refresh)}>Consultar fuentes Discovery</button>
 {sources.length>0&&<>
 <label>Fuente para scan<select value={sourceId} disabled={busy||!!pending.current} onChange={e=>{setSource(e.target.value);setAreas(sources.find(s=>s.id===e.target.value)?.configuration.areas??[]);setScan(null);setScans([]);setEvent('');setSupply('');}}>{sources.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
 <p>Fuente {source?.enabled?'habilitada':'deshabilitada'} · último scan: {source?.last_scan_state??'sin escaneos'} · {source?.last_error??''}</p>
 {restricted&&<p role="status">{source?.capabilities?.message??'DEFERRED — SOURCE AUTOMATION RESTRICTED'}</p>}
 <fieldset disabled={busy||restricted}><legend>Áreas de consulta</legend>{source?.areas.map(a=><label key={a.key}><input type="checkbox" checked={areas.includes(a.key)} onChange={e=>setAreas(e.target.checked?[...areas,a.key]:areas.filter(v=>v!==a.key))}/>{a.label}</label>)}</fieldset>
 <button disabled={busy||restricted||!areas.length} onClick={()=>void run(async()=>{await discoveryApi.configure(apiUrl,sourceId,{enabled:!source?.enabled,areas});await refresh();})}>{source?.enabled?'Deshabilitar':'Habilitar'} fuente con áreas seleccionadas</button>
 {source?.capabilities?.requires_date_pair&&<p>Esta fuente requiere ambas fechas o ninguna. Usa un rango acotado para reducir la consulta pública.</p>}
 <label>Publicado desde<input type="date" value={dateFrom} onChange={e=>setFrom(e.target.value)}/></label>
 <label>Publicado hasta<input type="date" value={dateTo} onChange={e=>setTo(e.target.value)}/></label>
 <label>Tipo de evento<input value={eventType} onChange={e=>setEvent(e.target.value)}/></label>
 <label>Tipo de suministro<input value={supply} onChange={e=>setSupply(e.target.value)}/></label>
 <p>El scan recorre todos los batches del filtro público; algunas fuentes entregan un array completo paginado localmente. Los conteos y fallos de adquisición se muestran por separado de los matches.</p>
 <button disabled={busy||restricted||invalidDates||!areas.length||!source?.enabled} onClick={()=>void run(async()=>{
  pending.current=pending.current??{id:crypto.randomUUID(),source:sourceId,query:{areas,published_from:dateFrom||null,published_to:dateTo||null,event_type:eventType||null,supply_type:supply||null,page_size:100}};const result=await discoveryApi.scan(apiUrl,pending.current.source,pending.current.id,pending.current.query);
  pending.current=null;if(mounted.current)setScan(result);await refresh();await list();})}>Ejecutar scan manual</button>
 {pending.current&&<button disabled={busy} onClick={()=>{pending.current=null;setError('');}}>Nueva solicitud independiente de scan</button>}
 <button disabled={busy} onClick={()=>void run(async()=>{await refresh();if(scans[0])setScan(scans[0]);})}>Consultar historial de scans</button>
 {scan&&<div role="status">Scan {scan.status} · páginas {scan.metrics.pages_completed??0}/{scan.metrics.pages_attempted??0} · filas {scan.metrics.rows_retrieved??0} · oportunidades únicas {scan.metrics.unique_opportunities??0}
 {scan.metrics.diagnostics?.map((d,i)=><p key={i}>{d.area}: {d.code}{d.page?` · página ${d.page}`:''}</p>)}</div>}
 {scans.map(s=><button key={s.id} disabled={busy} onClick={()=>setScan(s)}>{s.started_at} · {s.status}</button>)}
 <fieldset disabled={busy}><legend>Perfil de interés local</legend>
 <label>Perfil<select value={profileId} onChange={e=>chooseProfile(e.target.value)}><option value="">Sin perfil / nuevo</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}{p.active?'':' (inactivo)'}</option>)}</select></label>
 <label>Nombre del perfil<input value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>Incluir (ANY, uno por línea)<textarea value={include} onChange={e=>setInclude(e.target.value)}/></label>
 <label>Excluir (precedencia sobre incluir)<textarea value={exclude} onChange={e=>setExclude(e.target.value)}/></label>
 <label>Sinónimos (PLC=controlador lógico programable|otro)<textarea value={synonyms} onChange={e=>setSynonyms(e.target.value)}/></label>
 <label><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Perfil activo</label>
 <p>Fuentes del perfil: sin selección incluye todas.</p>{sources.map(s=><label key={s.id}><input type="checkbox" checked={profileSources.includes(s.id)} onChange={e=>setProfileSources(e.target.checked?[...profileSources,s.id]:profileSources.filter(id=>id!==s.id))}/>Restringir perfil a {s.id}</label>)}
 <label>Áreas de negocio/empresas del perfil (valores exactos, una por línea)<textarea value={profileAreas} onChange={e=>setProfileAreas(e.target.value)}/></label>
 <button disabled={!name.trim()} onClick={()=>void run(async()=>{
  const split=(s:string)=>s.split('\n').map(v=>v.trim()).filter(Boolean);const groups:Record<string,string[]>={};
  for(const line of split(synonyms)){const [term,...parts]=line.split('=');if(!term||parts.length!==1)throw new Error('Formato sinónimo');groups[term.trim()]=parts[0].split('|').map(t=>t.trim());}
  const saved=await discoveryApi.saveProfile(apiUrl,{name,include_keywords:split(include),exclude_keywords:split(exclude),synonyms:groups,source_ids:profileSources,business_areas:split(profileAreas),active},profileId||undefined,profiles.find(p=>p.id===profileId)?.revision);
  await refresh();if(mounted.current)setProfile(saved.id);})}>Guardar perfil</button>
 </fieldset>
 <label>Fuente de oportunidades locales<select value={listSource} onChange={e=>{setListSource(e.target.value);setPage(null);}}><option value="">All sources</option>{sources.map(s=><option key={s.id} value={s.id}>{s.id==='COMPRAS_MX'?'Compras MX':s.id}</option>)}</select></label>
 <label>Área o entidad (valor exacto)<input value={localArea} onChange={e=>setLocalArea(e.target.value)}/></label>
 <label>Buscar procedimiento, descripción o área<input value={search} onChange={e=>setSearch(e.target.value)}/></label>
 <label>Estado fuente (valor literal)<input value={sourceStatus} onChange={e=>setSourceStatus(e.target.value)}/></label>
 <label>Estado interno<select value={state} onChange={e=>setState(e.target.value)}><option value="">Todos</option>{['NEW','REVIEW','FOLLOWING','DISCARDED'].map(v=><option key={v}>{v}</option>)}</select></label>
 <label><input type="checkbox" checked={matched} onChange={e=>setMatched(e.target.checked)}/>Sólo coincidencias del perfil</label>
 <button disabled={busy} onClick={()=>void run(()=>list())}>Consultar oportunidades locales</button>
 {page&&<><p>{page.total} oportunidades locales. Un scan PARTIAL no certifica cobertura completa del portal.</p>
 <table><thead><tr>{['Fuente / Evento','Descripción','Publicado / Área','Evento / Suministro','Estado fuente','Estado interno','Coincidencias','Documentos'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>
 {page.items.map(row=><tr key={row.id}><td>{row.source_id} · <a href={row.public_url} target="_blank" rel="noreferrer">{row.procedure_number??row.external_id}</a>{row.procedure_number&&<small> · ID {row.external_id} · abrir portal público</small>}{row.internal_state==='NEW'?' · NEW':''}</td><td>{row.title}</td><td>{row.published_date??'Sin fecha'} · {row.business_area}{row.contracting_area?` · ${row.contracting_area}`:''}</td><td>{row.event_type??'—'} · {row.supply_type??'—'}</td><td>{row.source_status??'No publicado'}</td>
 <td><select aria-label={`Estado interno ${row.external_id}`} disabled={busy} value={row.internal_state} onChange={e=>{const next=e.target.value;void run(async()=>{await discoveryApi.state(apiUrl,row,next);await list(page.offset);});}}>{['NEW','REVIEW','FOLLOWING','DISCARDED'].map(v=><option key={v}>{v}</option>)}</select></td>
 <td>{row.match&&<>{row.match.matched?'Matched profile':'Sin coincidencia'}{row.match.include_hits.map((h,i)=><p key={`i${i}`}>{h.kind}: {h.term} → {h.matched_text} ({h.field})</p>)}{row.match.exclude_hits.map((h,i)=><p key={`e${i}`}>Excluido: {h.term} ({h.field})</p>)}{row.match.restrictions.join(', ')}</>}</td><td>{row.document_count} referencias descubiertas; sin descargar</td></tr>)}
 </tbody></table><button disabled={busy||page.offset===0} onClick={()=>void run(()=>list(Math.max(0,page.offset-50)))}>Página anterior</button><button disabled={busy||page.offset+page.limit>=page.total} onClick={()=>void run(()=>list(page.offset+50))}>Página siguiente</button></>}
 </>}{busy&&<p role="status">Procesando solicitud Discovery; las adquisiciones pueden recorrer varias páginas.</p>}{error&&<p role="alert">{error}</p>}
 </section>;
}
