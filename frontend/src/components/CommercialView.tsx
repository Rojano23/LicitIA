import {useEffect,useState} from 'react';
import {matrixApi} from '../api/commercialMatrix';
import {tendersApi} from '../api/tenders';
import {useRead} from './useRead';
import {CommercialMatrix} from './CommercialMatrix';
import {CommercialLine} from './CommercialLine';
import {commercialLabel as label,money} from '../ui/commercialPresentation';
import {sourceHref} from '../ui/engineeringPresentation';
import './commercialProduct.css';
export function CommercialView({apiUrl,tenderId,initialScope}:{apiUrl:string;tenderId:string;initialScope?:string}){
 const read=useRead(tenderId,()=>matrixApi.read(apiUrl,tenderId));
 const docs=useRead(`${tenderId}:documents`,()=>tendersApi.documents(apiUrl,tenderId));
 const [scope,setScope]=useState<string|null>(initialScope??null),[filter,setFilter]=useState('ALL');
 useEffect(()=>{if(initialScope){setScope(initialScope);setFilter("ALL");}},[initialScope]);
 const row=read.value?.rows.find(r=>r.scope_id===scope);
 return <section className="commercial-product" aria-label="Comercial"><header><h2>Comercial</h2><p>Costos, precios y procedencia. Las decisiones económicas permanecen bajo tu control.</p><button onClick={read.refresh}>Actualizar datos comerciales</button></header>
 {read.loading&&<p role="status">Consultando partidas…</p>}{read.error&&<p role="alert">No se pudo consultar la matriz. Vuelve a consultar.</p>}
 <label>Estado comercial <select value={filter} onChange={e=>setFilter(e.target.value)}>{['ALL','READY','INCOMPLETE','REVIEW_REQUIRED','MISSING_COST','MISSING_PRICE'].map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label>
 {read.value&&<><div className="financial-scroll"><table><caption>Costeo por partida · importes unitarios editables en detalle</caption><thead><tr>{['Partida / descripción','Cantidad heredada','Fuente de costo','Costo unitario','Precio unitario','Estado / acción'].map(v=><th key={v}>{v}</th>)}</tr></thead><tbody>{read.value.rows.filter(r=>filter==='ALL'||(filter==='MISSING_COST'?r.inputs.unit_cost==null:filter==='MISSING_PRICE'?r.inputs.offered_unit_price==null:r.summary.status===filter)).map(r=><tr key={r.scope_id} aria-selected={r.scope_id===scope}><td>{r.item_reference??'Sin referencia'}<p>{r.description}</p></td><td>{r.source.quantities.filter(q=>q.id===r.source.selected_quantity_id).map(q=><span key={q.id}>{q.quantity_raw} {q.unit_raw}</span>)}{!r.source.selected_quantity_id&&'Sin cantidad seleccionada'}</td><td>{label(r.inputs.cost_source_type)}<small>{r.inputs.reference_party_name??'Sin parte de referencia'}</small></td><td className="numeric">{money(r.inputs.unit_cost,r.inputs.currency)}</td><td className="numeric">{money(r.inputs.offered_unit_price,r.inputs.currency)}{r.manual_price_protected&&<small>Valor ajustado manualmente</small>}</td><td>{label(r.summary.status)}<button onClick={()=>setScope(r.scope_id)}>Detalle {r.item_reference??r.description}</button></td></tr>)}</tbody></table></div>
 {!read.value.rows.length&&<p>Aún no hay partidas listas para costeo.</p>}
 <details><summary>Subtotales calculables por moneda</summary>{read.value.summary_by_currency.map(g=><p key={g.currency??'none'}>{g.currency??'Sin moneda'} · {g.line_count} filas · Costo {money(g.total_cost,g.currency)} · Oferta {money(g.offered_total,g.currency)} · Utilidad {money(g.profit,g.currency)}. Oferta: {g.offered_total_calculable_count} calculables, {g.offered_total_missing_count} faltantes.</p>)}<p>Las monedas se mantienen separadas. No hay conversión de divisas.</p></details></>}
 {row&&<aside className="commercial-detail" aria-label="Detalle comercial"><h3>{row.item_reference??'Partida'} · {row.description}</h3><button onClick={()=>setScope(null)}>Cerrar detalle comercial</button><p>Fuente del costo: {label(row.inputs.cost_source_type)} · Origen: {label(row.inputs.cost_value_origin)} · Captura: {label(row.inputs.input_origin)}</p><p>{row.inputs.reference_party_name??'Sin proveedor o parte de referencia'}. {row.inputs.quote_reference??'Sin referencia de cotización'}. {row.inputs.quote_document_id?'Documento de cotización vinculado':'Sin documento de cotización vinculado'}.</p>
 {row.inputs.quote_document_id&&<a href={sourceHref(tenderId,row.inputs.quote_document_id)}>Ver documento de cotización</a>}
 <p>Calculado por el servidor: costo total {money(row.summary.total_cost,row.inputs.currency)} · oferta {money(row.summary.offered_total,row.inputs.currency)} · utilidad {money(row.summary.profit,row.inputs.currency)}</p><p>Markup efectivo: {row.summary.actual_markup_percent??'Sin resolver'}% · Margen efectivo: {row.summary.actual_margin_percent??'Sin resolver'}%. Son conceptos distintos.</p>
 {docs.error&&<p role="alert">No se pudo consultar el catálogo documental. Actualízalo antes de cambiar el documento de cotización.<button onClick={docs.refresh}>Consultar documentos</button></p>}
 <CommercialLine key={`${tenderId}:${row.scope_id}`} apiUrl={apiUrl} tenderId={tenderId} scopeDetailId={row.scope_id} documents={docs.value??[]} onSaved={read.refresh} product/>
 <details><summary>Diagnóstico de estado y avisos</summary><pre>{JSON.stringify({warnings:row.summary.warnings,revision:row.revision},null,2)}</pre></details></aside>}
 <details className="commercial-tools"><summary>Edición en lote e intercambio Excel / CSV</summary><p>La vista de trabajo conserva borradores, vista previa y confirmación de cada operación. Actualiza la tabla principal después de aplicar cambios.</p><CommercialMatrix apiUrl={apiUrl} tenderId={tenderId}/></details>
 </section>;
}
