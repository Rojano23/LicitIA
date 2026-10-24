import {useState} from 'react';
import {readDiagnostics,diagnosticSummary} from '../api/diagnostics';
import {useRead} from './useRead';
import {Button,ErrorState,LoadingState,Notice} from '../ui/primitives';
import './supportProduct.css';
export function DiagnosticsView({apiUrl,onOpenTools,toolsOpened=false,embedded=false}:{apiUrl:string;onOpenTools:()=>void;toolsOpened?:boolean;embedded?:boolean}){
 const read=useRead('local-diagnostics',()=>readDiagnostics(apiUrl));const [copy,setCopy]=useState<'idle'|'done'|'error'>('idle');
 async function copySummary(){if(!read.value)return;try{await navigator.clipboard.writeText(diagnosticSummary(read.value));setCopy('done');}catch{setCopy('error');}}
 return <section className="support-product" aria-label="Diagnóstico local">{!embedded&&<h2>Diagnóstico</h2>}<p>Información para soporte consultada en este equipo. No se envía telemetría ni se suben archivos.</p><Button onClick={()=>{setCopy('idle');read.refresh();}}>Actualizar diagnóstico</Button><Button disabled={!read.value||read.loading} onClick={()=>void copySummary()}>Copiar resumen para soporte</Button>{copy==='done'&&<p role="status">Resumen copiado localmente. Compártelo sólo si decides hacerlo.</p>}{copy==='error'&&<ErrorState>No se pudo copiar al portapapeles. Puedes seleccionar el resumen seguro.</ErrorState>}
 {read.loading&&<LoadingState/>}{read.error&&<ErrorState retry={read.refresh}>No se pudo consultar el diagnóstico.</ErrorState>}
 {read.value&&<><h3>Sistema</h3><p>{read.value.api===true?'API local responde':read.value.api===false?'Respuesta API no reconocida':'No se pudo consultar API local'}. Esto no verifica la base de datos.</p>
 <h3>Lectura y motor visual</h3><p>OCR: {read.value.ocr?`${read.value.ocr.available} disponibles de ${read.value.ocr.total}`:'No disponible al consultar'}</p><p>Runtime visual: {read.value.vision?read.value.vision.runtime?'Disponible al consultar':'No disponible al consultar':'Consulta no disponible'} · Modelo: {read.value.vision?read.value.vision.model?'Disponible al consultar':'No disponible al consultar':'Consulta no disponible'}</p>
 {(!read.value.api||!read.value.ocr||!read.value.vision||read.value.vision&&(!read.value.vision.runtime||!read.value.vision.model)||read.value.ocr?.available===0)&&<Notice tone="warning">Alguna consulta o servicio no está disponible. Las demás secciones conservan su resultado; no se ejecutó análisis.</Notice>}
 <h3>Discovery</h3><p>{read.value.sources?`${read.value.sources.enabled} fuentes habilitadas de ${read.value.sources.total}; ${read.value.sources.restricted} restringidas`:'No se pudieron consultar las fuentes locales'}</p><a href="#/configuracion">Revisar configuración de fuentes</a>
 <details><summary>Ver detalle técnico</summary><h4>Resultados de las consultas</h4><pre>{JSON.stringify(read.value,null,2)}</pre><h4>Resumen seguro para soporte</h4><pre>{diagnosticSummary(read.value)}</pre><p>Se excluyeron nombres de documentos/empresas/licitaciones, contenido, valores comerciales, paths, URLs de proveedores, tokens y mensajes libres del servidor.</p></details></>}
 <details><summary>Datos administrativos no expuestos por la API</summary><p>No hay contrato de lectura de versión de aplicación/backend, schema Alembic, ruta de storage, espacio libre o salud completa de DB. Consulta el procedimiento local del administrador; no se infieren desde /health.</p></details>
 <h3>Herramientas avanzadas del expediente</h3><p>Abre el workspace técnico existente sólo cuando necesites controles de documento, procesamiento y auditoría. Las acciones de análisis siguen siendo explícitas.</p><Button onClick={onOpenTools}>{toolsOpened?"Ocultar herramientas del expediente":"Abrir herramientas del expediente"}</Button>
 </section>;
}
