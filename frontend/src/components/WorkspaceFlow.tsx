import { ReadinessBoard } from "./ReadinessBoard";
import { BidReadinessInspection } from "./BidReadinessInspection";
import { useCallback, useEffect, useRef, useState } from "react";
import { workspaceApi, recoveryApi, type RetryRead, type ProcessingStatus, type WorkspaceRead, type WorkspaceSource } from "../api/workspace";
import { CommercialMatrix } from "./CommercialMatrix";
import { CommercialLine } from "./CommercialLine";
import { ScopeReview } from "./ScopeReview";

type Props = { apiUrl: string; tenderId: string; documents: readonly { id: string; original_filename: string }[] };
const statuses: Record<ProcessingStatus, string> = {
  NOT_PROCESSED: "Sin procesar", PROCESSING: "Procesando documentos", COMPLETED: "Procesamiento completado",
  COMPLETED_REVIEW_REQUIRED: "Completado con revisión requerida", PARTIAL: "Resultado parcial: hay documentos sin texto suficiente o no compatibles",
  FAILED: "Falló el procesamiento; revisa los documentos antes de volver a intentar",
  INTERRUPTED: "Procesamiento interrumpido; los resultados pueden estar incompletos", STALE: "Los documentos cambiaron; vuelve a procesar",
};
const reviewLabels: Record<string, string> = {
  NOT_REQUIRED: "Sin revisión requerida", PENDING: "Requiere revisión", CONFIRMED: "Confirmado por una persona",
  CORRECTED: "Corregido por una persona", REJECTED: "Rechazado por una persona", STALE_REVIEW: "Revisión desactualizada", SOURCE_BLOCKED: "Fuente bloqueada",
};
function Source({ source, apiUrl, tenderId }: { source: WorkspaceSource; apiUrl: string; tenderId: string }) {
  return <details><summary>Fuente: {source.filename ?? "Documento desconocido"}, página {source.page ?? "sin identificar"}, versión {source.revision ?? "sin identificar"}</summary>
    {source.available ? <a href={`${apiUrl}/tenders/${tenderId}/documents/${source.document_id}/content#page=${source.page ?? 1}`} target="_blank" rel="noreferrer">Abrir documento fuente</a> : <p>Fuente no disponible</p>}
    <blockquote>{source.excerpt}</blockquote><p>{source.method} · {source.locator}</p>
  </details>;
}
export function WorkspaceFlow({ apiUrl, tenderId, documents }: Props) {
  const [data, setData] = useState<WorkspaceRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<RetryRead | null>(null);
  const [recoveryError, setRecoveryError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reviewRevision, setReviewRevision] = useState(0);
  const generation = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; generation.current++; }; }, []);
  const refresh = useCallback(async () => {
    const request = ++generation.current;
    try {
      const result = await workspaceApi.read(apiUrl, tenderId);
      if (mounted.current && generation.current === request) { setData(result); setError(null); }
    } catch {
      if (mounted.current && generation.current === request) setError("No se pudo consultar el procesamiento. Verifica que el backend esté disponible y actualiza.");
    }
  }, [apiUrl, tenderId]);
  const documentKey = documents.map(d => d.id).join(",");
  useEffect(() => { void refresh(); }, [refresh, documentKey]);
  useEffect(() => {
    if (data?.processing.status !== "PROCESSING") return;
    const timer = window.setInterval(() => { void refresh(); }, 2000);
    return () => window.clearInterval(timer);
  }, [data?.processing.status, refresh]);
  async function inspectRecovery() {
    setRecovery(null); setRecoveryError(false);
    try { const result = await recoveryApi.read(apiUrl, tenderId); if (mounted.current) setRecovery(result); }
    catch { if (mounted.current) setRecoveryError(true); }
  }
  async function retry() {
    if (!recovery?.eligible) return;
    setBusy(true); setError(null);
    try {
      const result = await recoveryApi.retry(apiUrl, tenderId, recovery.fingerprint);
      if (mounted.current) { generation.current++; setData(result); setReviewRevision(n => n + 1); setRecovery(null); }
    } catch {
      if (mounted.current) { await refresh(); setRecovery(null); setError("No se pudo reintentar de forma segura. Los datos pudieron cambiar; verifica la recuperación nuevamente. No se borró evidencia para habilitar el reintento."); }
    } finally { if (mounted.current) setBusy(false); }
  }
  async function process() {
    setBusy(true); setError(null);
    const request = ++generation.current;
    try {
      const result = await workspaceApi.process(apiUrl, tenderId);
      if (mounted.current && generation.current === request) { setData(result); setReviewRevision(n => n + 1); }
    } catch {
      if (mounted.current) {
        await refresh();
        setError("No se pudo completar el procesamiento. Puede haber otra ejecución activa, documentos dañados o servicios no disponibles. Consulta el estado y revisa antes de intentar de nuevo.");
      }
    } finally { if (mounted.current) setBusy(false); }
  }
  return <>
    <section aria-label="Procesamiento y resultados canónicos" style={{ marginTop: 16, border: "1px solid #d9e1ec", padding: 12 }}>
      <h3>Procesamiento del expediente</h3>
      <p>Limited UAT: requiere validación humana. Los resultados pueden estar incompletos; los documentos originales son la autoridad. La evidencia solicitada no es una lista contractual certificada.</p>
      <p>Se procesa evidencia disponible. OCR y análisis visual requieren sus acciones específicas cuando falta percepción; este paso no activa proveedores.</p>
      <button disabled={busy || data?.processing.status === "PROCESSING" || documents.length === 0} onClick={() => void process()}>Procesar documentos disponibles</button>{" "}
      <button disabled={busy} onClick={() => { void refresh(); setReviewRevision(n => n + 1); }}>Actualizar resultados</button>
      <div>
        <button disabled={busy || data?.processing.status === "PROCESSING"} onClick={() => void inspectRecovery()}>Verificar recuperación</button>{" "}
        {recovery && <>
          <p>{recovery.eligible ? "Reintento disponible: reutiliza evidencia compatible y conserva las revisiones. No ejecuta OCR ni análisis visual." : "Reintento no disponible: revisa originales, procedencia y estado con el administrador."}</p>
          {recovery.provider_degraded && <p>Hay resultados de percepción fallidos o no disponibles. Se conserva la evidencia determinista válida; el proveedor debe revisarse por separado.</p>}
          {recovery.reasons.length > 0 && <p>Diagnóstico: {recovery.reasons.join(", ")}</p>}
          <button disabled={busy || !recovery.eligible} onClick={() => void retry()}>Reintentar de forma segura</button>
        </>}
        {recoveryError && <p role="alert">No se pudo verificar la recuperación; confirma que el backend y el almacenamiento estén disponibles.</p>}
      </div>
      <p role="status">{busy ? "Procesando documentos" : data ? statuses[data.processing.status] : "Consultando estado"}</p>
      {data?.processing.provider_degraded && <p>Percepción parcial o no disponible: la evidencia determinista válida permanece disponible y requiere revisión humana.</p>}
      {error && <p role="alert">{error} Los resultados visibles pueden estar desactualizados.</p>}
      {data && <>
        <ReadinessBoard key={`work:${tenderId}:${reviewRevision}:${documentKey}`} apiUrl={apiUrl} tenderId={tenderId} disabled={busy || data.processing.status === "PROCESSING"}/>
        <BidReadinessInspection key={`readiness:${tenderId}:${reviewRevision}:${documentKey}`} apiUrl={apiUrl} tenderId={tenderId} disabled={busy || data.processing.status === "PROCESSING"}/>
        <CommercialMatrix key={tenderId} apiUrl={apiUrl} tenderId={tenderId} />
        <h4>Alcance y cantidades</h4>
        <p>Las cantidades son de solo lectura y conservan su estado automático. Confirmar el alcance no confirma sus cantidades. La corrección independiente de cantidades está pendiente (P1). Después de revisar el alcance, usa Actualizar resultados para consultar la decisión vigente.</p>
        {data.scopes.length === 0 && <p>Sin resultados de alcance. Esto no confirma ausencia de obligaciones.</p>}
        {data.scopes.map(scope => <article key={scope.scope_detail_id} aria-label={`Alcance ${scope.candidate_item_key ?? scope.scope_detail_id}`}>
          <h5>{scope.candidate_item_key ?? "Alcance sin número"}: {scope.description}</h5>
          <p>{scope.review?.current ? reviewLabels[scope.review.current.effective_status] : "Sin resolver: evidencia no disponible"}</p>
          <Source source={scope.source} apiUrl={apiUrl} tenderId={tenderId} />
          {scope.quantities.length === 0 && <p>Cantidad no disponible</p>}
          {scope.quantities.map(q => q.scope_detail_id !== scope.scope_detail_id || q.tender_id !== tenderId ?
            <p key={q.id} role="alert">Cantidad con asociación no válida; requiere revisión.</p> :
            <div key={q.id}><p>Cantidad: {q.quantity_raw} {q.unit_raw ?? "sin unidad"} · {q.relation ?? "relación sin determinar"} · {q.status === "UNRESOLVED" ? "Sin resolver" : q.status === "REVIEW_REQUIRED" ? "Requiere revisión" : "Sin revisión requerida"}</p>
              <Source source={q.source} apiUrl={apiUrl} tenderId={tenderId} /></div>)}
          <CommercialLine apiUrl={apiUrl} tenderId={tenderId} scopeDetailId={scope.scope_detail_id} documents={documents} />
        </article>)}
        <details><summary>Requisitos y evidencia solicitada</summary>
          <p>{data.requirements.scope_note}</p>
          {data.requirements.requirements.length === 0 && <p>Sin requisitos disponibles; no equivale a cumplimiento.</p>}
          {data.requirements.requirements.map(r => <article key={r.requirement_id}><p>{r.canonical_text}</p>
            <p>Revisión: {r.review_status} · {r.review_freshness} · Vigencia: {r.effective_status} · Interpretación: {r.interpretation_status}</p>
            {r.interpretation_reason && <p>{r.interpretation_reason}</p>}{r.system_warnings.map(w => <p key={w}>{w}</p>)}
            {r.primary_source && <><p>{r.primary_source.source_filename}, página {r.primary_source.source_page ?? "sin identificar"}</p><blockquote>{r.primary_source.source_excerpt}</blockquote>
              <a href={`${apiUrl}/tenders/${tenderId}/documents/${r.primary_source.source_document_id}/content#page=${r.primary_source.source_page ?? 1}`}>Consultar fuente del requisito</a></>}
          </article>)}
          <h4>Evidencia solicitada — requiere validación humana</h4><p>{data.semantics.scope_note}</p>
          {data.semantics.requirements.flatMap(r => r.expected_evidence.map(e => <article key={e.id}><p>{e.evidence_description} ({e.evidence_type})</p>
            <p>Requisito: {r.canonical_text} · Interpretación: {r.interpretation_status} · {r.evidence_mode}</p>
            <p>{e.source_filename ?? "Fuente no identificada"}, página {e.source_page ?? "sin identificar"}</p><blockquote>{e.source_excerpt}</blockquote>
            {e.source_document_id && <a href={`${apiUrl}/tenders/${tenderId}/documents/${e.source_document_id}/content#page=${e.source_page ?? 1}`}>Consultar fuente de evidencia solicitada</a>}</article>))}
          {!data.semantics.requirements.some(r => r.expected_evidence.length) && <p>Sin evidencia solicitada disponible.</p>}
        </details>
      </>}
    </section>
    <ScopeReview key={reviewRevision} apiUrl={apiUrl} tenderId={tenderId} documents={documents} />
  </>;
}
