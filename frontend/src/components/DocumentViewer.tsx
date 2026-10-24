import {useEffect,useRef,useState} from 'react';
import {documentPath,tendersApi,type TenderDocument,type DocumentPage} from '../api/tenders';
import {Button,ErrorState,LoadingState,Notice} from '../ui/primitives';
export function DocumentViewer({apiUrl,tenderId,document:d,onBack,initialPage}:{apiUrl:string;tenderId:string;document:TenderDocument;initialPage?:number;onBack:()=>void}){
 const [pages,setPages]=useState<DocumentPage[]>([]),[page,setPage]=useState<number|null>(null),[pagesError,setPagesError]=useState(false),[pagesLoading,setPagesLoading]=useState(true);
 const [url,setUrl]=useState<string|null>(null),[contentError,setContentError]=useState(false),[contentLoading,setContentLoading]=useState(false);
 const [pageAttempt,setPageAttempt]=useState(0),[contentAttempt,setContentAttempt]=useState(0);
 const generation=useRef(0);const pdf=d.mime_type?.toLowerCase().includes('pdf')||d.original_filename.toLowerCase().endsWith('.pdf');
 useEffect(()=>{const request=++generation.current;setPages([]);setPage(initialPage??null);setPagesError(false);setPagesLoading(true);
  if(d.tender_id!==tenderId){setPagesError(true);setPagesLoading(false);return;}
  void tendersApi.pages(apiUrl,tenderId,d.id).then(result=>{if(generation.current===request){setPages(result);setPage(initialPage??result[0]?.page_number??null);}}).catch(()=>{if(generation.current===request)setPagesError(true);}).finally(()=>{if(generation.current===request)setPagesLoading(false);});
  return()=>{generation.current++;};
 },[apiUrl,tenderId,d.id,d.tender_id,pageAttempt,initialPage]);
 useEffect(()=>{let active=true,created:string|null=null;setUrl(null);setContentError(false);setContentLoading(!!pdf);
  if(pdf&&d.tender_id===tenderId)void tendersApi.content(apiUrl,tenderId,d.id).then(blob=>{if(active){created=URL.createObjectURL(blob);setUrl(created);}}).catch(()=>{if(active)setContentError(true);}).finally(()=>{if(active)setContentLoading(false);});
  return()=>{active=false;if(created)URL.revokeObjectURL(created);};
 },[apiUrl,tenderId,d.id,d.tender_id,pdf,contentAttempt]);
 const selected=pages.find(p=>p.page_number===page);
 if(d.tender_id!==tenderId)return <ErrorState>El documento no pertenece a esta licitación.</ErrorState>;
 return <section className="document-viewer" aria-label="Visor del documento"><div className="viewer-heading"><div><h3>{d.original_filename}</h3><p>Revisión {d.revision_number} · {d.is_current?'Actual':'Versión anterior'}</p></div><Button onClick={onBack}>Volver a lista</Button></div>
 <div className="viewer-actions">{pdf&&<a href={`${documentPath(apiUrl,tenderId,d.id)}/content${page?'#page='+page:''}`} target="_blank" rel="noreferrer">Abrir PDF original local</a>}
 {pages.length>0&&<label>Página de texto<select value={page??''} onChange={e=>setPage(Number(e.target.value))}>{page&&!pages.some(p=>p.page_number===page)&&<option value={page}>Página fuente {page}</option>}{pages.map(p=><option key={p.id} value={p.page_number}>Página {p.page_number}</option>)}</select></label>}
 {pdf&&url&&<Button onClick={()=>setContentAttempt(n=>n+1)}>Reabrir visor</Button>}</div>
 {pdf?<>{contentLoading&&<LoadingState>Cargando PDF original…</LoadingState>}{contentError&&<ErrorState retry={()=>setContentAttempt(n=>n+1)}>No pudimos cargar el PDF de este documento. El registro y el texto disponible se conservan.</ErrorState>}{url&&<iframe key={`${url}:${page}`} src={`${url}${page?'#page='+page:''}`} title={`Original: ${d.original_filename}`} className="product-pdf-viewer"/>}</>:<Notice>Vista previa no disponible para este formato. Puedes consultar sus datos y el texto derivado disponible. No hay un visor Office habilitado.</Notice>}
 <details open={pagesError||!pdf}><summary>Texto derivado por página</summary><p>El texto extraído no sustituye al original. La página del texto puede solicitarse al visor PDF; su navegación y zoom dependen del navegador.</p>
 {pagesLoading?<LoadingState>Cargando páginas…</LoadingState>:pagesError?<ErrorState retry={()=>setPageAttempt(n=>n+1)}>No pudimos cargar las páginas de este documento.</ErrorState>:selected?<><h4>Página {selected.page_number}</h4><pre className="document-text">{selected.text||'Sin texto nativo en esta página.'}</pre>{selected.ocr_results?.map(r=><details key={r.id}><summary>Texto OCR disponible — requiere revisión</summary><pre className="document-text">{r.text}</pre></details>)}</>:<p>No hay texto derivado disponible para esta página. Abrir el documento no ejecuta extracción.</p>}</details>
 <details><summary>Contexto y procedencia</summary><dl><dt>Nombre original</dt><dd>{d.original_filename}</dd><dt>Importado</dt><dd>{new Date(d.imported_at).toLocaleString('es-MX')}</dd><dt>Formato registrado</dt><dd>{d.mime_type||'No identificado'}</dd><dt>Tamaño</dt><dd>{d.file_size_bytes.toLocaleString('es-MX')} bytes</dd><dt>Revisión</dt><dd>{d.revision_number}; {d.is_current?'actual en el registro':'anterior; permanece conservada'}</dd></dl>
 <p>El archivo está registrado localmente. Una referencia pública no es un archivo importado. El contrato del registro no identifica si se obtuvo manualmente o desde Discovery.</p>
 <details><summary>Detalles técnicos</summary><p>Documento: {d.id}</p><p>Revisión de: {d.revision_of_document_id??'Documento inicial o independiente'}</p><p>SHA-256: {d.sha256}</p></details></details>
 </section>;
}
