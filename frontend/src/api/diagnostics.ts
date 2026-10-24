import axios from 'axios';
import {discoveryApi} from './discovery';
export type DiagnosticRead={api:boolean|null;ocr:{available:number;total:number}|null;vision:{runtime:boolean;model:boolean}|null;sources:{total:number;enabled:number;restricted:number}|null};
/** Never carry free-form payload, reasons, URLs, credentials or document data into diagnostics/copy. */
export async function readDiagnostics(base:string):Promise<DiagnosticRead>{
 const [health,ocr,vision,sources]=await Promise.allSettled([
  axios.get<{status:unknown}>(`${base}/health`),
  axios.get<{status:string}[]>(`${base}/ocr/providers`),
  axios.get<{runtime_available:unknown;model_available:unknown}>(`${base}/vision/providers`),
  discoveryApi.sources(base),
 ]);
 return {
  api:health.status==='fulfilled'?health.value.data.status==='ok':null,
  ocr:ocr.status==='fulfilled'&&Array.isArray(ocr.value.data)?{available:ocr.value.data.filter(p=>p.status==='AVAILABLE').length,total:ocr.value.data.length}:null,
  vision:vision.status==='fulfilled'&&typeof vision.value.data.runtime_available==='boolean'&&typeof vision.value.data.model_available==='boolean'?{runtime:vision.value.data.runtime_available,model:vision.value.data.model_available}:null,
  sources:sources.status==='fulfilled'&&Array.isArray(sources.value)?{total:sources.value.length,enabled:sources.value.filter(s=>s.enabled&&s.id!=='COMPRAS_MX').length,restricted:sources.value.filter(s=>s.id==='COMPRAS_MX').length}:null,
 };
}
export function diagnosticSummary(data:DiagnosticRead){
 const status=(value:boolean|null)=>value===null?'No disponible':value?'Disponible al consultar':'No disponible al consultar';
 return ['RX23 TuScope — resumen local de soporte',`API: ${status(data.api)}`,`OCR: ${data.ocr?`${data.ocr.available} disponibles de ${data.ocr.total}`:'No disponible'}`,`Motor visual: ${status(data.vision?.runtime??null)}`,`Modelo visual: ${status(data.vision?.model??null)}`,`Fuentes: ${data.sources?`${data.sources.enabled} habilitadas de ${data.sources.total}; ${data.sources.restricted} restringidas`:'No disponible'}`,'Esquema/versión backend: no expuestos por esta API','Sin datos de expediente en este resumen'].join('\n');
}
