import { useEffect, useRef, useState } from "react";
import { auditApi, type CommercialAudit } from "../api/commercialReadiness";
export function CommercialAuditDetails({apiUrl,tenderId,scopeId,disabled}: {apiUrl: string;tenderId: string;scopeId: string;disabled: boolean}) {
  const [history,setHistory]=useState<CommercialAudit | null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(false);
  const mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  async function read(before?: number) {
    setBusy(true);setError(false);
    try {const next=await auditApi.read(apiUrl,tenderId,scopeId,before);if(mounted.current) setHistory(prior=>before && prior ? {...next,events:[...prior.events,...next.events]}:next);}
    catch {if(mounted.current) setError(true);}
    finally {if(mounted.current) setBusy(false);}
  }
  return <div><button disabled={disabled || busy} onClick={()=>void read()}>Consultar historial comercial {scopeId}</button>
    {error && <p role="alert">No se pudo consultar la auditoría comercial.</p>}
    {history && <details open><summary>Historial comercial · revisión {history.current_revision}</summary>
      <p>Precio actual {history.current_manual_price ? "manual protegido":"calculado o sin definir"}. Actor declarado cuando existe; sin autenticación.</p>
      {history.events.map(event=><div key={event.revision}><p>Revisión {event.revision} · {event.origin} · {event.timestamp} · {event.actor_label ?? "Sin actor declarado"}</p>
        <p>{event.manual_price ? "Decisión manual":"Cálculo/edición"}: precio {event.offered_unit_price ?? "Sin definir"} · recomendación histórica {event.recommended_unit_price ?? "Sin resolver"} · {event.note ?? "Sin nota"}</p>
        {event.import_evidence?.sha256 && <p>Import SHA-256: {event.import_evidence.sha256}</p>}
        {event.changes.map(change=><p key={change.field}>{change.field}: {change.previous ?? "Sin definir"} → {change.current ?? "Sin definir"}</p>)}</div>)}
      {history.next_before_revision && <button disabled={disabled || busy} onClick={()=>void read(history.next_before_revision ?? undefined)}>Ver revisiones anteriores</button>}
    </details>}
  </div>;
}
