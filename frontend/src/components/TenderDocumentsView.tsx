import {useEffect,useRef,useState} from 'react';
import {extractionStatus,type TenderDocument} from '../api/tenders';
import {Button,EmptyState,ErrorState,LoadingState,StatusBadge,TableShell} from '../ui/primitives';
import {DocumentViewer} from './DocumentViewer';
import {DocumentImports} from './DocumentImports';
import {WorkspaceFlow} from './WorkspaceFlow';
export function TenderDocumentsView({apiUrl,tenderId,documents,loading,error,refresh,active:isActive=true,requestedDocument,requestedPage}:{requestedDocument?:string;requestedPage?:number;active?:boolean;apiUrl:string;tenderId:string;documents:TenderDocument[];loading:boolean;error:boolean;refresh:()=>void}){
 const [selected,setSelected]=useState<string|null>(null),[search,setSearch]=useState(''),[revisions,setRevisions]=useState('all'),[importOpen,setImportOpen]=useState(false);
 const list=useRef<HTMLDivElement>(null);const previous=useRef<HTMLButtonElement|null>(null);
 const rows=documents.filter(d=>d.original_filename.toLocaleLowerCase('es-MX').includes(search.toLocaleLowerCase('es-MX'))&&(revisions==='all'||d.is_current===(revisions==='current')));
 useEffect(()=>{if(requestedDocument)setSelected(requestedDocument);},[requestedDocument,requestedPage]);
 const active=documents.find(d=>d.id===selected);
 const back=()=>{setSelected(null);requestAnimationFrame(()=>previous.current?.focus());};
 return <div className="tender-documents"><div className="product-toolbar"><p>Originales y revisiones registrados en este expediente.</p><div className="product-actions"><Button variant="primary" onClick={()=>setImportOpen(v=>!v)}>Importar documentos</Button><Button disabled={loading} onClick={refresh}>Actualizar lista</Button></div></div>
 <div hidden={!importOpen}><DocumentImports key={tenderId} apiUrl={apiUrl} tenderId={tenderId} documents={documents} onImported={refresh}/></div>
 {loading&&<LoadingState>Consultando documentos…</LoadingState>}{error&&<ErrorState retry={refresh}>No pudimos consultar los documentos. La lista puede estar desactualizada.</ErrorState>}
 <div className="documents-workbench" data-viewing={!!active}>
 <div className="document-registry" ref={list}><h2>Documentos del expediente</h2><div className="document-filters"><label>Buscar documento<input value={search} onChange={e=>setSearch(e.target.value)}/></label><label>Revisiones<select value={revisions} onChange={e=>setRevisions(e.target.value)}><option value="all">Todas las revisiones</option><option value="current">Actuales</option><option value="previous">Anteriores</option></select></label></div>
 {!loading&&!error&&documents.length===0?<EmptyState title="Sin documentos importados">Importa los originales para iniciar el expediente.</EmptyState>:<TableShell label="Registro documental"><table><thead><tr><th>Archivo</th><th>Revisión</th><th>Texto / páginas</th><th>Acción</th></tr></thead><tbody>{rows.map(d=><tr key={d.id} data-selected={d.id===selected}><td>{d.original_filename}</td><td>{d.revision_number} · <StatusBadge tone={d.is_current?'info':'neutral'}>{d.is_current?'Actual':'Versión anterior'}</StatusBadge></td><td>{extractionStatus(d.processing_status)}{(d.page_count??0)>0?` · ${d.page_count} páginas registradas`:''}</td><td><Button onClick={e=>{previous.current=e.currentTarget;setSelected(d.id);}}>Ver documento</Button></td></tr>)}</tbody></table>{!rows.length&&documents.length>0&&<p>Sin coincidencias en estos filtros.</p>}</TableShell>}
 </div>
 {requestedDocument&&!loading&&!error&&!documents.some(d=>d.id===requestedDocument)&&<ErrorState>El documento fuente solicitado no está disponible en este expediente. No se sustituyó por otra revisión.</ErrorState>}
 {active&&<DocumentViewer key={`${tenderId}:${active.id}`} apiUrl={apiUrl} tenderId={tenderId} document={active} initialPage={active.id===requestedDocument?requestedPage:undefined} onBack={back}/>}
 </div>
 <details className="processing-disclosure"><summary>Procesamiento y recuperación del expediente</summary><WorkspaceFlow key={tenderId} apiUrl={apiUrl} tenderId={tenderId} documents={documents} processingOnly active={isActive}/></details>
 <details><summary>Herramientas documentales existentes</summary><p>Extracción, clasificación, referencias y controles explícitos de OCR/análisis visual permanecen disponibles en Diagnóstico. Regenerar páginas puede cambiar derivados; no equivale a un reintento seguro.</p><a href="#/configuracion/diagnostico">Abrir Diagnóstico</a></details>
 </div>;
}
