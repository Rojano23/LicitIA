import {commercialLabel as label} from "../ui/commercialPresentation";
import { useEffect, useRef, useState } from "react";
import { exchangeApi, type ImportPreview, type ImportApplied } from "../api/commercialExchange";

type Props = {apiUrl: string; tenderId: string; disabled: boolean; onBusyChange: (value: boolean) => void; onApplied: () => Promise<void>};
export function CommercialSpreadsheet({apiUrl,tenderId,disabled,onBusyChange,onApplied}: Props) {
  const [file,setFile]=useState<File | null>(null), [preview,setPreview]=useState<ImportPreview | null>(null);
  const [result,setResult]=useState<ImportApplied | null>(null), [error,setError]=useState<string | null>(null);
  const [replace,setReplace]=useState(false), [currency,setCurrency]=useState(false), [busy,setBusy]=useState(false);
  const mounted=useRef(true);
  useEffect(() => {mounted.current=true;return () => {mounted.current=false;};},[]);
  function state(value: boolean) {setBusy(value);onBusyChange(value);}
  function clear() {setPreview(null);setResult(null);setError(null);}
  async function download(kind: "xlsx" | "csv") {
    state(true);setError(null);
    try {
      const blob=await exchangeApi.export(apiUrl,tenderId,kind);
      if(mounted.current) {const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=`tuscope-commercial.${kind}`;link.click();URL.revokeObjectURL(url);}
    } catch {if(mounted.current) setError("No se pudo exportar. Revisa los límites y la disponibilidad del almacenamiento local.");}
    finally {if(mounted.current) state(false);}
  }
  async function inspect() {
    if(!file) return;
    clear();
    if(file.size>5*1024*1024 || !/\.(xlsx|csv)$/i.test(file.name)) {setError("Usa un archivo RX23 TuScope XLSX o CSV UTF-8 de máximo 5 MiB.");return;}
    state(true);
    try {const next=await exchangeApi.stage(apiUrl,tenderId,file,replace,currency);if(mounted.current) setPreview(next);}
    catch {if(mounted.current) setError("No se pudo validar el archivo. Usa un archivo generado por RX23 TuScope, conserva sus columnas y datos de referencia y pega valores en lugar de fórmulas. El archivo no se aplicó.");}
    finally {if(mounted.current) state(false);}
  }
  async function apply() {
    if(!preview || !window.confirm("¿Aplicar únicamente los cambios comerciales elegibles de la vista previa? La evidencia documental permanecerá intacta; se conservará auditoría.")) return;
    state(true);setError(null);
    try {
      const next=await exchangeApi.apply(apiUrl,tenderId,preview.stage_id);
      if(mounted.current) {setResult(next);setPreview(null);}
      await onApplied();
    } catch {if(mounted.current) {setPreview(null);setError("No se pudo completar o actualizar la importación. Consulta la matriz antes de repetir; conflictos nuevos no se sobrescriben automáticamente.");}}
    finally {if(mounted.current) state(false);}
  }
  return <section aria-label="Round trip comercial XLSX CSV">
    <h5>Trabajar en Excel o CSV</h5>
    <p>Exporta los datos guardados, edita los campos comerciales y reimporta para revisar diferencias. Las partidas, cantidades y fuentes son referencias de sólo lectura. Aplica o descarta borradores de la matriz antes de usar este flujo.</p>
    <p>Local y confidencial: protege el archivo descargado. XLSX es el formato principal; CSV UTF-8 usa coma y dos registros iniciales de datos de referencia y encabezados. No los ordenes con los datos. Hasta 1000 filas / 5 MiB, contexto válido 7 días; sin macros ni fórmulas editables.</p>
    <fieldset disabled={disabled || busy}><legend>Archivo comercial</legend>
      <button onClick={() => void download("xlsx")}>Exportar XLSX</button><button onClick={() => void download("csv")}>Exportar CSV</button>
      <label>Importar archivo comercial <input type="file" accept=".xlsx,.csv" onChange={e => {setFile(e.target.files?.[0] ?? null);clear();}}/></label>
      <label><input type="checkbox" checked={replace} onChange={e => {setReplace(e.target.checked);clear();}}/>Permitir recalcular precios manuales protegidos</label>
      <label><input type="checkbox" checked={currency} onChange={e => {setCurrency(e.target.checked);clear();}}/>Confirmar cambio de moneda sin conversión de divisas</label>
      <button disabled={!file} onClick={() => void inspect()}>Previsualizar importación</button>
    </fieldset>
    {error && <p role="alert">{error}</p>}
    {preview && <div aria-label="Preview de importación">
      <p>{label(preview.origin)}: {Object.entries(preview.counts).map(([key,value]) => `${label(key)}: ${value}`).join(" · ")}</p>
      <p>Archivo: {preview.file_evidence.file_name} · SHA-256: {preview.file_evidence.sha256}</p>
      {preview.rows.map((row,index) => <article key={`${row.scope_id}:${index}`}>
        <p>{row.item_reference || row.scope_id || `Fila ${row.import_row}`}: {label(row.state)} · {label(row.price_outcome)}</p>
        {[...row.errors,...row.warnings,...(row.invalid_fields ?? [])].map((message,i) => <p key={`${label(message)}:${i}`}>{label(message)}</p>)}
        {row.diff.length>0 && <table><caption>Diferencias comerciales {row.item_reference || row.scope_id}</caption><thead><tr><th>Campo</th><th>Actual</th><th>Importado</th><th>Propuesto por el sistema</th></tr></thead>
          <tbody>{row.diff.map(change => <tr key={label(change.field)}><td>{label(change.field)}</td><td>{change.current ?? "Sin resolver"}</td><td>{change.imported ?? "Sin resolver"}</td><td>{change.proposed ?? "Sin resolver"}</td></tr>)}</tbody></table>}
        {row.reference_diff?.map(change => <p key={label(change.field)}>Referencia alterada {label(change.field)}: {change.current} → {change.imported}. No se aplicará.</p>)}
      </article>)}
      <button disabled={disabled || busy || !preview.rows.some(row => row.eligible)} onClick={() => void apply()}>Aplicar cambios comerciales validados</button>
    </div>}
    {result && <div aria-label="Resultado de importación"><p>Importación aplicada: {Object.entries(result.counts).map(([k,v]) => `${label(k)}: ${v}`).join(" · ")}</p>
      {result.outcomes.map(row => <p key={row.scope_id}>{row.scope_id}: {label(row.outcome)} · {[...row.reasons,...(row.warnings ?? [])].map(label).join(", ")}</p>)}
    </div>}
  </section>;
}
