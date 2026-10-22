import {ProposalReadiness} from "./ProposalReadiness";
import {useEffect,useRef,useState} from "react";
import {boardApi,buckets,dimensions,type BoardRead,type BoardQuery,type Bucket,type Dimension} from "../api/readinessBoard";
import type {Workflow} from "../api/readinessWork";
import {WorkRow} from "./ReadinessWork";
const initial:BoardQuery={search:"",include_inactive:false,offset:0,limit:50};
export function ReadinessBoard({apiUrl,tenderId,disabled}:{apiUrl:string;tenderId:string;disabled:boolean}){
 const [query,setQuery]=useState<BoardQuery>(initial),[data,setData]=useState<BoardRead|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 function filter(change:Partial<BoardQuery>){setQuery(q=>({...q,...change,offset:0}));setData(null);}
 async function read(offset=query.offset){setBusy(true);setError(false);try{const result=await boardApi.read(apiUrl,tenderId,{...query,offset});if(mounted.current){setData(result);setQuery(q=>({...q,offset}));}}catch{if(mounted.current){setError(true);setData(null);}}finally{if(mounted.current)setBusy(false);}}
 return <section aria-label="Board operacional de readiness"><h4>Board de readiness</h4>
 <ProposalReadiness apiUrl={apiUrl} tenderId={tenderId} disabled={disabled||busy}/>
 <p>Fuente canónica y actividad humana separadas. Guardar notas antes de cambiar filtros o consultar de nuevo.</p>
 <fieldset disabled={busy||disabled}><legend>Filtros del board</legend>
 <label>Dimensión <select value={query.dimension??""} onChange={e=>filter({dimension:e.target.value as Dimension||undefined})}><option value="">Todas</option>{dimensions.map(d=><option key={d}>{d}</option>)}</select></label>
 <label>Severidad <select value={query.severity??""} onChange={e=>filter({severity:e.target.value as BoardQuery["severity"]||undefined})}><option value="">Todas activas</option>{["BLOCKER","REVIEW","WARNING"].map(s=><option key={s}>{s}</option>)}</select></label>
 <label>Actividad <select value={query.workflow_status??""} onChange={e=>filter({workflow_status:e.target.value as Workflow||undefined})}><option value="">Todas</option>{["OPEN","IN_REVIEW","RESOLVED","ACCEPTED_RISK","NOT_APPLICABLE"].map(s=><option key={s}>{s}</option>)}</select></label>
 <label>Sección <select value={query.bucket??""} onChange={e=>filter({bucket:e.target.value as Bucket||undefined})}><option value="">Todas</option>{buckets.map(b=><option key={b}>{b}</option>)}</select></label>
 <label>Buscar resumen o referencia <input maxLength={200} value={query.search} onChange={e=>filter({search:e.target.value})}/></label>
 <label><input type="checkbox" checked={query.include_inactive} onChange={e=>filter({include_inactive:e.target.checked})}/>Incluir historia resuelta u obsoleta</label>
 <button onClick={()=>void read(0)}>Consultar board</button></fieldset>
 {error&&<p role="alert">No se pudo consultar el board. Vuelve a consultar el contexto vigente.</p>}
 {data&&<><p>{data.notice}</p><h5>Fuente canónica</h5><p>Estado global: {data.canonical_summary.status} · Bloqueos/faltantes: {data.canonical_summary.blocker_count} · Revisar: {data.canonical_summary.review_required_count} · Advertencias: {data.canonical_summary.warning_count}</p>
 <p>Handoff futuro MVP-09: {data.canonical_summary.blocker_count} bloqueos/faltantes canónicos; cerrar actividades no completa datos de propuesta.</p>
 <h5>Actividad humana</h5><p>{Object.entries(data.work_summary).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>
 <p>Trabajo rastreado resuelto por fuente: {data.work_summary.resolved??0}. Riesgos aceptados visibles: {data.work_summary.accepted_risks??0}. Sin porcentaje de cumplimiento.</p>
 <table><caption>Dimensiones canónicas y trabajo abierto</caption><thead><tr><th>Dimensión</th><th>Estado fuente</th><th>Bloqueos/faltantes</th><th>Revisar</th><th>Advertencias</th><th>Trabajo abierto</th></tr></thead><tbody>{data.dimensions.map(d=><tr key={d.dimension}><td>{d.dimension}</td><td>{d.status}</td><td>{d.blocker_count}</td><td>{d.review_count}</td><td>{d.warning_count}</td><td>{d.open_work_count}</td></tr>)}</tbody></table>
 <p>Secciones del Tender (incluyen historia anotada): {Object.entries(data.bucket_counts).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>
 <p>{data.total_filtered} resultados; página de hasta {data.limit} filas. Orden: bloqueos duros, revisión pendiente, incompletos, advertencias, aceptados/resueltos.</p>
 {data.items.map(row=><div key={`${row.work.id}:${row.work.revision}:${row.work.context_sha256}`}><h5>{row.bucket} · Prioridad {row.priority+1}</h5>
 {row.source_target&&<a href={`${apiUrl}${row.source_target}`} target="_blank" rel="noreferrer">Consultar fuente</a>}
 <WorkRow item={{...row.work,action_target:row.action_target}} apiUrl={apiUrl} tenderId={tenderId} disabled={disabled||busy} onSaved={()=>read()}/></div>)}
 <button disabled={disabled||busy||data.offset===0} onClick={()=>void read(Math.max(0,data.offset-data.limit))}>Página anterior</button><button disabled={disabled||busy||data.offset+data.items.length>=data.total_filtered} onClick={()=>void read(data.offset+data.limit)}>Página siguiente</button></>}
 </section>;
}
