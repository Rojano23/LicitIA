import {useEffect,useRef,useState} from "react";
import {workApi,type WorkItem,type WorkRead,type Workflow,type WorkEvent} from "../api/readinessWork";
export function WorkRow({item,apiUrl,tenderId,disabled,onSaved}:{item:WorkItem;apiUrl:string;tenderId:string;disabled:boolean;onSaved:()=>Promise<void>}){
 const [state,setState]=useState<Workflow>(item.workflow_status),[note,setNote]=useState(item.note??""),[owner,setOwner]=useState(item.owner??""),[actor,setActor]=useState("");
 const [busy,setBusy]=useState(false),[error,setError]=useState(false),[history,setHistory]=useState<WorkEvent[]|null>(null);
 const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function save(){setBusy(true);setError(false);try{await workApi.update(apiUrl,tenderId,item,{workflow_status:state,note:note||null,owner:owner||null,actor_label:actor||null});await onSaved();}catch{if(mounted.current)setError(true);}finally{if(mounted.current)setBusy(false);}}
 async function inspect(){setBusy(true);setError(false);try{const result=await workApi.history(apiUrl,tenderId,item.id);if(mounted.current)setHistory(result);}catch{if(mounted.current)setError(true);}finally{if(mounted.current)setBusy(false);}}
 const states:Workflow[]=item.accepted_risk_allowed?["OPEN","IN_REVIEW","RESOLVED","ACCEPTED_RISK","NOT_APPLICABLE"]:["OPEN","IN_REVIEW","RESOLVED"];
 return <article><p>{item.dimension} · {item.issue?.severity??"Histórico"} · {item.code} · {item.lifecycle}</p><p>{item.entity_type}: {item.entity_id} · {item.issue?.summary}</p>
 {item.annotation_stale&&<p>La fuente cambió: la decisión anterior se conserva, pero el seguimiento actual vuelve a OPEN.</p>}
 {item.canonical_blocker_remains&&<p>El bloqueo canónico permanece aunque se cierre la actividad humana.</p>}
 <a href={`${apiUrl}${item.action_target}`} target="_blank" rel="noreferrer">Consultar contexto relacionado</a>
 <fieldset disabled={disabled||busy||item.lifecycle!=="ACTIVE"}><legend>Seguimiento humano {item.id}</legend>
 <label>Estado de actividad <select value={state} onChange={e=>setState(e.target.value as Workflow)}>{states.map(s=><option key={s}>{s}</option>)}</select></label>
 <label>Nota <textarea maxLength={4000} value={note} onChange={e=>setNote(e.target.value)}/></label>
 <label>Responsable declarado <input maxLength={200} value={owner} onChange={e=>setOwner(e.target.value)}/></label>
 <label>Actor declarado <input maxLength={200} value={actor} onChange={e=>setActor(e.target.value)}/></label>
 <button onClick={()=>void save()}>Guardar seguimiento</button></fieldset>
 {item.lifecycle!=="ACTIVE"&&<p>Nota histórica: {item.note??"Sin nota"}</p>}
 <button disabled={disabled||busy} onClick={()=>void inspect()}>Consultar decisiones {item.id}</button>
 {history?.map(event=><p key={event.revision}>Revisión {event.revision} · {event.workflow_status} · {event.timestamp} · {event.actor_label??"Sin actor declarado"} · {event.note}</p>)}
 {error&&<p role="alert">No se pudo guardar o consultar. Actualiza el contexto antes de repetir; una revisión anterior no sobrescribe otra nueva.</p>}
 </article>;
}
export function ReadinessWork({apiUrl,tenderId,disabled}:{apiUrl:string;tenderId:string;disabled:boolean}){
 const [data,setData]=useState<WorkRead|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false),[status,setStatus]=useState<Workflow|"">(""),[inactive,setInactive]=useState(false),[offset,setOffset]=useState(0);
 const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function read(page=offset){setBusy(true);setError(false);try{const next=await workApi.read(apiUrl,tenderId,{offset:page,workflow_status:status||undefined,include_inactive:inactive});if(mounted.current){setData(next);setOffset(page);}}catch{if(mounted.current){setError(true);setData(null);}}finally{if(mounted.current)setBusy(false);}}
 function invalidate(){setData(null);setOffset(0);}
 return <section aria-label="Seguimiento humano de readiness"><h4>Trabajo pendiente y decisiones humanas</h4><p>Actividad humana separada del estado fuente. RESOLVED o ACCEPTED_RISK no crean datos faltantes ni certifican cumplimiento. Actor y responsable no están autenticados.</p>
 <fieldset disabled={disabled||busy}><legend>Consultar trabajo</legend>
 <label>Filtrar actividad <select value={status} onChange={e=>{setStatus(e.target.value as Workflow|"");invalidate();}}><option value="">Todas</option>{["OPEN","IN_REVIEW","RESOLVED","ACCEPTED_RISK","NOT_APPLICABLE"].map(s=><option key={s}>{s}</option>)}</select></label>
 <label><input type="checkbox" checked={inactive} onChange={e=>{setInactive(e.target.checked);invalidate();}}/>Incluir resueltos por fuente y obsoletos</label>
 <button onClick={()=>void read(0)}>Consultar seguimiento de readiness</button></fieldset>
 {error&&<p role="alert">No se pudo consultar el seguimiento.</p>}
 {data&&<><p>{data.notice}</p><p>Estado fuente: {data.canonical_summary.status} · {data.canonical_summary.blocker_count} bloqueos/faltantes.</p><p>Actividad: {Object.entries(data.work_summary).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>
 {data.items.map(item=><WorkRow key={`${item.id}:${item.revision}:${item.context_sha256}`} item={item} apiUrl={apiUrl} tenderId={tenderId} disabled={disabled||busy} onSaved={()=>read()}/>)}
 <button disabled={disabled||busy||offset===0} onClick={()=>void read(Math.max(0,offset-50))}>Página anterior</button><button disabled={disabled||busy||offset+data.items.length>=data.total_filtered} onClick={()=>void read(offset+50)}>Página siguiente</button></>}
 </section>;
}
