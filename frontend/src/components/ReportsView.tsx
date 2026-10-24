import {useState} from 'react';
import {tendersApi,tenderStatus} from '../api/tenders';
import {useRead} from './useRead';
import {Button,ErrorState,LoadingState,TableShell} from '../ui/primitives';
import {tenderHref} from '../ui/routes';
import './supportProduct.css';
export function ReportsView({apiUrl,embedded=false}:{apiUrl:string;embedded?:boolean}){
 const tenders=useRead('report-tenders',()=>tendersApi.list(apiUrl));
 const [selected,setSelected]=useState(''),[status,setStatus]=useState(''),[search,setSearch]=useState('');
 const rows=tenders.value?.filter(t=>(!status||t.status===status)&&(!search||(t.title+' '+(t.external_reference??'')).toLocaleLowerCase('es-MX').includes(search.toLocaleLowerCase('es-MX'))));
 const valid=tenders.value?.some(t=>t.id===selected);
 return <section className="support-product" aria-label="Reportes">{!embedded&&<h2>Reportes</h2>}<p>Consultas y archivos disponibles en los flujos existentes. Sin consolidación económica entre monedas o licitaciones.</p><TableShell label="Catálogo de consultas"><table><thead><tr><th>Consulta / archivo</th><th>Propósito y alcance</th><th>Acción</th></tr></thead><tbody>
 <tr><td>Registro de licitaciones</td><td>Datos del registro local; no evalúa preparación.</td><td><Button onClick={()=>document.getElementById("report-tenders")?.scrollIntoView()}>Consultar registro abajo</Button></td></tr>
 <tr><td>Comercial · Excel / CSV</td><td>Intercambio comercial por licitación, con preview al importar.</td><td>{valid?<a href={tenderHref(selected,'comercial')}>Abrir intercambio comercial</a>:'Elige licitación'}</td></tr>
 <tr><td>Preparación y bloqueos</td><td>Pendientes de cada licitación y capturas históricas de preparación.</td><td>{valid?<a href={tenderHref(selected,'preparacion')}>Consultar preparación</a>:'Elige licitación'}</td></tr>
 <tr><td>Versiones y archivos de propuesta</td><td>DOCX / XLSX / PDF / ZIP efectivamente generados; generación explícita.</td><td>{valid?<a href={tenderHref(selected,'propuesta')}>Consultar archivos de propuesta</a>:'Elige licitación'}</td></tr>
 <tr><td>Oportunidades seguidas</td><td>Listado local Discovery, filtros y cambios registrados.</td><td><a href="#/discovery?view=following">Consultar seguimiento</a></td></tr>
 </tbody></table></TableShell><label>Licitación para consultas<select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Selecciona licitación</option>{tenders.value?.map(t=><option key={t.id} value={t.id}>{t.external_reference||t.title}</option>)}</select></label>
 <h3 id="report-tenders">Registro local de licitaciones</h3><div className="support-filters"><label>Buscar referencia o nombre<input value={search} onChange={e=>setSearch(e.target.value)}/></label><label>Estado del registro<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">Todos</option>{['DRAFT','ACTIVE','ARCHIVED'].map(v=><option key={v} value={v}>{tenderStatus(v)}</option>)}</select></label><Button onClick={tenders.refresh}>Actualizar registro de reportes</Button></div>
 {tenders.loading&&<LoadingState/>}{tenders.error&&<ErrorState retry={tenders.refresh}>No se pudo consultar el registro; no se interpreta como ausencia de licitaciones.</ErrorState>}
 {rows&&<><p>{rows.length} de {tenders.value?.length} registros locales</p><TableShell label="Registro consultado"><table><thead><tr><th>Referencia / licitación</th><th>Estado</th><th>Actualización del registro</th><th>Acción</th></tr></thead><tbody>{rows.map(t=><tr key={t.id}><td>{t.external_reference||'Sin referencia'}<p>{t.title}</p></td><td>{tenderStatus(t.status)}</td><td>{t.updated_at}</td><td><a href={tenderHref(t.id)}>Abrir licitación</a></td></tr>)}</tbody></table></TableShell>{!rows.length&&<p>No hay registros para esta consulta.</p>}</>}
 <details><summary>Alcance del catálogo</summary><p>No hay reportes globales de cumplimiento, tendencias o rentabilidad contratados. Requisitos y evidencia se revisan en cada licitación. Los archivos se consultan/generan en sus módulos; abrir este catálogo no los genera.</p></details>
 </section>;
}
