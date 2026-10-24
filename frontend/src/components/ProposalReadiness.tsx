import {commercialLabel as label} from "../ui/commercialPresentation";
import {useEffect,useRef,useState} from "react";
import {proposalApi,type Evaluation,type Snapshot,type SnapshotHistory,type SnapshotRequest} from "../api/proposalReadiness";
export function ProposalReadiness({apiUrl,tenderId,disabled,product=false}:{apiUrl:string;tenderId:string;disabled:boolean;product?:boolean}){
 const [data,setData]=useState<Evaluation|null>(null),[history,setHistory]=useState<SnapshotHistory|null>(null),[created,setCreated]=useState<Snapshot|null>(null);
 const [ack,setAck]=useState(false),[actor,setActor]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const pending=useRef<SnapshotRequest|null>(null),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function inspect(before?:string){setBusy(true);setError(false);try{const result=await proposalApi.evaluate(apiUrl,tenderId);const prior=await proposalApi.history(apiUrl,tenderId,before);if(mounted.current){setData(result);setHistory(prior);setCreated(null);setAck(false);pending.current=null;}}catch{if(mounted.current){setError(true);setData(null);setHistory(null);}}finally{if(mounted.current)setBusy(false);}}
 async function create(){if(!data)return;setBusy(true);setError(false);try{
 const request=pending.current??{request_id:crypto.randomUUID(),expected_input_sha256:data.input_sha256,acknowledge_warnings:ack,actor_label:actor||null};pending.current=request;
 const snapshot=await proposalApi.create(apiUrl,tenderId,request);if(mounted.current){setCreated(snapshot);pending.current=null;setData(null);setHistory(null);}
 }catch{if(mounted.current)setError(true);}finally{if(mounted.current)setBusy(false);}}
 const allowed=data&&["ELIGIBLE","ELIGIBLE_WITH_WARNINGS"].includes(data.projection.eligibility);
 return <section aria-label="Preparación de captura para propuesta"><h5>Captura de preparación para propuesta</h5>
 <p>Esta captura conserva la información de preparación usada para la propuesta. No genera una propuesta ni certifica cumplimiento. La licitación sigue editable.</p>
 <button disabled={disabled||busy} onClick={()=>void inspect()}>Evaluar preparación e historial</button>
 {data&&<><p>Elegibilidad de propuesta: {product?label(data.projection.eligibility):data.projection.eligibility} · Estado fuente: {product?label(data.projection.readiness_status):data.projection.readiness_status}</p><p>{data.projection.notice}</p>
 <p>Se muestran hasta 50 señales; la lista de preparación permite consultar las demás por página.</p>
 <p>{data.projection.rows.length} filas elegibles; {data.projection.blockers.length} bloqueos/faltantes; {data.projection.reviews.length} revisiones; {data.projection.warnings.length} advertencias.</p>
 <details><summary>Detalle técnico de señales de la captura</summary>{[...data.projection.blockers,...data.projection.reviews,...data.projection.warnings].slice(0,50).map(i=><p key={i.id}>{i.dimension} · {i.code} · {i.entity_type}: {i.entity_id}</p>)}
 </details>{data.projection.accepted_risks.slice(0,50).map(r=><p key={r.issue_id}>Riesgo aceptado: {r.issue_id} · {r.note}</p>)}
 <fieldset disabled={disabled||busy||pending.current!==null}><legend>Confirmación de la captura</legend>
 <label>Responsable declarado de la captura <input maxLength={200} value={actor} onChange={e=>setActor(e.target.value)}/></label>
 <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>Confirmo las advertencias y riesgos visibles para preparar esta propuesta</label></fieldset>
 <button disabled={disabled||busy||!allowed||data.projection.warnings.length>0&&!ack} onClick={()=>void create()}>Guardar captura de preparación</button>
 {!allowed&&<p>Completa los datos o revisiones del expediente antes de guardar la captura de preparación. Las cantidades permanecen de sólo lectura.</p>}
 </>}
 {created&&!product&&<p>Snapshot creado: {created.payload.snapshot_id} · SHA-256: {created.payload_sha256}. Consulta el historial para verificar CURRENT/STALE.</p>}{created&&product&&<><p>Captura creada. Consulta el historial para comprobar si hay cambios posteriores.</p><details><summary>Integridad de captura</summary><p>{created.payload.snapshot_id} · SHA-256: {created.payload_sha256}</p></details></>}
 {history&&<><h5>Historial de capturas (20 por página)</h5>{history.items.map(s=><p key={s.snapshot_id}>{s.created_at} · {product?label(s.eligibility):s.eligibility} · {product?label(s.state):s.state} · <a href={`${apiUrl}/tenders/${tenderId}/proposal-readiness/snapshots/${s.snapshot_id}/handoff`} target="_blank" rel="noreferrer">{product?"Ver datos técnicos de la captura":`Handoff ${s.snapshot_id}`}</a></p>)}
 {history.next_before_id&&<button disabled={disabled||busy} onClick={()=>void inspect(history.next_before_id??undefined)}>Más capturas anteriores</button>}</>}
 {error&&<p role="alert">No se pudo consultar la preparación o guardar la captura. Reintentar creación conserva la misma solicitud; si el contexto cambió, vuelve a evaluar antes de confirmar.</p>}
 </section>;
}
