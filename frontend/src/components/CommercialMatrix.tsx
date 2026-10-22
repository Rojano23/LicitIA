import { CommercialAuditDetails } from "./CommercialAuditDetails";
import { CommercialSpreadsheet } from "./CommercialSpreadsheet";
import { useEffect, useRef, useState } from "react";
import { costSources, type CommercialInputs } from "../api/commercial";
import { matrixApi, target, type MatrixRead, type MatrixRow, type BulkWrite, type BulkRead, type BulkAction } from "../api/commercialMatrix";

type Props = { apiUrl: string; tenderId: string };
type EditKey = "unit_cost" | "offered_unit_price" | "markup_percent" | "target_margin_percent" | "reference_party_name" | "notes";
function EditableRow({ apiUrl,tenderId,row, selected, toggle, disabled, preview, invalidate, draft, onDraft }: {
  apiUrl: string; tenderId: string; row: MatrixRow; selected: boolean; toggle: () => void; disabled: boolean;
  preview: (row: MatrixRow, fields: Partial<CommercialInputs>) => void; invalidate: () => void;
  draft: Partial<CommercialInputs>; onDraft: (fields: Partial<CommercialInputs>) => void;
}) {
  const changes = draft;
  const value = {...row.inputs,...changes};
  function edit<K extends keyof CommercialInputs>(key: K, val: CommercialInputs[K]) { onDraft({...changes,[key]:val}); invalidate(); }
  const input = (key: EditKey, label: string) => <input aria-label={`${label} ${row.item_reference ?? row.scope_id}`} value={value[key] ?? ""} disabled={disabled}
    onChange={e => edit(key,e.target.value || null)} onKeyDown={e => { if (e.key === "Enter" && Object.keys(changes).length) { e.preventDefault(); preview(row,changes); } }} />;
  const select = <K extends "currency" | "cost_source_type" | "calculation_mode" | "calculation_basis">(key: K, label: string, options: readonly string[]) =>
    <select aria-label={`${label} ${row.item_reference ?? row.scope_id}`} disabled={disabled} value={value[key] ?? ""} onChange={e => edit(key,(e.target.value || null) as CommercialInputs[K])}>
      {key === "currency" || key === "calculation_basis" ? <option value="">Sin definir</option> : null}{options.map(v => <option key={v}>{v}</option>)}</select>;
  return <tr>
    <td><input type="checkbox" aria-label={`Seleccionar ${row.item_reference ?? row.scope_id}`} checked={selected} onChange={toggle} disabled={disabled} /></td>
    <td>{row.item_reference ?? row.scope_id}<p>{row.description}</p>{row.source.quantities.map(q => <p key={q.id}>{q.quantity_raw} {q.unit_raw} · {q.status}</p>)}
      {row.source.scope && <details><summary>Fuente y revisión</summary><p>{row.source.scope.source.filename}, p. {row.source.scope.source.page} · {row.source.scope.review_status}</p><blockquote>{row.source.scope.source.excerpt}</blockquote></details>}</td>
    <td>{select("cost_source_type","Fuente de costo",costSources)}{input("reference_party_name","Parte")}{input("unit_cost","Costo")}{select("currency","Moneda",["MXN","USD","EUR"])}</td>
    <td>{select("calculation_mode","Modo",["COST_FIRST","PRICE_FIRST"])}{select("calculation_basis","Regla",["MARKUP","MARGIN"])}{input("markup_percent","Markup %")}{input("target_margin_percent","Margen %")}</td>
    <td>{input("offered_unit_price","Precio")}{row.manual_price_protected && <p>Precio manual protegido</p>}{input("notes","Notas")}
      <button disabled={disabled || !Object.keys(changes).length} onClick={() => preview(row,changes)}>Vista previa de fila {row.item_reference}</button></td>
    <td><p>Costo total: {row.summary.total_cost ?? "Sin resolver"}</p><p>Oferta: {row.summary.offered_total ?? "Sin resolver"}</p><p>Utilidad: {row.summary.profit ?? "Sin resolver"}</p><p>{row.inputs.currency ?? "Sin moneda"}</p><p>Markup: {row.summary.actual_markup_percent ?? "Sin resolver"}% · Margen: {row.summary.actual_margin_percent ?? "Sin resolver"}%</p></td>
    <td>{row.initialized ? row.summary.status : "Sin inicializar · INCOMPLETE"}{row.summary.readiness ? row.summary.readiness.reasons.map(reason => <p key={reason.code}>{reason.severity}: {reason.code}</p>) : row.summary.warnings.map(w => <p key={w}>{w}</p>)}
      {row.initialized && <CommercialAuditDetails apiUrl={apiUrl} tenderId={tenderId} scopeId={row.scope_id} disabled={disabled}/> }</td>
  </tr>;
}

export function CommercialMatrix({ apiUrl,tenderId }: Props) {
  const [data,setData] = useState<MatrixRead | null>(null);
  const [opened,setOpened] = useState(false), [busy,setBusy] = useState(false);
  const [error,setError] = useState<string | null>(null);
  const [drafts,setDrafts] = useState<Record<string,Partial<CommercialInputs>>>({});
  const [selected,setSelected] = useState<Set<string>>(new Set());
  const [filter,setFilter] = useState("ALL"), [sourceFilter,setSourceFilter] = useState(""), [currencyFilter,setCurrencyFilter] = useState("");
  const [action,setAction] = useState<BulkAction>("PATCH"), [patchField,setPatchField] = useState("cost_source_type"), [patchValue,setPatchValue] = useState("INTERNAL_COST"), [percent,setPercent] = useState("");
  const [copySource,setCopySource] = useState("");
  const [defaultCurrency,setDefaultCurrency] = useState<CommercialInputs["currency"]>(null), [defaultMode,setDefaultMode] = useState<CommercialInputs["calculation_mode"]>("PRICE_FIRST");
  const [defaultBasis,setDefaultBasis] = useState<CommercialInputs["calculation_basis"]>(null), [defaultPercent,setDefaultPercent] = useState("");
  const [replace,setReplace] = useState(false), [confirmCurrency,setConfirmCurrency] = useState(false), [recalculate,setRecalculate] = useState(false);
  const [pending,setPending] = useState<BulkWrite | null>(null), [result,setResult] = useState<BulkRead | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current=true; return () => {mounted.current=false;}; },[]);
  function invalidate() { setPending(null); setResult(null); }
  async function load() {
    if (Object.keys(drafts).length && !window.confirm("¿Descartar las ediciones sin aplicar y actualizar la matriz?")) return;
    setDrafts({});
    setOpened(true); setBusy(true); setError(null); invalidate();
    try { const next=await matrixApi.read(apiUrl,tenderId); if(mounted.current) {setData(next);setSelected(new Set());} }
    catch { if(mounted.current) setError("No se pudo consultar la matriz. Los datos visibles pueden estar desactualizados."); }
    finally {if(mounted.current) setBusy(false);}
  }
  const visible = (data?.rows ?? []).filter(row => (filter === "ALL" || (filter === "MISSING_COST" ? row.inputs.unit_cost === null : filter === "MISSING_PRICE" ? row.inputs.offered_unit_price === null : row.summary.status === filter)) && (!sourceFilter || row.inputs.cost_source_type === sourceFilter) && (!currencyFilter || (row.inputs.currency ?? "UNSPECIFIED") === currencyFilter));
  const chosen = visible.filter(row => selected.has(row.scope_id));
  const defaults: Partial<CommercialInputs> = {calculation_mode:defaultMode,...(defaultCurrency ? {currency:defaultCurrency}:{}),...(defaultBasis ? {calculation_basis:defaultBasis,[defaultBasis === "MARKUP" ? "markup_percent":"target_margin_percent"]:defaultPercent || null}:{})};
  function request(rows: MatrixRow[], kind: BulkAction, changes: Partial<CommercialInputs>): BulkWrite {
    const source = data?.rows.find(row => row.scope_id === copySource);
    return {targets:rows.map(target),action:kind,changes,defaults,row_changes:Object.fromEntries(rows.filter(r => drafts[r.scope_id]).map(r => [r.scope_id,drafts[r.scope_id]])),copy_from:kind === "COPY_SETTINGS" && source ? target(source):undefined,
      recalculate,replace_manual_price:replace,confirm_currency_change:confirmCurrency,input_origin:"UI",apply:false};
  }
  async function preview(payload: BulkWrite) {
    setBusy(true);setError(null);invalidate();
    try { const next=await matrixApi.bulk(apiUrl,tenderId,payload); if(mounted.current) {setResult(next);setPending({...payload,operation_id:next.operation_id});} }
    catch {if(mounted.current) setError("No se pudo previsualizar. Revisa los campos y actualiza las filas antes de continuar.");}
    finally {if(mounted.current) setBusy(false);}
  }
  async function apply() {
    if(!pending) return;
    if((pending.replace_manual_price || pending.confirm_currency_change) && !window.confirm("¿Aplicar el reemplazo de precios manuales o la redenominación de moneda solicitados? Los números no se convierten por tipo de cambio; se conservará auditoría.")) return;
    setBusy(true);setError(null);
    try {
      const next=await matrixApi.bulk(apiUrl,tenderId,{...pending,apply:true});
      if(mounted.current) {setResult(next);setPending(null);setDrafts(prev => Object.fromEntries(Object.entries(prev).filter(([id]) => !next.outcomes.some(o => o.scope_id === id && (o.outcome === "UPDATED" || o.reasons.includes("UNCHANGED"))))));}
      const refreshed=await matrixApi.read(apiUrl,tenderId);if(mounted.current) setData(refreshed);
    } catch {if(mounted.current) {setPending(null);setError("No se pudo completar o actualizar el lote. Consulta el estado antes de repetir: no se sobrescriben revisiones nuevas con expectativas anteriores.");}}
    finally {if(mounted.current) setBusy(false);}
  }
  function previewChosen() {
    const changes = action === "MARKUP" ? {markup_percent:percent || null} : action === "MARGIN" ? {target_margin_percent:percent || null} : action === "PATCH" ? {[patchField]:patchValue || null} : {};
    void preview(request(chosen,action,changes));
  }
  const editControl = (set: () => void) => {set();invalidate();};
  return <section aria-label="Matriz comercial provisional">
    <h4>Matriz comercial</h4><button disabled={busy} onClick={() => void load()}>{opened ? "Actualizar matriz":"Abrir matriz comercial"}</button>
    {error && <p role="alert">{error}</p>}
    {opened && data && <>
      {data.commercial_readiness && <div aria-label="Completitud comercial"><p>{data.commercial_readiness.status}: {data.commercial_readiness.ready_count} READY · {data.commercial_readiness.incomplete_count} INCOMPLETE · {data.commercial_readiness.review_required_count} REVIEW_REQUIRED</p>
        <p>{data.commercial_readiness.total_scope_items} Scope · {data.commercial_readiness.warning_count} advertencias comerciales · {data.commercial_readiness.missing_commercial_treatment_count} sin tratamiento comercial. Una advertencia comercial por sí sola no impide usar un precio decidido.</p></div>}
      <CommercialSpreadsheet apiUrl={apiUrl} tenderId={tenderId} disabled={busy || Object.keys(drafts).length > 0} onBusyChange={setBusy}
        onApplied={async () => {const refreshed=await matrixApi.read(apiUrl,tenderId);if(mounted.current) {setData(refreshed);setDrafts({});setSelected(new Set());invalidate();}}}/>
      <p>Datos heredados de Scope/Quantity. Selección y defaults de esta sesión; no se crean líneas al consultar. Tab recorre campos; Enter previsualiza la fila. Los cambios sólo se guardan al aplicar el preview.</p>
      <fieldset disabled={busy}><legend>Filtros y selección</legend>
        <label>Estado <select value={filter} onChange={e => editControl(() => setFilter(e.target.value))}>{["ALL","READY","INCOMPLETE","REVIEW_REQUIRED","MISSING_COST","MISSING_PRICE"].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Filtrar fuente <select value={sourceFilter} onChange={e => editControl(() => setSourceFilter(e.target.value))}><option value="">Todas</option>{costSources.map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Filtrar moneda <select value={currencyFilter} onChange={e => editControl(() => setCurrencyFilter(e.target.value))}><option value="">Todas</option>{["MXN","USD","EUR","UNSPECIFIED"].map(v => <option key={v}>{v}</option>)}</select></label>
        <button onClick={() => editControl(() => setSelected(new Set(visible.map(r => r.scope_id))))}>Seleccionar visibles</button><button onClick={() => editControl(() => setSelected(new Set()))}>Limpiar selección</button>
        <p>Seleccionadas visibles: {chosen.length}. El lote sólo afecta esas filas; las ocultas no se incluyen. Máximo 100 por lote.</p>
      </fieldset>
      <fieldset disabled={busy}><legend>Defaults para líneas nuevas en esta sesión</legend>
        <label>Moneda inicial <select value={defaultCurrency ?? ""} onChange={e => editControl(() => setDefaultCurrency((e.target.value || null) as CommercialInputs["currency"]))}><option value="">Sin moneda</option>{["MXN","USD","EUR"].map(v => <option key={v}>{v}</option>)}</select></label>
        <label>Modo inicial <select value={defaultMode} onChange={e => editControl(() => setDefaultMode(e.target.value as CommercialInputs["calculation_mode"]))}><option>PRICE_FIRST</option><option>COST_FIRST</option></select></label>
        <label>Regla inicial <select value={defaultBasis ?? ""} onChange={e => editControl(() => setDefaultBasis((e.target.value || null) as CommercialInputs["calculation_basis"]))}><option value="">Sin regla</option><option>MARKUP</option><option>MARGIN</option></select></label>
        <label>Porcentaje inicial <input value={defaultPercent} onChange={e => editControl(() => setDefaultPercent(e.target.value))}/></label>
      </fieldset>
      <button disabled={busy || !visible.some(r => drafts[r.scope_id]) || visible.filter(r => drafts[r.scope_id]).length > 100} onClick={() => void preview(request(visible.filter(r => drafts[r.scope_id]),"PATCH",{}))}>Previsualizar ediciones visibles</button>
      <fieldset disabled={busy}><legend>Acción compartida</legend>
        <p>MARKUP y MARGIN establecen COST_FIRST con la regla elegida. El preview muestra los ajustes propuestos; los precios manuales siguen protegidos.</p>
        <label>Acción <select value={action} onChange={e => editControl(() => setAction(e.target.value as BulkAction))}>{["PATCH","MARKUP","MARGIN","RECALCULATE","COPY_SETTINGS","INITIALIZE"].map(v => <option key={v}>{v}</option>)}</select></label>
        {action === "PATCH" && <><label>Campo compartido <select value={patchField} onChange={e => editControl(() => {setPatchField(e.target.value);setPatchValue("");})}>{["cost_source_type","currency","calculation_mode","reference_party_name"].map(v => <option key={v}>{v}</option>)}</select></label>
          <label>Valor compartido {patchField === "reference_party_name" ? <input value={patchValue} onChange={e => editControl(() => setPatchValue(e.target.value))}/> : <select value={patchValue} onChange={e => editControl(() => setPatchValue(e.target.value))}><option value="">Sin definir</option>{(patchField === "currency" ? ["MXN","USD","EUR"]:patchField === "calculation_mode" ? ["COST_FIRST","PRICE_FIRST"]:costSources).map(v => <option key={v}>{v}</option>)}</select>}</label></>}
        {(action === "MARKUP" || action === "MARGIN") && <label>Porcentaje del lote <input value={percent} onChange={e => editControl(() => setPercent(e.target.value))}/></label>}
        {action === "COPY_SETTINGS" && <label>Copiar ajustes desde <select value={copySource} onChange={e => editControl(() => setCopySource(e.target.value))}><option value="">Selecciona fila</option>{data.rows.filter(r => r.initialized).map(r => <option key={r.scope_id} value={r.scope_id}>{r.item_reference ?? r.scope_id}</option>)}</select></label>}
        <label><input type="checkbox" checked={recalculate} onChange={e => editControl(() => setRecalculate(e.target.checked))}/>Recalcular precios compatibles</label>
        <label><input type="checkbox" checked={replace} onChange={e => editControl(() => setReplace(e.target.checked))}/>Reemplazar también precios manuales</label>
        <label><input type="checkbox" checked={confirmCurrency} onChange={e => editControl(() => setConfirmCurrency(e.target.checked))}/>Confirmar cambio de denominación sin FX</label>
        <button disabled={!chosen.length || chosen.length > 100 || (action === "COPY_SETTINGS" && !copySource)} onClick={previewChosen}>Previsualizar lote</button>
      </fieldset>
      {result && <div aria-label="Resultado comercial por fila"><p>{result.applied ? "Lote aplicado":"Vista previa"}: {Object.entries(result.counts).map(([k,v]) => `${k}: ${v}`).join(" · ")}</p>
        <ul>{result.outcomes.map(o => <li key={o.scope_id}>{data.rows.find(r => r.scope_id === o.scope_id)?.item_reference ?? o.scope_id}: {o.outcome} · Precio: {o.price_outcome} · {[...o.reasons,...(o.warnings ?? [])].join(", ")}{o.proposed_inputs && <span> · Fuente: {o.proposed_inputs.cost_source_type} · Parte: {o.proposed_inputs.reference_party_name ?? "Sin definir"} · Costo: {o.proposed_inputs.unit_cost ?? "Sin resolver"} · Moneda: {o.proposed_inputs.currency ?? "Sin moneda"} · Modo: {o.proposed_inputs.calculation_mode} · Regla: {o.proposed_inputs.calculation_basis ?? "Sin regla"} · Markup objetivo: {o.proposed_inputs.markup_percent ?? "Sin definir"}% · Margen objetivo: {o.proposed_inputs.target_margin_percent ?? "Sin definir"}% · Precio propuesto: {o.proposed_inputs.offered_unit_price ?? "Sin resolver"}</span>}</li>)}</ul>
        {pending && <button disabled={busy || !result.outcomes.some(o => o.outcome === "ELIGIBLE")} onClick={() => void apply()}>Aplicar vista previa</button>}
      </div>}
      <div style={{overflowX:"auto"}}><table><caption>Hoja de trabajo comercial por Scope</caption><thead><tr>{["Selección","Alcance, Quantity y fuente","Costo y referencia","Modo y regla","Precio y notas","Cálculos","Estado y avisos"].map(v => <th key={v}>{v}</th>)}</tr></thead>
        <tbody>{visible.map(row => <EditableRow apiUrl={apiUrl} tenderId={tenderId} key={`${row.scope_id}:${row.revision}:${row.source_fingerprint}`} row={row} selected={selected.has(row.scope_id)} disabled={busy}
          toggle={() => editControl(() => setSelected(prev => {const next=new Set(prev);if(next.has(row.scope_id)) next.delete(row.scope_id);else next.add(row.scope_id);return next;}))}
          draft={drafts[row.scope_id] ?? {}} onDraft={fields => setDrafts(prev => ({...prev,[row.scope_id]:fields}))} invalidate={invalidate} preview={(r,fields) => void preview(request([r],"PATCH",fields))}/>)}</tbody></table></div>
      {!visible.length && <p>Sin filas para este filtro.</p>}
      <h5>Resumen por moneda — subtotales calculables</h5>
      {data.summary_by_currency.map(group => <div key={group.currency ?? "none"}><p>{group.currency ?? "Sin moneda"}: {group.line_count} filas · {Object.entries(group.status_counts).map(([k,v]) => `${k}: ${v}`).join(" · ")}</p>
        <p>Costo: {group.total_cost ?? "Sin resolver"} ({group.total_cost_calculable_count} calculables, {group.total_cost_missing_count} faltantes) · Oferta: {group.offered_total ?? "Sin resolver"} ({group.offered_total_calculable_count} calculables, {group.offered_total_missing_count} faltantes) · Utilidad: {group.profit ?? "Sin resolver"} ({group.profit_calculable_count} calculables, {group.profit_missing_count} faltantes)</p>
        <p>Sobre {group.paired_count} pares completos: markup {group.paired_markup_percent ?? "Sin resolver"}% · margen {group.paired_margin_percent ?? "Sin resolver"}%</p></div>)}
      {data.archived_lines.map(line => <p key={line.id}>Línea preservada con Scope retirado: {line.id} · {line.warning} · <a href={`${apiUrl}/tenders/${tenderId}/scopes/${line.scope_id}/commercial-line`}>Consultar auditoría</a></p>)}
    </>}
  </section>;
}
