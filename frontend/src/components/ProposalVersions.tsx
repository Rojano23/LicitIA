import {commercialLabel as label} from "../ui/commercialPresentation";
import {proposalApi,type SnapshotHistory} from "../api/proposalReadiness";
import {ProposalExports} from "./ProposalExports";
import {ProposalComposition} from "./ProposalComposition";
import type {Composition} from "../api/proposalComposition";
import {useEffect,useRef,useState} from "react";
import {versionsApi,type ProposalVersion,type ProposalConfig,type VersionPage,type CreateVersion,type ProposalEvent} from "../api/proposalVersions";
export function ProposalVersions({apiUrl,tenderId,disabled,product=false}:{apiUrl:string;tenderId:string;disabled:boolean;product?:boolean}){
 const [snapshots,setSnapshots]=useState<SnapshotHistory|null>(null);
 const [page,setPage]=useState<VersionPage|null>(null),[selected,setSelected]=useState<ProposalVersion|null>(null),[config,setConfig]=useState<ProposalConfig|null>(null);
 const [snapshot,setSnapshot]=useState(""),[actor,setActor]=useState(""),[warnings,setWarnings]=useState(false),[stale,setStale]=useState(false),[confirmFreeze,setConfirmFreeze]=useState(false);
 const [source,setSource]=useState<string|null>(null),[history,setHistory]=useState<ProposalEvent[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const [composition,setComposition]=useState<Composition|null>(null),[compositionAck,setCompositionAck]=useState(false);
 const selectionGeneration=useRef(0);
 const pending=useRef<CreateVersion|null>(null),mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function run(work:()=>Promise<void>){setBusy(true);setError(false);try{await work();}catch{if(mounted.current)setError(true);}finally{if(mounted.current)setBusy(false);}}
 function adopt(value:ProposalVersion){if(!mounted.current)return;setSelected(value);setConfig(value.configuration);setSource(null);setHistory([]);setConfirmFreeze(false);setComposition(null);setCompositionAck(false);}
 async function list(before?:string){await run(async()=>{const value=await versionsApi.list(apiUrl,tenderId,before);if(mounted.current)setPage(value);});}
 async function inspect(id:string){const generation=++selectionGeneration.current;await run(async()=>{const value=await versionsApi.get(apiUrl,tenderId,id);if(value.id!==id||value.tender_id!==tenderId)throw new Error("VERSION_CONTEXT_MISMATCH");if(generation===selectionGeneration.current)adopt(value);});}
 async function create(revision:boolean){if(revision&&!selected)return;await run(async()=>{
 const payload=pending.current??{request_id:crypto.randomUUID(),snapshot_id:snapshot,...(revision&&selected?{proposal_id:selected.proposal_id,previous_version_id:selected.id}:{}),acknowledge_warnings:warnings,acknowledge_stale:stale,actor_label:actor||null,origin:"WORKSPACE" as const};pending.current=payload;
 const value=await versionsApi.create(apiUrl,tenderId,payload);pending.current=null;adopt(value);const result=await versionsApi.list(apiUrl,tenderId);if(mounted.current)setPage(result);
 });}
 const editable=selected?.state==="DRAFT"&&selected.is_latest;
 const dirty=!!selected&&!!config&&JSON.stringify(config)!==JSON.stringify(selected.configuration);
 return <section aria-label="Versiones de propuesta"><h2>{product?"Propuesta":"Propuesta: dominio y versiones"}</h2><p>Versiones ligadas a una captura de preparación. La composición y la generación requieren acciones explícitas.</p>
 <button disabled={disabled||busy} onClick={()=>void list()}>Consultar versiones de propuesta</button>
 <details open={!page?.items.length}><summary>Crear borrador o revisión desde una captura preparada</summary><fieldset disabled={disabled||busy||pending.current!==null}><legend>Crear desde una captura de preparación</legend>
 {product?<><button onClick={()=>void run(async()=>{const value=await proposalApi.history(apiUrl,tenderId);if(mounted.current)setSnapshots(value);})}>Consultar capturas preparadas</button><label>Captura de preparación <select value={snapshot} onChange={e=>setSnapshot(e.target.value)}><option value="">Elegir captura explícitamente</option>{snapshots?.items.map(item=><option key={item.snapshot_id} value={item.snapshot_id}>{item.created_at} · {label(item.eligibility)} · {label(item.state)}</option>)}</select></label>{snapshots?.next_before_id&&<button onClick={()=>void run(async()=>{const value=await proposalApi.history(apiUrl,tenderId,snapshots.next_before_id??undefined);if(mounted.current)setSnapshots(current=>({items:[...(current?.items??[]),...value.items],next_before_id:value.next_before_id}));})}>Más capturas anteriores</button>}<a href={`#/licitaciones/${encodeURIComponent(tenderId)}/preparacion`}>Revisar preparación actual o capturar estado</a></>:<label>Snapshot ID para propuesta <input value={snapshot} onChange={e=>setSnapshot(e.target.value)} maxLength={36}/></label>}
 <label>Responsable declarado de propuesta <input value={actor} onChange={e=>setActor(e.target.value)} maxLength={200}/></label>
 <label><input type="checkbox" checked={warnings} onChange={e=>setWarnings(e.target.checked)}/>Confirmo las advertencias de la captura elegida</label>
 <label><input type="checkbox" checked={stale} onChange={e=>setStale(e.target.checked)}/>Acepto usar la captura histórica si hay cambios posteriores</label></fieldset>
 <button disabled={disabled||busy||!snapshot} onClick={()=>void create(false)}>{product?"Crear borrador":"Crear propuesta nueva desde snapshot"}</button>
 <button disabled={disabled||busy||!snapshot||!selected?.is_latest} onClick={()=>void create(true)}>Crear revisión desde versión seleccionada</button>
 {pending.current&&<button disabled={busy||disabled} onClick={()=>{pending.current=null;setError(false);}}>Iniciar otra solicitud explícita</button>}
 </details>
 {product&&page&&!page.items.length&&<p>Aún no hay una propuesta.</p>}
 {page&&<><table><caption>Versiones de propuesta</caption><thead><tr><th>Versión</th><th>Estado</th><th>Historia</th><th>Acción</th></tr></thead><tbody>{page.items.map(v=><tr key={v.id}><td>{v.version}</td><td>{product?label(v.state):v.state}</td><td>{v.is_latest?"Más reciente":"Histórica"}<details><summary>Identificación técnica de captura vinculada</summary>{v.snapshot_id}</details></td><td><button disabled={disabled||busy} onClick={()=>void inspect(v.id)}>Abrir versión {product?v.version:v.id}</button></td></tr>)}</tbody></table>{page.next_before_id&&<button disabled={disabled||busy} onClick={()=>void list(page.next_before_id??undefined)}>Más versiones anteriores</button>}</>}
 {selected&&config&&<><p>Versión seleccionada: {selected.version} · {product?label(selected.state):selected.state} · Elegibilidad almacenada: {product?label(selected.snapshot_eligibility):selected.snapshot_eligibility} · {product?"Captura fija de preparación":`Snapshot fijo: ${selected.snapshot_id}`}</p>
 <p>{source?(product?label(source):source):"Cambios posteriores aún no consultados"}</p>{product&&selected.state==="FROZEN"&&<p>Versión congelada e inmutable. Los cambios requieren una nueva revisión; esta versión conserva su contenido histórico.</p>}<details><summary>Vínculo e integridad de esta versión</summary><p>Captura: {selected.snapshot_id} · SHA congelada: {selected.frozen_sha256??"Sin congelar"}</p></details>
 <button disabled={disabled||busy} onClick={()=>void run(async()=>{const value=await versionsApi.source(apiUrl,tenderId,selected.id);if(mounted.current)setSource(value.state);})}>{product?"Consultar cambios posteriores":"Verificar CURRENT/STALE de fuente"}</button>
 <fieldset disabled={disabled||busy||!editable}><legend>Configuración de borrador</legend>
 <label>Título de propuesta <input maxLength={300} value={config.title??""} onChange={e=>setConfig({...config,title:e.target.value||null})}/></label>
 <label>Nombre de participante <input maxLength={300} value={config.bidder_name??""} onChange={e=>setConfig({...config,bidder_name:e.target.value||null})}/></label>
 <label>Referencia del participante <input maxLength={200} value={config.bidder_reference??""} onChange={e=>setConfig({...config,bidder_reference:e.target.value||null})}/></label>
 <label>Presentación de monedas <select value={config.currency_presentation} onChange={e=>setConfig({...config,currency_presentation:e.target.value as ProposalConfig["currency_presentation"]})}><option value="BY_CURRENCY">{product?"Agrupar por moneda":"BY_CURRENCY"}</option><option value="ORIGINAL">{product?"Monedas originales":"ORIGINAL"}</option></select></label>
 <label>Notas de propuesta <textarea maxLength={4000} value={config.notes??""} onChange={e=>setConfig({...config,notes:e.target.value||null})}/></label>
 <p>Secciones genéricas: {selected.sections.map(s=>product?label(s.type):s.type).join(" · ")}. Disposición y respuestas disponibles en el compositor.</p>
 <button onClick={()=>void run(async()=>adopt(await versionsApi.update(apiUrl,tenderId,selected,config,actor||null)))}>Guardar configuración de propuesta</button></fieldset>
 <ProposalComposition key={selected.id} apiUrl={apiUrl} tenderId={tenderId} versionId={selected.id} product={product} editable={!!editable} disabled={disabled||busy} onState={setComposition}/>
 <label><input type="checkbox" disabled={disabled||busy||!editable} checked={compositionAck} onChange={e=>setCompositionAck(e.target.checked)}/>Acepto las revisiones intencionales de composición</label>
 <label><input type="checkbox" disabled={disabled||busy||!editable} checked={confirmFreeze} onChange={e=>setConfirmFreeze(e.target.checked)}/>Confirmo congelar esta versión y toda su composición; después requerirá una nueva revisión</label>
 {dirty&&<p>Guarda la configuración antes de congelar esta versión.</p>}
 <button disabled={disabled||busy||!editable||!confirmFreeze||dirty||!composition?.initialized||!!composition.summary?.hard_incomplete.length||!!composition.summary?.blocking_review.length||!!(composition.summary?.acknowledgeable_review.length&&!compositionAck)} onClick={()=>void run(async()=>adopt(await versionsApi.freeze(apiUrl,tenderId,selected,warnings,stale,actor||null,composition?.revision,compositionAck)))}>Congelar versión de propuesta</button>
 <ProposalExports key={`exports:${selected.id}`} apiUrl={apiUrl} tenderId={tenderId} version={selected} product={product} compositionRevision={composition?.revision??null} disabled={disabled||busy||dirty||!composition?.initialized}/>
 <button disabled={disabled||busy} onClick={()=>void run(async()=>{const events=await versionsApi.history(apiUrl,tenderId,selected.id);if(mounted.current)setHistory(events);})}>Consultar auditoría de propuesta</button>
 {history.map(e=><p key={e.sequence}>{e.sequence} · {product?label(e.action):e.action} · {e.created_at} · {e.actor_label??"Actor no declarado"}</p>)}
 <a href={`${apiUrl}/tenders/${tenderId}/proposal-versions/${selected.id}/inputs`} target="_blank" rel="noreferrer">Ver datos técnicos de esta versión</a></>}
 {error&&<p role="alert">No se pudo completar la acción. Revisa la captura elegida, las confirmaciones y la versión actual. Al reintentar la creación se conserva la misma solicitud y la captura elegida.</p>}
 </section>;
}
