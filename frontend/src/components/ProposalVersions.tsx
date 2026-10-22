import {useEffect,useRef,useState} from "react";
import {versionsApi,type ProposalVersion,type ProposalConfig,type VersionPage,type CreateVersion,type ProposalEvent} from "../api/proposalVersions";
export function ProposalVersions({apiUrl,tenderId,disabled}:{apiUrl:string;tenderId:string;disabled:boolean}){
 const [page,setPage]=useState<VersionPage|null>(null),[selected,setSelected]=useState<ProposalVersion|null>(null),[config,setConfig]=useState<ProposalConfig|null>(null);
 const [snapshot,setSnapshot]=useState(""),[actor,setActor]=useState(""),[warnings,setWarnings]=useState(false),[stale,setStale]=useState(false),[confirmFreeze,setConfirmFreeze]=useState(false);
 const [source,setSource]=useState<string|null>(null),[history,setHistory]=useState<ProposalEvent[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const pending=useRef<CreateVersion|null>(null),mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function run(work:()=>Promise<void>){setBusy(true);setError(false);try{await work();}catch{if(mounted.current)setError(true);}finally{if(mounted.current)setBusy(false);}}
 function adopt(value:ProposalVersion){if(!mounted.current)return;setSelected(value);setConfig(value.configuration);setSource(null);setHistory([]);setConfirmFreeze(false);}
 async function list(before?:string){await run(async()=>{const value=await versionsApi.list(apiUrl,tenderId,before);if(mounted.current)setPage(value);});}
 async function inspect(id:string){await run(async()=>{const value=await versionsApi.get(apiUrl,tenderId,id);adopt(value);});}
 async function create(revision:boolean){if(revision&&!selected)return;await run(async()=>{
 const payload=pending.current??{request_id:crypto.randomUUID(),snapshot_id:snapshot,...(revision&&selected?{proposal_id:selected.proposal_id,previous_version_id:selected.id}:{}),acknowledge_warnings:warnings,acknowledge_stale:stale,actor_label:actor||null,origin:"WORKSPACE" as const};pending.current=payload;
 const value=await versionsApi.create(apiUrl,tenderId,payload);pending.current=null;adopt(value);const result=await versionsApi.list(apiUrl,tenderId);if(mounted.current)setPage(result);
 });}
 const editable=selected?.state==="DRAFT"&&selected.is_latest;
 const dirty=!!selected&&!!config&&JSON.stringify(config)!==JSON.stringify(selected.configuration);
 return <section aria-label="Versiones de propuesta"><h4>Propuesta: dominio y versiones</h4><p>Snapshot explícito, configuración humana y versiones. No genera documentos ni reinterpreta evidencia.</p>
 <button disabled={disabled||busy} onClick={()=>void list()}>Consultar versiones de propuesta</button>
 <fieldset disabled={disabled||busy||pending.current!==null}><legend>Crear desde snapshot preparado</legend>
 <label>Snapshot ID para propuesta <input value={snapshot} onChange={e=>setSnapshot(e.target.value)} maxLength={36}/></label>
 <label>Actor declarado de propuesta <input value={actor} onChange={e=>setActor(e.target.value)} maxLength={200}/></label>
 <label><input type="checkbox" checked={warnings} onChange={e=>setWarnings(e.target.checked)}/>Confirmo las advertencias del snapshot elegido</label>
 <label><input type="checkbox" checked={stale} onChange={e=>setStale(e.target.checked)}/>Acepto usar el snapshot histórico si está STALE</label></fieldset>
 <button disabled={disabled||busy||!snapshot} onClick={()=>void create(false)}>Crear propuesta nueva desde snapshot</button>
 <button disabled={disabled||busy||!snapshot||!selected?.is_latest} onClick={()=>void create(true)}>Crear revisión desde versión seleccionada</button>
 {pending.current&&<button disabled={busy||disabled} onClick={()=>{pending.current=null;setError(false);}}>Iniciar otra solicitud explícita</button>}
 {page&&<><ul>{page.items.map(v=><li key={v.id}>Versión {v.version} · {v.state} · Snapshot {v.snapshot_id} · {v.is_latest?"Más reciente":"Histórica"} <button disabled={disabled||busy} onClick={()=>void inspect(v.id)}>Abrir versión {v.id}</button></li>)}</ul>{page.next_before_id&&<button disabled={disabled||busy} onClick={()=>void list(page.next_before_id??undefined)}>Más versiones anteriores</button>}</>}
 {selected&&config&&<><p>Versión seleccionada: {selected.version} · {selected.state} · Elegibilidad almacenada: {selected.snapshot_eligibility} · Snapshot fijo: {selected.snapshot_id}</p>
 <p>{source??"Freshness no consultada"} · SHA frozen: {selected.frozen_sha256??"Sin congelar"}</p>
 <button disabled={disabled||busy} onClick={()=>void run(async()=>{const value=await versionsApi.source(apiUrl,tenderId,selected.id);if(mounted.current)setSource(value.state);})}>Verificar CURRENT/STALE de fuente</button>
 <fieldset disabled={disabled||busy||!editable}><legend>Configuración de borrador</legend>
 <label>Título de propuesta <input maxLength={300} value={config.title??""} onChange={e=>setConfig({...config,title:e.target.value||null})}/></label>
 <label>Nombre de participante <input maxLength={300} value={config.bidder_name??""} onChange={e=>setConfig({...config,bidder_name:e.target.value||null})}/></label>
 <label>Referencia del participante <input maxLength={200} value={config.bidder_reference??""} onChange={e=>setConfig({...config,bidder_reference:e.target.value||null})}/></label>
 <label>Presentación de monedas <select value={config.currency_presentation} onChange={e=>setConfig({...config,currency_presentation:e.target.value as ProposalConfig["currency_presentation"]})}><option>BY_CURRENCY</option><option>ORIGINAL</option></select></label>
 <label>Notas de propuesta <textarea maxLength={4000} value={config.notes??""} onChange={e=>setConfig({...config,notes:e.target.value||null})}/></label>
 <p>Secciones genéricas: {selected.sections.map(s=>s.type).join(" · ")}. Inclusión/orden configurables por API; composición en M9-B.</p>
 <button onClick={()=>void run(async()=>adopt(await versionsApi.update(apiUrl,tenderId,selected,config,actor||null)))}>Guardar configuración de propuesta</button></fieldset>
 <label><input type="checkbox" disabled={disabled||busy||!editable} checked={confirmFreeze} onChange={e=>setConfirmFreeze(e.target.checked)}/>Confirmo congelar esta configuración; después requerirá una nueva revisión</label>
 {dirty&&<p>Guarda la configuración antes de congelar esta versión.</p>}
 <button disabled={disabled||busy||!editable||!confirmFreeze||dirty} onClick={()=>void run(async()=>adopt(await versionsApi.freeze(apiUrl,tenderId,selected,warnings,stale,actor||null)))}>Congelar versión de propuesta</button>
 <button disabled={disabled||busy} onClick={()=>void run(async()=>{const events=await versionsApi.history(apiUrl,tenderId,selected.id);if(mounted.current)setHistory(events);})}>Consultar auditoría de propuesta</button>
 {history.map(e=><p key={e.sequence}>{e.sequence} · {e.action} · {e.created_at} · {e.actor_label??"Actor no declarado"}</p>)}
 <a href={`${apiUrl}/tenders/${tenderId}/proposal-versions/${selected.id}/inputs`} target="_blank" rel="noreferrer">Consultar input canónico de esta versión</a></>}
 {error&&<p role="alert">No se pudo completar la acción. Revisa snapshot, confirmaciones y revisión vigente. Retry de creación conserva la solicitud; el binding no cambia automáticamente.</p>}
 </section>;
}
