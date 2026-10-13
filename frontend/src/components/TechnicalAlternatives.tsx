import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  technicalAlternativesApi, alternativeMutationMessage,
  type AlternativeContent, type AlternativeLifecycle, type TechnicalAlternative,
} from "../api/technicalAlternatives";
import type { ComplianceEvaluation } from "../api/alternativeCompliance";
import { AlternativeCompliance } from "./AlternativeCompliance";
import { applicabilityLabels, complianceLabels, dateLabel, lifecycleLabels } from "./alternativeLabels";
import "./TechnicalAlternatives.css";

export type AlternativeWorkspaceProps = {
  apiUrl: string; tenderId: string;
  documents: readonly { id: string; original_filename: string }[];
};
export type MutationRunner = (operation: () => Promise<void>) => Promise<void>;
const emptyContent: AlternativeContent = { name: "", technical_description: "", assumptions: null, notes: null, lifecycle_state: "DRAFT" };

export function TechnicalAlternatives(props: AlternativeWorkspaceProps) {
  const [open, setOpen] = useState(false);
  return <section className="technical-alternatives" aria-labelledby="alternatives-title">
    <div className="alternative-heading"><div><h3 id="alternatives-title">Alternativas técnicas</h3>
      <p>Define cómo propones cumplir la licitación. La alternativa no cambia lo que exige el alcance contractual.</p></div>
      <button type="button" aria-expanded={open} aria-controls="alternatives-content" onClick={() => setOpen(!open)}>
        {open ? "Cerrar alternativas técnicas" : "Abrir alternativas técnicas"}</button></div>
    <div id="alternatives-content" hidden={!open}>{open && <AlternativesWorkspace key={`${props.apiUrl}:${props.tenderId}`} {...props} />}</div>
  </section>;
}

function AlternativesWorkspace(props: AlternativeWorkspaceProps) {
  const api = useMemo(() => technicalAlternativesApi(props.apiUrl, props.tenderId), [props.apiUrl, props.tenderId]);
  const [alternatives, setAlternatives] = useState<TechnicalAlternative[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [summaries, setSummaries] = useState<Record<string, ComplianceEvaluation | undefined>>({});
  const pending = useRef(false);
  const alive = useRef(false);
  const request = useRef(0);

  const load = useCallback(async () => {
    const generation = ++request.current;
    setLoading(true); setError(null); setSummaries({});
    try {
      const result = await api.list();
      if (!alive.current || generation !== request.current) return;
      setAlternatives(result);
      setSelectedId(previous => result.some(row => row.id === previous) ? previous : result[0]?.id ?? "");
    } catch {
      if (alive.current && generation === request.current) setError("No se pudieron cargar las alternativas. Verifica la conexión con el servidor local.");
    } finally {
      if (alive.current && generation === request.current) setLoading(false);
    }
  }, [api]);
  useEffect(() => { alive.current = true; void load(); return () => { alive.current = false; ++request.current; }; }, [load]);

  async function refresh() { await load(); if (alive.current) setRefreshVersion(value => value + 1); }
  const run: MutationRunner = async operation => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setMutationError(null); setFeedback(null);
    try {
      await operation();
      if (alive.current) setFeedback("Guardado confirmado por el servidor local.");
    } catch (failure: unknown) {
      if (!alive.current) return;
      setMutationError(alternativeMutationMessage(failure)); setCreating(false);
      await refresh();
    } finally {
      pending.current = false;
      if (alive.current) setBusy(false);
    }
  };
  function publish(row: TechnicalAlternative) {
    if (!alive.current) return;
    setAlternatives(previous => previous.map(item => item.id === row.id ? row : item));
    setSummaries(previous => ({ ...previous, [row.id]: undefined }));
  }
  const report = useCallback((id: string, evaluation: ComplianceEvaluation | undefined) => {
    if (alive.current) setSummaries(previous => ({ ...previous, [id]: evaluation }));
  }, []);

  return <>
    <div className="alternative-actions"><button type="button" disabled={busy || loading} onClick={() => { setCreating(true); setMutationError(null); }}>Crear alternativa</button>
      <button type="button" disabled={busy || loading} onClick={() => void refresh()}>Actualizar alternativas</button></div>
    {feedback && <p role="status">{feedback}</p>}
    {mutationError && <div role="alert" className="alternative-warning"><p>{mutationError}</p>
      <button type="button" disabled={busy || loading} onClick={() => void refresh()}>Actualizar información</button></div>}
    {creating && <AlternativeForm key="create" initial={emptyContent} busy={busy} title="Crear alternativa técnica" submitLabel="Guardar alternativa"
      onCancel={() => setCreating(false)} onSave={values => run(async () => {
        const row = await api.create(values);
        if (!alive.current) return;
        setCreating(false); setSelectedId(row.id); await load();
      })} />}
    {loading && <p role="status">Cargando alternativas...</p>}
    {error && <div role="alert"><p>{error}</p><button type="button" disabled={busy} onClick={() => void refresh()}>Reintentar alternativas</button></div>}
    {!loading && !error && alternatives.length === 0 && <p>No hay alternativas técnicas todavía.</p>}
    <div className="alternative-layout"><aside aria-label="Lista de alternativas técnicas"><ul>
      {alternatives.map(row => <li key={row.id}><button type="button" disabled={busy || loading || !!error} aria-pressed={selectedId === row.id}
        onClick={() => { setSelectedId(row.id); setCreating(false); setMutationError(null); setFeedback(null); }}>
        <strong>{row.current_revision.name}</strong><span>Revisión {row.current_revision.revision} · {lifecycleLabels[row.current_revision.lifecycle_state]}</span>
        <span className="alternative-excerpt">{row.current_revision.technical_description}</span>
        {summaries[row.id] && <span>Evaluación consultada: {applicabilityLabels[summaries[row.id]!.applicability]} · {complianceLabels[summaries[row.id]!.overall_status]}</span>}
      </button></li>)}
    </ul></aside>
      <div aria-label="Detalle de alternativa">{!loading && !error && selectedId && <AlternativeDetail key={selectedId} {...props}
        alternativeId={selectedId} refreshVersion={refreshVersion} busy={busy} run={run} publish={publish} report={report} />}</div>
    </div>
  </>;
}

function AlternativeDetail(props: AlternativeWorkspaceProps & {
  alternativeId: string; refreshVersion: number; busy: boolean; run: MutationRunner;
  publish: (row: TechnicalAlternative) => void;
  report: (id: string, row: ComplianceEvaluation | undefined) => void;
}) {
  const api = useMemo(() => technicalAlternativesApi(props.apiUrl, props.tenderId), [props.apiUrl, props.tenderId]);
  const [detail, setDetail] = useState<TechnicalAlternative | null>(null);
  const [error, setError] = useState(false);
  const [mode, setMode] = useState<"edit" | "archive" | null>(null);
  const [retry, setRetry] = useState(0);
  const alive = useRef(false);
  useEffect(() => {
    alive.current = true; let active = true;
    setDetail(null); setError(false); setMode(null);
    void api.detail(props.alternativeId).then(row => { if (active) setDetail(row); }, () => { if (active) setError(true); });
    return () => { active = false; alive.current = false; };
  }, [api, props.alternativeId, props.refreshVersion, retry]);
  if (error) return <div role="alert"><p>No se pudo cargar la alternativa.</p><button type="button" disabled={props.busy} onClick={() => setRetry(value => value + 1)}>Reintentar detalle</button></div>;
  if (!detail) return <p role="status">Cargando detalle de alternativa...</p>;
  const current = detail.current_revision;
  async function save(values: AlternativeContent) {
    await props.run(async () => {
      const row = await api.append(detail!.id, { ...values, expected_current_revision: current.revision });
      if (!alive.current) return;
      setDetail(row); setMode(null); props.publish(row);
    });
  }
  return <>
    <h4>{current.name}</h4><p>Revisión actual {current.revision} · {lifecycleLabels[current.lifecycle_state]}</p>
    <p className="alternative-text">{current.technical_description}</p>
    {current.assumptions && <p className="alternative-text">Supuestos: {current.assumptions}</p>}
    {current.notes && <p className="alternative-text">Notas: {current.notes}</p>}
    <div className="alternative-actions"><button type="button" disabled={props.busy} onClick={() => setMode("edit")}>Crear nueva revisión</button>
      {current.lifecycle_state !== "ARCHIVED" && <button type="button" disabled={props.busy} onClick={() => setMode("archive")}>Archivar alternativa</button>}</div>
    {mode === "edit" && <AlternativeForm key={`${detail.id}:${current.revision}`} initial={current} busy={props.busy} title="Nueva revisión de alternativa" submitLabel="Guardar nueva revisión" onCancel={() => setMode(null)} onSave={save} />}
    {mode === "archive" && <div role="group" aria-label="Confirmación de archivo" className="alternative-warning">
      <p>Archivar conserva la alternativa y su historial, pero deja de considerarla una propuesta activa.</p>
      <button type="button" disabled={props.busy} onClick={() => void save({ name: current.name, technical_description: current.technical_description,
        assumptions: current.assumptions, notes: current.notes, lifecycle_state: "ARCHIVED" })}>Confirmar archivo</button>
      <button type="button" disabled={props.busy} onClick={() => setMode(null)}>Cancelar archivo</button></div>}
    <details><summary>Historial de revisiones de alternativa</summary><ol className="alternative-history">
      {detail.revisions.map(revision => <li key={revision.id}><strong>Revisión {revision.revision} · {revision.name} · {lifecycleLabels[revision.lifecycle_state]}</strong>
        <p><time dateTime={revision.created_at}>{dateLabel(revision.created_at)}</time></p><p className="alternative-text">{revision.technical_description}</p>
        {revision.assumptions && <p>Supuestos: {revision.assumptions}</p>}{revision.notes && <p>Notas: {revision.notes}</p>}</li>)}
    </ol></details>
    <AlternativeCompliance key={`compliance:${detail.id}:${current.revision}`} {...props} alternative={detail} />
  </>;
}

function AlternativeForm({ initial, busy, title, submitLabel, onCancel, onSave }: {
  initial: AlternativeContent; busy: boolean; title: string; submitLabel: string;
  onCancel: () => void; onSave: (values: AlternativeContent) => Promise<void>;
}) {
  const [values, setValues] = useState<AlternativeContent>({ name: initial.name, technical_description: initial.technical_description,
    assumptions: initial.assumptions, notes: initial.notes, lifecycle_state: initial.lifecycle_state });
  const valid = values.name.trim().length > 0 && values.name.trim().length <= 255 && !!values.technical_description.trim();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!valid || busy) return;
    void onSave({ ...values, name: values.name.trim(), technical_description: values.technical_description.trim(),
      assumptions: values.assumptions?.trim() || null, notes: values.notes?.trim() || null });
  }
  return <form aria-label={title} className="alternative-form" onSubmit={submit}><h4>{title}</h4><fieldset disabled={busy}>
    <label>Nombre de alternativa<input required maxLength={255} value={values.name} onChange={event => setValues({ ...values, name: event.target.value })} /></label>
    <label>Descripción técnica<textarea required value={values.technical_description} onChange={event => setValues({ ...values, technical_description: event.target.value })} /></label>
    <label>Supuestos (opcional)<textarea value={values.assumptions ?? ""} onChange={event => setValues({ ...values, assumptions: event.target.value })} /></label>
    <label>Notas (opcional)<textarea value={values.notes ?? ""} onChange={event => setValues({ ...values, notes: event.target.value })} /></label>
    <label>Estado de alternativa<select value={values.lifecycle_state} onChange={event => setValues({ ...values, lifecycle_state: event.target.value as AlternativeLifecycle })}>
      {Object.entries(lifecycleLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    {values.lifecycle_state === "ARCHIVED" && <p>Archivada: se conservará el historial y no podrá iniciar una evaluación nueva.</p>}
    <button type="submit" disabled={!valid || busy}>{busy ? "Guardando..." : submitLabel}</button>
    <button type="button" disabled={busy} onClick={onCancel}>Cancelar</button>
  </fieldset></form>;
}
