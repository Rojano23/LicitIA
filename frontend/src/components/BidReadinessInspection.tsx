import {useEffect,useRef,useState} from "react";
import {bidReadinessApi,type BidReadiness} from "../api/bidReadiness";
export function BidReadinessInspection({apiUrl,tenderId,disabled}:{apiUrl:string;tenderId:string;disabled:boolean}) {
 const [data,setData]=useState<BidReadiness|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function read(){setBusy(true);setError(false);setData(null);try{const next=await bidReadinessApi.read(apiUrl,tenderId);if(mounted.current)setData(next);}catch{if(mounted.current)setError(true);}finally{if(mounted.current)setBusy(false);}}
 return <section aria-label="Inspección Bid Readiness"><h4>Preparación según registros rastreados</h4>
 <p>Consulta puntual: vuelve a consultar después de cambios en documentos, revisiones o decisiones comerciales.</p>
 <button disabled={disabled||busy} onClick={()=>void read()}>Consultar Bid Readiness</button>
 {error&&<p role="alert">No se pudo consultar readiness. No hay una evaluación vigente visible.</p>}
 {data&&<><p>{data.notice}</p><p role="status">{data.status} · {data.blocker_count} bloqueos/faltantes · {data.review_required_count} señales de revisión · {data.warning_count} advertencias · {data.total_issues} señales totales</p>
 <ul>{data.dimensions.map(d=><li key={d.dimension}>{d.dimension}: {d.status} · {d.issue_count} señales</li>)}</ul>
 {data.issues.map(i=><article key={i.id}><p>{i.dimension} · {i.severity} · {i.code}: {i.summary}</p><p>{i.entity_type}: {i.entity_id} · {i.source_module}</p>
 {i.reference&&<p>Documento {i.reference.document_id??"sin identificar"} · versión {i.reference.revision??"sin identificar"} · p. {i.reference.page??"sin identificar"} · {i.reference.locator}</p>}
 {i.reference?.excerpt&&<blockquote>{i.reference.excerpt}</blockquote>}
 </article>)}</>}
 </section>;
}
