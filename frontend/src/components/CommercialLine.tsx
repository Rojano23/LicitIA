import { useEffect, useRef, useState } from "react";
import { commercialApi, costSources, valueOrigins, type CommercialInputs, type CommercialRead } from "../api/commercial";

type Props = { apiUrl: string; tenderId: string; scopeDetailId: string; documents: readonly { id: string; original_filename: string }[] };
const empty: CommercialInputs = { cost_source_type: "MANUAL", cost_value_origin: "MANUAL_INPUT", currency: null,
  reference_party_name: null, reference_party_reference: null, reference_party_note: null, quote_document_id: null, quote_reference: null,
  unit_cost: null, offered_unit_price: null, calculation_mode: "PRICE_FIRST", calculation_basis: null, markup_percent: null,
  target_margin_percent: null, quantity_id: null, notes: null, input_origin: "UI", actor_label: null };

export function CommercialLine({ apiUrl, tenderId, scopeDetailId, documents }: Props) {
  const [opened, setOpened] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [line, setLine] = useState<CommercialRead | null>(null);
  const [form, setForm] = useState<CommercialInputs>(empty);
  const [dirty, setDirty] = useState<Partial<CommercialInputs>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  function accept(row: CommercialRead | null) { setLine(row); setForm(row?.inputs ?? empty); setDirty({}); setLoaded(true); }
  async function load() {
    setOpened(true); setBusy(true); setError(null);
    try { const row = await commercialApi.read(apiUrl, tenderId, scopeDetailId); if (mounted.current) accept(row); }
    catch { if (mounted.current) { setLoaded(false); setError("No se pudo consultar la decisión comercial. Actualiza antes de guardar."); } }
    finally { if (mounted.current) setBusy(false); }
  }
  function field<K extends keyof CommercialInputs>(key: K, value: CommercialInputs[K]) {
    setForm(prev => ({ ...prev, [key]: value })); setDirty(prev => ({ ...prev, [key]: value }));
  }
  async function save() {
    setBusy(true); setError(null);
    try {
      const row = await commercialApi.save(apiUrl, tenderId, scopeDetailId, { ...(line ? dirty : form), input_origin: "UI" }, line);
      if (mounted.current) accept(row);
    } catch { if (mounted.current) setError("No se pudo guardar. Revisa los decimales o actualiza: pudo cambiar la revisión o la fuente. Conservamos tus entradas."); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function apply() {
    if (!line) return;
    const replace = line.price_method === "MANUAL";
    if (replace && !window.confirm("¿Reemplazar el precio manual por la recomendación? La decisión anterior quedará en el historial.")) return;
    setBusy(true); setError(null);
    try { const row = await commercialApi.apply(apiUrl, tenderId, scopeDetailId, line, replace); if (mounted.current) accept(row); }
    catch { if (mounted.current) setError("No se pudo aplicar el cálculo. Actualiza y revisa moneda, costo y regla."); }
    finally { if (mounted.current) setBusy(false); }
  }
  const text = (key: "unit_cost" | "offered_unit_price" | "markup_percent" | "target_margin_percent" | "reference_party_name" | "quote_reference" | "notes", label: string) =>
    <label>{label} <input value={form[key] ?? ""} onChange={e => field(key, e.target.value || null)} /></label>;
  return <section aria-label="Decisión comercial provisional">
    <button onClick={() => void load()} disabled={busy}>{opened ? "Actualizar comercial" : "Comercial"}</button>
    {error && <p role="alert">{error}</p>}
    {opened && loaded && <>
      <p>Decisión comercial humana. Importes decimales; sin conversión de moneda. Guarda antes de aplicar una recomendación.</p>
      {line?.source.scope && <p>{line.source.scope.description} · Revisión: {line.source.scope.review_status}</p>}
      {line?.source.quantities.map(q => <p key={q.id}>Cantidad heredada: {q.quantity_raw} {q.unit_raw} · {q.status}</p>)}
      <fieldset disabled={busy}><legend>Costo y precio</legend>
        <label>Fuente de costo <select value={form.cost_source_type} onChange={e => field("cost_source_type", e.target.value as CommercialInputs["cost_source_type"])}>{costSources.map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Origen del costo <select value={form.cost_value_origin} onChange={e => field("cost_value_origin", e.target.value as CommercialInputs["cost_value_origin"])}>{valueOrigins.map(v => <option key={v}>{v}</option>)}</select></label>
        {text("reference_party_name", "Parte de referencia")}{text("quote_reference", "Referencia de cotización (opcional)")}
        <label>Documento de cotización <select value={form.quote_document_id ?? ""} onChange={e => field("quote_document_id", e.target.value || null)}><option value="">Sin documento</option>{documents.map(d => <option key={d.id} value={d.id}>{d.original_filename}</option>)}</select></label>
        <label>Moneda <select value={form.currency ?? ""} onChange={e => field("currency", (e.target.value || null) as CommercialInputs["currency"])}><option value="">Sin moneda</option>{["MXN", "USD", "EUR"].map(v => <option key={v}>{v}</option>)}</select></label>
        {text("unit_cost", "Costo unitario")}
        <label>Modo <select value={form.calculation_mode} onChange={e => field("calculation_mode", e.target.value as CommercialInputs["calculation_mode"])}><option value="PRICE_FIRST">Precio primero</option><option value="COST_FIRST">Costo primero</option></select></label>
        <label>Regla <select value={form.calculation_basis ?? ""} onChange={e => field("calculation_basis", (e.target.value || null) as CommercialInputs["calculation_basis"])}><option value="">Sin regla</option><option value="MARKUP">Markup</option><option value="MARGIN">Margen</option></select></label>
        {text("markup_percent", "Markup objetivo (%)")}{text("target_margin_percent", "Margen objetivo (%)")}{text("offered_unit_price", "Precio unitario ofrecido")}{text("notes", "Notas comerciales")}
        {line && line.source.quantities.length > 1 && <label>Cantidad canónica <select value={form.quantity_id ?? ""} onChange={e => field("quantity_id", e.target.value || null)}><option value="">Sin selección</option>{line.source.quantities.map(q => <option key={q.id} value={q.id}>{q.quantity_raw} {q.unit_raw} · {q.id}</option>)}</select></label>}
        <button onClick={() => void save()}>Guardar decisión comercial</button>
      </fieldset>
      {line && <>
        <p>Estado comercial: {line.summary.status} · Precio: {line.price_method ?? "sin elegir"} · Origen: {line.price_value_origin ?? "sin elegir"}</p>
        <dl>{([['recommended_unit_price','Recomendación unitaria'],['total_cost','Costo total'],['offered_total','Total ofertado'],['profit','Utilidad'],['actual_markup_percent','Markup efectivo (%)'],['actual_margin_percent','Margen efectivo (%)']] as const).map(([key,label]) => <div key={key}><dt>{label}</dt><dd>{line.summary[key] ?? "Sin resolver"}{key.includes("percent") ? "" : ` ${line.summary.currency ?? "sin moneda"}`}</dd></div>)}</dl>
        {line.summary.warnings.map(w => <p key={w}>Revisar: {w}</p>)}
        <button disabled={busy || Object.keys(dirty).length > 0 || !line.summary.recommended_unit_price} onClick={() => void apply()}>Aplicar recomendación al precio</button>
        <details><summary>Historial comercial</summary>{line.history.map(h => <p key={h.revision}>Revisión {h.revision} · {h.created_at} · {h.action} · {h.inputs.input_origin} · {h.price_method} · {h.inputs.offered_unit_price ?? "sin precio"} {h.inputs.currency} · {h.price_value_origin}</p>)}</details>
      </>}
    </>}
  </section>;
}
