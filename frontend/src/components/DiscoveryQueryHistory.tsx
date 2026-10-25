import {discoveryApi} from '../api/discovery';
import {displayDate,sourceName,scanLabels} from '../ui/discoveryPresentation';
import {Button,ErrorState,LoadingState,TableShell} from '../ui/primitives';
import {useRead} from './useRead';
export function DiscoveryQueryHistory({apiUrl}:{apiUrl:string}){
 const read=useRead(`discovery-query-history:${apiUrl}`,()=>discoveryApi.scans(apiUrl));
 return <section aria-label="Historial de consultas Discovery"><h3>Historial de consultas Discovery</h3><p>Hasta 20 consultas recientes. Esta lectura no consulta portales públicos.</p><Button disabled={read.loading} onClick={read.refresh}>Actualizar consultas Discovery</Button>{read.loading&&<LoadingState/>}{read.error&&<ErrorState retry={read.refresh}>No se pudo consultar el historial de Discovery.</ErrorState>}
 {read.value&&<TableShell label="Consultas Discovery" empty={!read.value.length}><table><thead><tr>{['Fecha','Fuente','Periodo solicitado','Resultado','Oportunidades','Filas','Lotes completados / intentados'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{read.value.slice(0,20).map(s=><tr key={s.id}><td>{displayDate(s.started_at)} {new Date(s.started_at).toString()!=='Invalid Date'?new Intl.DateTimeFormat('es-MX',{timeStyle:'short'}).format(new Date(s.started_at)):''}</td><td>{sourceName(s.source_id??'')}</td><td>{s.query?.published_from?displayDate(s.query.published_from):'Sin inicio'} — {s.query?.published_to?displayDate(s.query.published_to):'Sin fin'}</td><td>{scanLabels[s.status]??'Estado por revisar'}{s.status==='PARTIAL'&&<p>Cobertura incompleta</p>}{s.status==='FAILED'&&<p>La consulta no se completó</p>}{!!s.metrics.diagnostics?.length&&<p>{s.metrics.diagnostics.length} incidencias registradas</p>}</td><td>{s.metrics.unique_opportunities??'No disponible'}</td><td>{s.metrics.rows_retrieved??'No disponible'}</td><td>{s.metrics.pages_completed??'No disponible'} / {s.metrics.pages_attempted??'No disponible'}</td></tr>)}</tbody></table></TableShell>}
 </section>;
}
