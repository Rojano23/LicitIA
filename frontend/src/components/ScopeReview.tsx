import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  scopeReviewApi, scopeReviewError,
  type EffectiveReviewStatus, type ReviewDecision, type ScopeMachineEvidence,
  type ScopeReviewDecisionRequest, type ScopeReviewHistoryEntry, type ScopeReviewItem,
} from "../api/scopeReview";
import "./ScopeReview.css";

type Props = {
  apiUrl: string;
  tenderId: string;
  documents: readonly { id: string; original_filename: string }[];
};
type QueueFilter = "Todos" | "Pendientes" | "Revisados" | "Bloqueados";

const effectiveLabels: Record<EffectiveReviewStatus, string> = {
  NOT_REQUIRED: "Sin revisión requerida", PENDING: "Requiere revisión",
  CONFIRMED: "Confirmado", CORRECTED: "Corregido", REJECTED: "Rechazado",
  STALE_REVIEW: "Revisión anterior desactualizada", SOURCE_BLOCKED: "Fuente bloqueada",
};
const humanLabels = {
  NO_REVIEW: "Sin revisión humana", CURRENT: "Revisión humana vigente", STALE: "Revisión humana desactualizada",
};
const sourceLabels: Record<string, string> = {
  ACTIVE: "Vigente", ACTIVE_WITH_EFFECTS: "Vigente con efectos documentales",
  EFFECTIVE: "Efectiva", EFFECTIVE_WITH_OVERLAY: "Efectiva con aclaraciones o modificaciones",
  SUPERSEDED: "Sustituida", REVOKED: "Revocada", UNRESOLVED_SOURCE: "Fuente sin resolver",
  REVIEW_REQUIRED: "Requiere revisión", UNCHANGED: "Sin cambios de ubicación",
  MODIFIED: "Ubicación modificada", CORRECTED: "Ubicación corregida", CLARIFIED: "Ubicación aclarada",
  SUPPLEMENTED: "Ubicación complementada",
};
const diagnosticLabels: Record<string, string> = {
  FACT_REVIEW_REQUIRED: "LicitIA marcó este hallazgo para revisión humana.",
  SOURCE_DOCUMENT_MISSING: "No se encuentra el documento fuente.",
  SOURCE_DOCUMENT_REVIEW_REQUIRED: "La vigencia del documento fuente requiere revisión.",
  SOURCE_LOCATOR_REVIEW_REQUIRED: "Los efectos sobre esta ubicación documental requieren revisión.",
  SOURCE_LOCATOR_UNRESOLVED: "No se pudo resolver la ubicación afectada en la fuente.",
  SOURCE_LOCATOR_ABSENT_PARTIAL_NOT_APPLIED: "Falta una ubicación documental para aplicar el efecto parcial.",
};
const blockLabels: Record<string, string> = {
  TARGET_REMOVED: "Este registro fue regenerado o retirado. Su revisión permanece como historial y no se aplica automáticamente a registros nuevos.",
  SOURCE_SUPERSEDED: "La fuente fue sustituida. Una revisión de alcance no puede volverla vigente.",
  SOURCE_REVOKED: "La fuente fue revocada. Una revisión de alcance no puede volverla vigente.",
  SOURCE_UNRESOLVED_SOURCE: "La fuente no está resuelta. Primero debe aclararse su estado documental.",
  SOURCE_REVIEW_REQUIRED: "Hay ambigüedad en la fuente o su versión. Primero debe resolverse la revisión documental; confirmar el alcance no resuelve esa ambigüedad.",
};
const historyLabels: Record<ScopeReviewHistoryEntry["reason"], string> = {
  CURRENT: "Revisión actual", HISTORICAL_REVISION: "Decisión anterior",
  TARGET_CHANGED: "Desactualizada: cambió la evidencia o la fuente",
  TARGET_REMOVED: "Histórica: registro regenerado o retirado",
};
const conflictMessages: Record<string, string> = {
  SCOPE_REVIEW_TARGET_STALE: "La información de este alcance cambió desde que la abriste. LicitIA actualizará la información antes de que tomes una decisión.",
  SCOPE_REVIEW_REVISION_CONFLICT: "Este alcance fue revisado mientras lo tenías abierto. Se actualizará la revisión más reciente.",
  SCOPE_SOURCE_NOT_REVIEWABLE: "La fuente ya no permite revisar este alcance. Se actualizará la información para mostrar el motivo.",
};

function machineForDisplay(item: ScopeReviewItem): ScopeMachineEvidence | undefined {
  // An archived snapshot is labelled as historical, never treated as current facts.
  return item.current?.machine ?? item.history[item.history.length - 1]?.review.machine_snapshot;
}
function itemLabel(item: ScopeReviewItem): string {
  return item.current ? effectiveLabels[item.current.effective_status] : "Registro histórico";
}
function blockReason(item: ScopeReviewItem): string {
  return blockLabels[item.not_reviewable_reason ?? ""] ?? "La fuente no permite revisión de alcance. Debe revisarse su estado documental antes de tomar una decisión.";
}
function readError(error: unknown): string {
  return scopeReviewError(error).status === 404
    ? "La licitación o el elemento de alcance ya no está disponible. Actualiza la lista o selecciona otra licitación."
    : "No se pudo cargar la revisión de alcance. Verifica la conexión con el servidor local e inténtalo de nuevo.";
}

export function ScopeReview(props: Props) {
  const [open, setOpen] = useState(false);
  return (
    <section className="scope-review" aria-labelledby="scope-review-title">
      <div className="scope-review-heading">
        <div>
          <h3 id="scope-review-title">Revisión de alcance</h3>
          <p>Revisa los hallazgos de ejecución, sus fuentes y las decisiones humanas.</p>
        </div>
        <button type="button" aria-expanded={open} aria-controls="scope-review-content" onClick={() => setOpen(!open)}>
          {open ? "Cerrar revisión de alcance" : "Abrir revisión de alcance"}
        </button>
      </div>
      <div id="scope-review-content" hidden={!open}>
        {open && <ScopeReviewPanel key={`${props.apiUrl}:${props.tenderId}`} {...props} />}
      </div>
    </section>
  );
}

function ScopeReviewPanel({ apiUrl, tenderId, documents }: Props) {
  const api = useMemo(() => scopeReviewApi(apiUrl, tenderId), [apiUrl, tenderId]);
  const [items, setItems] = useState<ScopeReviewItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<ScopeReviewItem | null>(null);
  const [filter, setFilter] = useState<QueueFilter>("Todos");
  const [queueLoading, setQueueLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const [description, setDescription] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const alive = useRef(false);
  const queueRequest = useRef(0);
  const detailRequest = useRef(0);

  const loadQueue = useCallback(async () => {
    const request = ++queueRequest.current;
    setQueueLoading(true);
    setQueueError(null);
    try {
      const result = await api.list();
      if (!alive.current || request !== queueRequest.current) return;
      setItems(result);
      setSelectedId((previous) => result.some((item) => item.scope_detail_id === previous)
        ? previous : result[0]?.scope_detail_id ?? "");
    } catch (error: unknown) {
      if (alive.current && request === queueRequest.current) setQueueError(readError(error));
    } finally {
      if (alive.current && request === queueRequest.current) setQueueLoading(false);
    }
  }, [api]);

  const loadDetail = useCallback(async (id: string) => {
    const request = ++detailRequest.current;
    setDetail(null);
    setDetailLoading(true);
    setDetailError(null);
    setDecision(null);
    setDescription("");
    setNote("");
    try {
      const result = await api.detail(id);
      if (alive.current && request === detailRequest.current) setDetail(result);
    } catch (error: unknown) {
      if (alive.current && request === detailRequest.current) setDetailError(readError(error));
    } finally {
      if (alive.current && request === detailRequest.current) setDetailLoading(false);
    }
  }, [api]);

  useEffect(() => {
    alive.current = true;
    void loadQueue();
    return () => {
      alive.current = false;
      queueRequest.current += 1;
      detailRequest.current += 1;
    };
  }, [loadQueue]);

  useEffect(() => {
    setFeedback(null);
    setDecisionError(null);
    if (selectedId) void loadDetail(selectedId);
    else {
      detailRequest.current += 1;
      setDetail(null);
      setDecision(null);
    }
  }, [selectedId, loadDetail]);

  async function refresh() {
    await Promise.all([loadQueue(), selectedId ? loadDetail(selectedId) : Promise.resolve()]);
  }

  function beginDecision(value: ReviewDecision) {
    setDecision(value);
    setDescription(detail?.current?.effective_description ?? "");
    setNote("");
    setFeedback(null);
    setDecisionError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current || !detail?.reviewable || !detail.current || !detail.projection_fingerprint
      || detail.scope_detail_id !== selectedId || !decision || queueLoading || detailLoading || queueError || detailError) return;
    if (decision === "CORRECTED" && !description.trim()) {
      setDecisionError("Escribe una descripción para guardar la corrección.");
      return;
    }
    const expectations = {
      expected_projection_fingerprint: detail.projection_fingerprint,
      expected_current_review_revision: detail.current_review_revision,
      note: note.trim() || null,
    };
    const payload: ScopeReviewDecisionRequest = decision === "CORRECTED"
      ? { ...expectations, decision, correction: { description: description.trim() } }
      : { ...expectations, decision };
    submittingRef.current = true;
    setSubmitting(true);
    setDecisionError(null);
    try {
      const result = await api.decide(detail.scope_detail_id, payload);
      if (!alive.current) return;
      setDetail(result);
      // Preserve queue order and consume only the recalculated backend response.
      setItems((previous) => previous.map((item) => item.scope_detail_id === result.scope_detail_id ? result : item));
      setDecision(null);
      setNote("");
      setDescription("");
      setFeedback("Decisión guardada. El estado mostrado fue recalculado por LicitIA.");
    } catch (error: unknown) {
      if (!alive.current) return;
      const failure = scopeReviewError(error);
      if (failure.status === 409) {
        setDecisionError(conflictMessages[failure.code ?? ""] ?? "La información cambió. Se actualizará antes de que tomes una nueva decisión.");
        await refresh();
      } else {
        setDecisionError(failure.status === 404 ? readError(error)
          : "No se pudo confirmar el guardado de la decisión. Se actualizará la información; revisa el historial antes de volver a decidir.");
        setDecision(null);
        await refresh();
      }
    } finally {
      submittingRef.current = false;
      if (alive.current) setSubmitting(false);
    }
  }

  const filteredItems = items.filter((item) => {
    if (filter === "Pendientes") return item.current?.effective_status === "PENDING" || item.current?.effective_status === "STALE_REVIEW";
    if (filter === "Revisados") return item.current?.human_review_status === "CURRENT";
    if (filter === "Bloqueados") return !item.reviewable;
    return true;
  });
  const machine = detail ? machineForDisplay(detail) : undefined;
  const disabled = submitting || queueLoading || detailLoading || !!queueError || !!detailError;

  return (
    <>
      {feedback && <p role="status" className="scope-review-success">{feedback}</p>}
      {decisionError && <div role="alert" className="scope-review-warning"><p>{decisionError}</p>
        <button type="button" disabled={disabled} onClick={() => void refresh()}>Actualizar información</button>
      </div>}
      <div className="scope-review-layout">
        <aside aria-label="Cola de revisión de alcance">
          <div className="scope-review-heading"><h4>Elementos de alcance</h4>
            <button type="button" disabled={submitting || queueLoading} onClick={() => void refresh()}>Actualizar</button>
          </div>
          <div className="scope-review-filters" aria-label="Filtrar alcance">
            {(["Todos", "Pendientes", "Revisados", "Bloqueados"] as const).map((value) => (
              <button type="button" key={value} aria-pressed={filter === value} disabled={submitting} onClick={() => setFilter(value)}>{value}</button>
            ))}
          </div>
          {queueLoading && <p role="status">Analizando alcance...</p>}
          {queueError && <div role="alert"><p>{queueError}</p><button type="button" onClick={() => void refresh()}>Reintentar</button></div>}
          {!queueLoading && !queueError && items.length === 0 && <p>No hay elementos de alcance disponibles para revisión.</p>}
          {!queueLoading && !queueError && items.length > 0 && filteredItems.length === 0 && <p>No hay elementos para este filtro.</p>}
          <ul className="scope-review-queue">
            {filteredItems.map((item) => (
              <li key={item.scope_detail_id}>
                <button type="button" disabled={submitting || queueLoading} aria-pressed={selectedId === item.scope_detail_id}
                  onClick={() => setSelectedId(item.scope_detail_id)}>
                  <span className="scope-review-queue-description">{machineForDisplay(item)?.description ?? "Registro histórico sin descripción"}</span>
                  <span>{itemLabel(item)}</span>
                  {item.current && <small>{item.current.machine_review_required ? "LicitIA solicitó revisión" : "LicitIA no solicitó revisión"}</small>}
                  {!item.reviewable && <small>{blockReason(item)}</small>}
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <div aria-label="Detalle de alcance" aria-busy={detailLoading || submitting}>
          {detailLoading && <p role="status">Cargando detalle de alcance...</p>}
          {detailError && <div role="alert"><p>{detailError}</p><button type="button" onClick={() => void refresh()}>Reintentar detalle</button></div>}
          {!selectedId && !queueLoading && <p>Selecciona un elemento para revisar sus fuentes y decisiones.</p>}
          {detail && machine && <>
            <h4>Lo que LicitIA encontró</h4>
            {!detail.current && <p className="scope-review-warning">Evidencia histórica del registro retirado; no es un hallazgo vigente.</p>}
            <p>{machine.description}</p>
            <p>{detail.current ? (detail.current.machine_review_required ? "LicitIA originalmente requirió revisión." : "LicitIA no requirió revisión automática.")
              : (machine.review_required ? "El hallazgo histórico requería revisión." : "El hallazgo histórico no requería revisión.")}</p>
            {detail.current && <ul>{detail.current.source_projection.diagnostics.map((diagnostic, index) => (
              <li key={`${diagnostic.code}:${index}`}>{diagnosticLabels[diagnostic.code] ?? "Hay una observación documental que requiere atención."}
                <details><summary>Diagnóstico técnico</summary><p>{diagnostic.code}: {diagnostic.message}</p></details>
              </li>
            ))}</ul>}
            <h4>Fuente y ubicación</h4>
            <dl className="scope-review-provenance">
              <dt>Documento</dt><dd>{documents.find((document) => document.id === machine.source_document_id)?.original_filename ?? machine.source_document_id}</dd>
              <dt>Versión documental</dt><dd>{machine.document_revision}</dd>
              <dt>Página</dt><dd>{machine.source_page}</dd>
              <dt>Ubicación</dt><dd>{machine.source_locator || "Sin ubicación disponible"}</dd>
              {detail.current && <>
                <dt>Estado de la fuente</dt><dd>{sourceLabels[detail.current.source_projection.status] ?? "Estado de fuente pendiente de revisión"}</dd>
                <dt>Vigencia documental</dt><dd>{sourceLabels[detail.current.source_projection.document_effective_status ?? ""] ?? "Sin vigencia resuelta"}</dd>
                {detail.current.source_projection.partial_locator_status && <>
                  <dt>Estado de la ubicación</dt><dd>{sourceLabels[detail.current.source_projection.partial_locator_status] ?? "Ubicación pendiente de revisión"}</dd>
                </>}
              </>}
            </dl>
            <blockquote>{machine.source_excerpt}</blockquote>
            <a href={`${apiUrl}/tenders/${encodeURIComponent(tenderId)}/documents/${encodeURIComponent(machine.source_document_id)}/content#page=${machine.source_page}`}
              target="_blank" rel="noreferrer">Abrir documento fuente en página {machine.source_page}</a>
            <h4>Estado efectivo de revisión</h4>
            <p><strong>{itemLabel(detail)}</strong></p>
            {detail.current && <>
              <p>{humanLabels[detail.current.human_review_status]}</p>
              {detail.current.human_resolved_machine_review && <p>La decisión humana resolvió la revisión del hallazgo.</p>}
              <p>{detail.current.effective_description}</p>
              <p>{detail.current.accepted_execution_scope ? "Aceptado como alcance de ejecución." : "No aceptado como alcance de ejecución."}</p>
            </>}
            {!detail.reviewable && <p className="scope-review-warning">{blockReason(detail)}</p>}
            {detail.reviewable && detail.current && <>
              <div className="scope-review-actions">
                <button type="button" disabled={disabled} onClick={() => beginDecision("CONFIRMED")}>Confirmar</button>
                <button type="button" disabled={disabled} onClick={() => beginDecision("CORRECTED")}>Corregir</button>
                <button type="button" disabled={disabled} onClick={() => beginDecision("REJECTED")}>Rechazar</button>
              </div>
              {decision && <form onSubmit={(event) => void submit(event)} className="scope-review-form" aria-label="Decisión humana">
                {decision === "CONFIRMED" && <p>Se aceptará como alcance de ejecución: <strong>{detail.current.machine.description}</strong></p>}
                {decision === "CORRECTED" && <label>Descripción corregida
                  <textarea required value={description} disabled={submitting} onChange={(event) => setDescription(event.target.value)} />
                </label>}
                {decision === "REJECTED" && <p>El elemento no será aceptado como alcance de ejecución. La evidencia máquina y las decisiones permanecerán en el historial de auditoría. Confirma el rechazo para continuar.</p>}
                <label>Nota de revisión (opcional)<textarea value={note} disabled={submitting} onChange={(event) => setNote(event.target.value)} /></label>
                <div className="scope-review-actions">
                  <button type="submit" disabled={disabled || (decision === "CORRECTED" && !description.trim())}>
                    {submitting ? "Guardando decisión..." : decision === "REJECTED" ? "Confirmar rechazo" : decision === "CORRECTED" ? "Guardar corrección" : "Guardar confirmación"}
                  </button>
                  <button type="button" disabled={submitting} onClick={() => setDecision(null)}>Cancelar</button>
                </div>
              </form>}
            </>}
            <h4>Historial de revisión humana</h4>
            {detail.history.length === 0 ? <p>Sin decisiones humanas registradas.</p> : <ol className="scope-review-history">
              {detail.history.map((entry) => (
                <li key={entry.review.id} className={entry.applicable ? "scope-review-current" : "scope-review-historical"}>
                  <strong>Revisión {entry.review.revision} · {effectiveLabels[entry.review.decision]}</strong>
                  <p><time dateTime={entry.review.reviewed_at}>{new Date(entry.review.reviewed_at).toLocaleString("es-MX")}</time></p>
                  <p>{entry.applicable ? "Aplicable actualmente" : "Histórica / no aplicable"} · {historyLabels[entry.reason]}</p>
                  {entry.review.note && <p>Nota: {entry.review.note}</p>}
                  {entry.review.correction && <p>Descripción corregida: {entry.review.correction.description}</p>}
                  <details>
                    <summary>Evidencia revisada en esta decisión</summary>
                    <p>Hallazgo revisado: {entry.review.machine_snapshot.description}</p>
                    <p>Documento revisado: {documents.find((document) => document.id === entry.review.machine_snapshot.source_document_id)?.original_filename ?? entry.review.machine_snapshot.source_document_id}</p>
                    <p>Versión {entry.review.machine_snapshot.document_revision} · Página {entry.review.machine_snapshot.source_page} · Ubicación: {entry.review.machine_snapshot.source_locator}</p>
                    <blockquote>{entry.review.machine_snapshot.source_excerpt}</blockquote>
                  </details>
                </li>
              ))}
            </ol>}
          </>}
        </div>
      </div>
    </>
  );
}
