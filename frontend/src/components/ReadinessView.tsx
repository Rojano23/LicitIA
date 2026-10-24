import {useState} from 'react';
import {boardApi,buckets,type BoardRead} from '../api/readinessBoard';
import {useRead} from './useRead';
import {WorkRow} from './ReadinessWork';
import {ProposalReadiness} from './ProposalReadiness';
import {areaSection,commercialLabel as label} from '../ui/commercialPresentation';
import './commercialProduct.css';
export function ReadinessView({apiUrl,tenderId}:{apiUrl:string;tenderId:string}){
 const [offset,setOffset]=useState(0),[bucket,setBucket]=useState(''),[selected,setSelected]=useState<string|null>(null);
 const read=useRead<BoardRead>(`${tenderId}:${offset}:${bucket}`,()=>boardApi.read(apiUrl,tenderId,{search:'',include_inactive:false,offset,limit:50,bucket:(bucket||undefined) as typeof buckets[number]|undefined}));
 const row=read.value?.items.find(i=>i.work.id===selected);
 return <section className="readiness-product" aria-label="Preparación"><h2>Preparación</h2><p>Estado de los registros según la última consulta local. Cerrar una actividad no completa datos faltantes ni certifica cumplimiento.</p><button onClick={read.refresh}>Actualizar preparación actual</button>
 {read.loading&&<p role="status">Consultando estado actual…</p>}{read.error&&<p role="alert">No se pudo consultar preparación. Vuelve a consultar; no se afirma un estado listo.</p>}
 {read.value&&<><h3>{label(read.value.canonical_summary.status)}</h3><p>Bloqueos y faltantes: {read.value.canonical_summary.blocker_count} · Revisiones pendientes: {read.value.canonical_summary.review_required_count} · Advertencias: {read.value.canonical_summary.warning_count}</p>
 <details><summary>Áreas evaluadas por el motor</summary><table><thead><tr><th>Área</th><th>Estado actual</th><th>Bloqueos</th><th>Revisiones</th><th>Advertencias</th></tr></thead><tbody>{read.value.dimensions.map(d=><tr key={d.dimension}><td>{label(d.dimension)}</td><td>{label(d.status)}</td><td>{d.blocker_count}</td><td>{d.review_count}</td><td>{d.warning_count}</td></tr>)}</tbody></table></details>
 <label>Grupo de atención <select value={bucket} onChange={e=>{setBucket(e.target.value);setOffset(0);setSelected(null);}}><option value="">Todos, bloqueos primero</option>{buckets.map(b=><option key={b} value={b}>{label(b)}</option>)}</select></label>
 <div className="financial-scroll"><table><caption>Trabajo por resolver · prioridad canónica</caption><thead><tr><th>Atención</th><th>Área / motivo</th><th>Actividad humana</th><th>Acción</th></tr></thead><tbody>{read.value.items.map(i=><tr key={i.work.id}><td>{label(i.bucket)}<p>{label(i.work.issue?.severity)}</p></td><td>{label(i.work.dimension)}<p>{i.work.issue?.summary??'Registro histórico'}</p></td><td>{label(i.work.workflow_status)}</td><td><a href={`#/licitaciones/${encodeURIComponent(tenderId)}/${areaSection(i.work.dimension)}${i.work.dimension==='COMMERCIAL'&&i.work.entity_type==='SCOPE'?'?scope='+encodeURIComponent(i.work.entity_id):''}`}>Ir a {label(i.work.dimension)}</a><button onClick={()=>setSelected(i.work.id)}>Ver detalle de atención</button></td></tr>)}</tbody></table></div>
 {!read.value.items.length&&<p>Sin resultados en este grupo. El estado actual es el indicado por el motor.</p>}
 <p>{read.value.total_filtered} resultados · hasta 50 por página. Orden: bloqueos, revisión, incompletos y advertencias.</p><button disabled={offset===0||read.loading} onClick={()=>{setOffset(Math.max(0,offset-50));setSelected(null);}}>Página anterior de preparación</button><button disabled={offset+read.value.items.length>=read.value.total_filtered||read.loading} onClick={()=>{setOffset(offset+50);setSelected(null);}}>Página siguiente de preparación</button>
 {row&&<aside aria-label="Detalle de preparación"><h3>{row.work.issue?.summary??'Seguimiento humano'}</h3><button onClick={()=>setSelected(null)}>Cerrar detalle de preparación</button><WorkRow key={`${tenderId}:${row.work.id}:${row.work.revision}:${row.work.context_sha256}`} item={row.work} apiUrl={apiUrl} tenderId={tenderId} disabled={false} onSaved={async()=>read.refresh()} product/></aside>}</>}
 <details><summary>Capturar estado para una propuesta · snapshots e historial</summary><p>Una captura conserva el estado histórico. Es distinta de la preparación actual mostrada arriba.</p><ProposalReadiness key={tenderId} apiUrl={apiUrl} tenderId={tenderId} disabled={false} product/></details>
 </section>;
}
