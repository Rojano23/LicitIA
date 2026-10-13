import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  alternativeComplianceApi, type ComplianceDecisionWrite, type ComplianceEvaluation,
  type ComplianceItem, type ComplianceStatus, type ScopeSnapshot,
} from "../api/alternativeCompliance";
import type { TechnicalAlternative } from "../api/technicalAlternatives";
import type { AlternativeWorkspaceProps, MutationRunner } from "./TechnicalAlternatives";
import { applicabilityLabels, complianceLabels, dateLabel, scopeStateLabels, staleExplanations } from "./alternativeLabels";

type Props = AlternativeWorkspaceProps & {
  alternative: TechnicalAlternative; refreshVersion: number; busy: boolean; run: MutationRunner;
  report: (id: string, row: ComplianceEvaluation | undefined) => void;
};

export function AlternativeCompliance({ apiUrl, tenderId, documents, alternative, refreshVersion, busy, run, report }: Props) {
  const api = useMemo(() => alternativeComplianceApi(apiUrl, tenderId, alternative.id), [apiUrl, tenderId, alternative.id]);
  const [scope, setScope] = useState<ScopeSnapshot | null>(null);
  const [history, setHistory] = useState<ComplianceEvaluation[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [evaluation, setEvaluation] = useState<ComplianceEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [scopeError, setScopeError] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const alive = useRef(false);
  const loadRequest = useRef(0);
  const detailRequest = useRef(0);

  const load = useCallback(async () => {
    const request = ++loadRequest.current;
    setLoading(true); setScope(null); setHistoryError(false); setScopeError(false);
    setEvaluation(null); ++detailRequest.current;
    const [evaluations, snapshot] = await Promise.allSettled([api.list(), api.scope()]);
    if (!alive.current || request !== loadRequest.current) return;
    if (evaluations.status === "fulfilled") {
      setHistory(evaluations.value);
      setSelectedId(previous => evaluations.value.some(row => row.id === previous) ? previous
        : evaluations.value.find(row => row.applicability === "CURRENT")?.id ?? evaluations.value[0]?.id ?? "");
      report(alternative.id, evaluations.value.find(row => row.applicability === "CURRENT"));
    } else { setHistoryError(true); setHistory([]); setSelectedId(""); report(alternative.id, undefined); }
    if (snapshot.status === "fulfilled") setScope(snapshot.value); else setScopeError(true);
    setLoading(false);
  }, [api, alternative.id, report]);

  const loadDetail = useCallback(async (id: string) => {
    const request = ++detailRequest.current;
    setEvaluation(null); setDetailLoading(true); setDetailError(false);
    try {
      const row = await api.detail(id);
      if (!alive.current || request !== detailRequest.current) return;
      setEvaluation(row); report(alternative.id, row);
    } catch {
      if (alive.current && request === detailRequest.current) setDetailError(true);
    } finally { if (alive.current && request === detailRequest.current) setDetailLoading(false); }
  }, [api, alternative.id, report]);

  useEffect(() => {
    alive.current = true; void load();
    return () => { alive.current = false; ++loadRequest.current; ++detailRequest.current; };
  }, [load, alternative.current_revision.revision, refreshVersion]);
  useEffect(() => {
    if (!loading && !historyError && selectedId) void loadDetail(selectedId);
    else if (!selectedId) { setEvaluation(null); setDetailLoading(false); ++detailRequest.current; }
  }, [selectedId, loading, historyError, loadDetail]);

  async function createEvaluation() {
    if (!scope || busy || loading || historyError || scopeError) return;
    await run(async () => {
      const row = await api.create({
        expected_alternative_revision: alternative.current_revision.revision,
        expected_alternative_fingerprint: alternative.current_revision.fingerprint,
        expected_scope_snapshot_fingerprint: scope.fingerprint,
      });
      if (!alive.current) return;
      setHistory(previous => previous.some(value => value.id === row.id)
        ? previous.map(value => value.id === row.id ? row : value) : [...previous, row]);
      setSelectedId(row.id); setEvaluation(row); report(alternative.id, row);
    });
  }
  async function save(item: ComplianceItem, values: Omit<ComplianceDecisionWrite, "expected_current_decision_revision">) {
    if (!evaluation || busy || loading || detailLoading || detailError || evaluation.applicability !== "CURRENT") return;
    await run(async () => {
      const row = await api.decide(evaluation.id, item.item_key, { ...values,
        expected_current_decision_revision: item.latest_decision?.revision ?? null });
      if (!alive.current) return;
      setEvaluation(row); setHistory(previous => previous.map(value => value.id === row.id ? row : value));
      report(alternative.id, row);
    });
  }
  const archived = alternative.current_revision.lifecycle_state === "ARCHIVED";
  return <section className="alternative-compliance" aria-label="Evaluación de cumplimiento">
    <h4>Evaluación de cumplimiento</h4><p>Alternativa actual: revisión {alternative.current_revision.revision}. Cada juicio técnico es una decisión humana.</p>
    <button type="button" disabled={busy || loading || detailLoading} onClick={() => void load()}>Actualizar evaluaciones</button>
    {loading && <p role="status">Cargando evaluación...</p>}
    {historyError && <div role="alert"><p>No se pudieron cargar las evaluaciones.</p><button type="button" disabled={busy} onClick={() => void load()}>Reintentar evaluaciones</button></div>}
    {scopeError && <div role="alert"><p>No se pudo cargar el alcance contractual vigente.</p><button type="button" disabled={busy} onClick={() => void load()}>Reintentar alcance</button></div>}
    {scope && <p>Alcance contractual vigente: {scope.unresolved ? "contiene contexto sin resolver" : "sin contexto pendiente reportado por el servidor"}.</p>}
    {archived ? <p className="alternative-warning">La alternativa está archivada. Conserva sus evaluaciones históricas, pero no puede iniciar una nueva.</p>
      : <button type="button" disabled={busy || loading || !scope || historyError || scopeError} onClick={() => void createEvaluation()}>Crear nueva evaluación</button>}
    {!loading && !historyError && history.length === 0 && <p>Esta alternativa aún no tiene una evaluación de cumplimiento.</p>}
    {history.length > 0 && <div><h5>Historial de evaluaciones</h5><ul className="evaluation-list">
      {history.map(row => <li key={row.id}><button type="button" aria-pressed={selectedId === row.id} disabled={busy || loading || detailLoading}
        onClick={() => setSelectedId(row.id)}>
        Revisión evaluada {row.alternative_revision.revision} · {dateLabel(row.created_at)} · {applicabilityLabels[row.applicability]} · {complianceLabels[row.overall_status]}
      </button></li>)}
    </ul></div>}
    {detailLoading && <p role="status">Cargando detalle de evaluación...</p>}
    {detailError && <div role="alert"><p>No se pudo cargar el detalle de evaluación.</p>
      <button type="button" disabled={busy} onClick={() => void loadDetail(selectedId)}>Reintentar evaluación</button></div>}
    {evaluation && <div aria-label="Detalle de evaluación" aria-busy={busy}>
      {evaluation.applicability !== "CURRENT" && <div role="alert" className="alternative-stale">
        <strong>Evaluación histórica desactualizada</strong><p>{staleExplanations[evaluation.applicability]}</p>
        <p>No admite nuevas decisiones. Inicia una evaluación nueva con la alternativa y el alcance vigentes.</p></div>}
      <div className="evaluation-summary"><h5>{complianceLabels[evaluation.overall_status]}</h5>
        <p>{applicabilityLabels[evaluation.applicability]} · Revisión evaluada {evaluation.alternative_revision.revision}</p>
        {evaluation.applicability !== "CURRENT" && <p>Resultado histórico: {complianceLabels[evaluation.historical_aggregate]}.</p>}
        <p>Alcance congelado: {evaluation.scope_snapshot.unresolved ? "contexto contractual sin resolver" : "sin contexto pendiente reportado por el servidor"}.</p>
        <dl className="compliance-counts" aria-label="Conteos de evaluación">
          {(Object.keys(evaluation.counts) as ComplianceStatus[]).map(status => <div key={status}><dt>{complianceLabels[status]}</dt><dd>{evaluation.counts[status]}</dd></div>)}
        </dl>
      </div>
      {evaluation.scope_snapshot.unresolved && <div className="alternative-warning"><strong>Ambigüedad contractual pendiente</strong>
        <p>El cumplimiento de una alternativa no resuelve ambigüedades del alcance ni de sus fuentes. Revisa el alcance contractual en su flujo de revisión.</p></div>}
      <details><summary>Alternativa exacta evaluada</summary><p>{evaluation.alternative_revision.name}</p>
        <p className="alternative-text">{evaluation.alternative_revision.technical_description}</p>
        {evaluation.alternative_revision.assumptions && <p>Supuestos: {evaluation.alternative_revision.assumptions}</p>}</details>
      {evaluation.items.length === 0 && <p>Esta evaluación no contiene obligaciones evaluables. El estado mostrado proviene del servidor.</p>}
      {evaluation.items.map(item => <ComplianceObligation key={`${evaluation.id}:${item.item_key}:${item.latest_decision?.id ?? "none"}`} item={item}
        apiUrl={apiUrl} tenderId={tenderId} documents={documents} busy={busy}
        historical={evaluation.applicability !== "CURRENT"}
        disabled={evaluation.applicability !== "CURRENT" || loading || detailLoading || detailError || historyError}
        onSave={values => save(item, values)} />)}
    </div>}
  </section>;
}

function ComplianceObligation({ item, apiUrl, tenderId, documents, busy, disabled, historical, onSave }: {
  item: ComplianceItem; apiUrl: string; tenderId: string; documents: AlternativeWorkspaceProps["documents"];
  busy: boolean; disabled: boolean; historical: boolean;
  onSave: (values: Omit<ComplianceDecisionWrite, "expected_current_decision_revision">) => Promise<void>;
}) {
  const [status, setStatus] = useState<ComplianceDecisionWrite["status"] | "">("");
  const [rationale, setRationale] = useState("");
  const [reference, setReference] = useState("");
  const source = item.snapshot.machine;
  const blocked = busy || disabled;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (blocked || !status || !rationale.trim()) return;
    void onSave({ status, rationale: rationale.trim(), evidence_note: reference.trim() || null });
  }
  return <article className="compliance-obligation" aria-label={item.snapshot.effective_description}>
    <div className="contractual-obligation"><h5>Lo que exige la licitación</h5><p className="alternative-text">{item.snapshot.effective_description}</p>
      <dl className="alternative-provenance"><dt>Documento fuente</dt><dd>{documents.find(row => row.id === source.source_document_id)?.original_filename ?? source.source_document_id ?? "Documento no disponible"}</dd>
        <dt>Versión documental</dt><dd>{source.document_revision ?? "No disponible"}</dd>
        <dt>Página</dt><dd>{source.source_page ?? "No disponible"}</dd><dt>Ubicación</dt><dd>{source.source_locator ?? "No disponible"}</dd>
        <dt>Revisión humana de alcance</dt><dd>{scopeStateLabels[item.snapshot.human_review_status] ?? "Estado de revisión no disponible"}
          {item.snapshot.current_review_revision !== null && ` · Revisión ${item.snapshot.current_review_revision}`}</dd>
        <dt>Estado de alcance</dt><dd>{scopeStateLabels[item.snapshot.effective_status] ?? "Estado contractual por revisar"}</dd>
        {item.snapshot.source_projection && <><dt>Estado de fuente</dt><dd>{scopeStateLabels[item.snapshot.source_projection.status] ?? "Estado de fuente por revisar"}</dd></>}
      </dl>
      {source.source_excerpt && <blockquote>{source.source_excerpt}</blockquote>}
      {source.source_document_id && <a href={`${apiUrl}/tenders/${encodeURIComponent(tenderId)}/documents/${encodeURIComponent(source.source_document_id)}/content${source.source_page ? `#page=${source.source_page}` : ""}`} target="_blank" rel="noreferrer">Abrir documento fuente</a>}
      {item.snapshot.unresolved && <p className="alternative-warning">Contexto contractual sin resolver. Este juicio técnico no confirma ni corrige la obligación contractual.</p>}
    </div>
    <div className="human-assessment"><h5>Juicio técnico sobre esta alternativa</h5>
      {historical && <p className="alternative-warning">Juicio histórico; no expresa cumplimiento vigente.</p>}
      <strong>{complianceLabels[item.status]}</strong>
      {item.latest_decision && <><p className="alternative-text">Justificación: {item.latest_decision.rationale}</p>
        {item.latest_decision.evidence_note && <p className="alternative-text">Evidencia / referencia: {item.latest_decision.evidence_note}</p>}</>}
      <form aria-label={`Evaluar obligación: ${item.snapshot.effective_description}`} onSubmit={submit} className="alternative-form">
        <fieldset disabled={blocked}><legend>Registrar juicio humano</legend>
          <label>Decisión de cumplimiento<select required value={status} onChange={event => setStatus(event.target.value as ComplianceDecisionWrite["status"] | "")}>
            <option value="">Selecciona una decisión</option>
            {(["COMPLIANT", "PARTIAL", "NON_COMPLIANT", "REVIEW_REQUIRED"] as const).map(value => <option key={value} value={value}>{complianceLabels[value]}</option>)}
          </select></label>
          <label>Justificación técnica<textarea required value={rationale} onChange={event => setRationale(event.target.value)} /></label>
          <label>Evidencia / referencia (opcional)<textarea value={reference} onChange={event => setReference(event.target.value)} /></label>
          <button type="submit" disabled={blocked || !status || !rationale.trim()}>{busy ? "Guardando juicio..." : "Guardar juicio técnico"}</button>
        </fieldset>
      </form>
      <details><summary>Historial de decisiones técnicas</summary>{item.decisions.length === 0 ? <p>Sin decisiones técnicas registradas.</p> : <ol className="alternative-history">
        {item.decisions.map(row => <li key={row.id}><strong>Revisión {row.revision} · {complianceLabels[row.status]}</strong>
          <p><time dateTime={row.created_at}>{dateLabel(row.created_at)}</time></p><p className="alternative-text">{row.rationale}</p>
          {row.evidence_note && <p className="alternative-text">Evidencia / referencia: {row.evidence_note}</p>}</li>)}
      </ol>}</details>
    </div>
  </article>;
}
