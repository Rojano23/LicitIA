import axios from 'axios';
import { useEffect, useRef, useState } from 'react';
import { discoveryApi, monitoringApi, type Counters, type Page, type Scan } from '../api/discovery';
import { Button, EmptyState, ErrorState, LoadingState, StatusBadge, TableShell } from '../ui/primitives';
import { displayDate, scanLabels, sourceName } from '../ui/discoveryPresentation';
import { tenderHref } from '../ui/routes';
import './discovery.css';
export type RecentTender={id:string;title:string;external_reference:string|null;institution_profile:string|null;status:string;updated_at:string};
export function InicioView({apiUrl}:{apiUrl:string}) {
 const [summary,setSummary]=useState<Counters|null>(null),[following,setFollowing]=useState<Page|null>(null),[scans,setScans]=useState<Scan[]|null>(null),[tenders,setTenders]=useState<RecentTender[]|null>(null);
 const [loading,setLoading]=useState(true),[failed,setFailed]=useState<string[]>([]);
 const generation=useRef(0);
 async function load(){const request=++generation.current;setLoading(true);setFailed([]);
  const results=await Promise.allSettled([monitoringApi.summary(apiUrl),discoveryApi.list(apiUrl,{following:true,unread_only:true,limit:5,offset:0}),discoveryApi.scans(apiUrl,undefined),axios.get<RecentTender[]>(`${apiUrl}/tenders`).then(r=>r.data)]);
  if(request!==generation.current)return;
  const names=['resumen de oportunidades','oportunidades en seguimiento','consultas recientes','licitaciones'];
  setFailed(results.flatMap((r,i)=>r.status==='rejected'?[names[i]]:[]));
  setSummary(results[0].status==='fulfilled'?results[0].value:null);setFollowing(results[1].status==='fulfilled'?results[1].value:null);
  setScans(results[2].status==='fulfilled'?results[2].value:null);setTenders(results[3].status==='fulfilled'?results[3].value:null);setLoading(false);
 }
 useEffect(()=>{void load();return()=>{generation.current++;};},[apiUrl]);
 const scanIssues=scans?.filter(s=>s.status==='PARTIAL'||s.status==='FAILED').slice(0,3)??[];
 const empty=summary?.new_opportunities===0&&summary.followed_with_changes===0&&tenders?.length===0&&following?.items.length===0&&scanIssues.length===0&&!failed.length;
 return <div className="inicio-product">
  <div className="product-toolbar"><p>Oportunidades, cambios y expedientes por revisar.</p><Button onClick={()=>void load()} disabled={loading}>Actualizar vista</Button></div>
  {loading&&<LoadingState/>}{failed.length>0&&<ErrorState retry={()=>void load()}>No se pudo consultar: {failed.join(', ')}. Las demás secciones permanecen disponibles.</ErrorState>}
  {!loading&&empty?<EmptyState title="Aún no hay licitaciones." action={<div className="product-actions"><a className="ui-button ui-button--primary" href="#/licitaciones">Crear licitación</a><a className="ui-button" href="#/discovery">Ir a Discovery</a></div>}>Crea un expediente o consulta oportunidades públicas para comenzar.</EmptyState>:<>
   {summary&&<section aria-label="Indicadores de Discovery" className="metric-strip">
    <a className="metric-link" href="#/discovery?view=new"><span>Oportunidades nuevas</span><strong>{summary.new_opportunities}</strong><small>Guardadas con estado Nueva</small></a>
    <a className="metric-link" href="#/discovery?view=following-changes"><span>Siguiendo con cambios</span><strong>{summary.followed_with_changes}</strong><small>Con cambios de fuente sin leer</small></a>
   </section>}
   <section className="inicio-attention" aria-label="Requiere atención"><h2>Requiere atención</h2>
    <h3>Oportunidades que sigues</h3>
    {following?.items.length===0&&<p>Sin cambios pendientes en las oportunidades que sigues.</p>}
    <ul className="attention-list attention-list--opportunities">{following?.items.map(row=><li key={row.id}><div><strong>{row.title}</strong><p>{sourceName(row.source_id)} · {row.procedure_number??row.external_id} · {row.unread_changes??0} cambios sin leer{row.unread_document_changes?` · ${row.unread_document_changes} documentales`:''}</p></div><a href={`#/discovery?view=following-changes&opportunity=${encodeURIComponent(row.id)}`}>Revisar cambios</a></li>)}</ul>
    {(following?.total??0)>5&&<a href="#/discovery?view=following-changes">Ver todas las oportunidades con cambios</a>}
    <h3>Consultas que requieren revisión</h3><p className="ui-secondary">Hasta tres consultas parciales o fallidas entre las veinte más recientes; no indica el estado actual completo de la fuente.</p>
    {scans&&scanIssues.length===0&&<p>Sin consultas parciales o fallidas en este conjunto reciente.</p>}
    <ul className="attention-list attention-list--scans">{scanIssues.map(scan=><li key={scan.id}><div><strong>{sourceName(scan.source_id??'Fuente')} · {scanLabels[scan.status]}</strong><p>{displayDate(scan.started_at)} · Los resultados guardados se conservan.</p></div><a href="#/configuracion/diagnostico">Revisar consulta</a></li>)}</ul>
   </section>
   <section className="inicio-recent"><h2>Licitaciones recientes</h2>{tenders&&<TableShell label="Licitaciones recientes" empty={!tenders.length}><table><thead><tr><th scope="col">Referencia / Licitación</th><th scope="col">Perfil institucional</th><th scope="col">Estado</th><th scope="col">Registro actualizado</th><th scope="col">Acción</th></tr></thead><tbody>{[...tenders].sort((a,b)=>b.updated_at.localeCompare(a.updated_at)||a.id.localeCompare(b.id)).slice(0,5).map(t=><tr key={t.id}><td><strong>{t.external_reference??'Sin referencia'}</strong><br/>{t.title}</td><td>{t.institution_profile??'Sin perfil'}</td><td><StatusBadge>{({DRAFT:'Borrador',ACTIVE:'Activa',ARCHIVED:'Archivada'} as Record<string,string>)[t.status]??'Por revisar'}</StatusBadge></td><td>{displayDate(t.updated_at)}</td><td><a href={tenderHref(t.id)}>Abrir licitación</a></td></tr>)}</tbody></table></TableShell>}<a href="#/licitaciones">Ver licitaciones</a></section>
  </>}
 </div>;
}
