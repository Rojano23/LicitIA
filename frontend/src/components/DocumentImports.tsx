import {useEffect,useRef,useState} from 'react';
import {tendersApi,type TenderDocument,type ImportResult} from '../api/tenders';
import {Button,Notice} from '../ui/primitives';
type Pending={clientImportId:string;file:File;state:'QUEUED'|'BUSY'|'DONE'|'ERROR'|'CANCELLED';result?:ImportResult;target:string;action:string};
const labels:Record<string,string>={IMPORTED:'Importado',DUPLICATE:'Contenido idéntico ya registrado',NAME_CONFLICT:'Mismo nombre, contenido diferente',FAILED:'No se pudo importar'};
export function DocumentImports({apiUrl,tenderId,documents,onImported}:{apiUrl:string;tenderId:string;documents:readonly TenderDocument[];onImported:()=>void}){
 const [items,setItems]=useState<Pending[]>([]);const alive=useRef(true);const locks=useRef(new Set<string>());
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const update=(id:string,patch:Partial<Pending>)=>setItems(old=>old.map(i=>i.clientImportId===id?{...i,...patch}:i));
 async function submit(item:Pending,action='NONE',target?:string){
  if(locks.current.has(item.clientImportId))return;
  if(action==='NEW_REVISION'&&!documents.some(d=>d.id===target&&d.is_current&&d.original_filename===item.file.name&&d.tender_id===tenderId))return;
  locks.current.add(item.clientImportId);update(item.clientImportId,{state:'BUSY'});
  try{const result=await tendersApi.import(apiUrl,tenderId,item.file,action,target);if(alive.current){update(item.clientImportId,{state:'DONE',result,action:'',target:''});onImported();}}
  catch{if(alive.current)update(item.clientImportId,{state:'ERROR'});}
  finally{locks.current.delete(item.clientImportId);}
 }
 useEffect(()=>{const guard=(event:Event)=>{const next=(event as CustomEvent<{tenderId?:string}>).detail.tenderId;
  if(next&&next!==tenderId&&items.some(i=>i.state==='QUEUED'||i.state==='BUSY'||i.state==='ERROR'||i.result?.status==='NAME_CONFLICT'&&i.state!=='CANCELLED')){
   if(items.some(i=>i.state==='BUSY')||!window.confirm('Hay importaciones pendientes. ¿Abandonar este expediente?'))event.preventDefault();
  }};window.addEventListener('tuscope:navigate',guard);return()=>window.removeEventListener('tuscope:navigate',guard);},[items,tenderId]);
 const busy=items.some(i=>i.state==='BUSY');
 useEffect(()=>{const guard=(event:BeforeUnloadEvent)=>{if(items.some(i=>i.state==='QUEUED'||i.state==='BUSY'||i.state==='ERROR'||i.result?.status==='NAME_CONFLICT'&&i.state!=='CANCELLED')){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',guard);return()=>window.removeEventListener('beforeunload',guard);},[items]);
 return <section className="document-imports" aria-label="Importación de documentos"><h3>Importar documentos</h3>
 <p>Los originales se conservan. Importar no ejecuta análisis. Selecciona archivos y confirma su importación.</p>
 <label>Archivos del expediente<input type="file" multiple disabled={busy} onChange={e=>{const incoming=Array.from(e.target.files??[]).map(file=>({clientImportId:crypto.randomUUID(),file,state:'QUEUED' as const,target:'',action:''}));setItems(old=>[...old,...incoming]);e.target.value='';}}/></label>
 {items.some(i=>i.state==='QUEUED')&&<Button disabled={busy} variant="primary" onClick={()=>{void(async()=>{for(const item of items.filter(i=>i.state==='QUEUED'))await submit(item);})();}}>Importar archivos seleccionados</Button>}
 {items.length>0&&<ul className="import-outcomes">{items.map(item=><li key={item.clientImportId} data-import-id={item.clientImportId}><strong>{item.file.name}</strong>
 <p role="status">{item.state==='QUEUED'?'Pendiente de importar':item.state==='BUSY'?'Importando…':item.state==='CANCELLED'?'Cancelado: no se aplicó una decisión':item.state==='ERROR'?'No se pudo confirmar la importación. Actualiza la lista antes de reintentar; puede haberse guardado.':labels[item.result?.status??'']??'Resultado por revisar'}</p>
 {(item.state==='ERROR'||item.result?.status==='FAILED')&&<Button disabled={busy} onClick={()=>void submit(item)}>Reintentar importación</Button>}
 {item.result?.status==='NAME_CONFLICT'&&item.state==='DONE'&&<div className="conflict-decision"><Notice tone="warning">Elige qué hacer con este archivo; no se resuelve automáticamente.</Notice>
 <label>Decisión para {item.file.name}<select value={item.action} onChange={e=>update(item.clientImportId,{action:e.target.value,target:''})}><option value="">Selecciona una decisión</option><option value="IMPORT_INDEPENDENT">Importar como documento independiente</option><option value="NEW_REVISION">Registrar como nueva revisión</option></select></label>
 {item.action==='NEW_REVISION'&&<label>Revisión actual para {item.file.name}<select value={item.target} onChange={e=>update(item.clientImportId,{target:e.target.value})}><option value="">Selecciona el documento actual</option>{documents.filter(d=>d.tender_id===tenderId&&d.is_current&&d.original_filename===item.file.name).map(d=><option key={d.id} value={d.id}>{d.original_filename} · Revisión {d.revision_number} · Actual · importado {new Date(d.imported_at).toLocaleString('es-MX')}</option>)}</select></label>}
 <Button disabled={busy||!item.action||item.action==='NEW_REVISION'&&!item.target} onClick={()=>{if(window.confirm(`Confirmar ${item.action==='NEW_REVISION'?'nueva revisión':'documento independiente'} de ${item.file.name}${item.action==='NEW_REVISION'?' sobre el documento actual seleccionado':''}.`))void submit(item,item.action,item.target);}}>Confirmar decisión</Button>
 <Button disabled={busy} onClick={()=>update(item.clientImportId,{state:'CANCELLED'})}>Cancelar</Button>
 </div>}
 {item.state==='QUEUED'&&<Button disabled={busy} onClick={()=>update(item.clientImportId,{state:'CANCELLED'})}>Cancelar</Button>}
 </li>)}</ul>}
 </section>;
}
