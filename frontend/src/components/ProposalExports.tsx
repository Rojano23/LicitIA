import {useEffect,useRef,useState} from "react";
import axios from "axios";
import {exportsApi,type ExportRequest,type ExportPage,type ArtifactType} from "../api/proposalExports";
import {versionsApi,type ProposalVersion} from "../api/proposalVersions";

type Props={apiUrl:string;tenderId:string;version:ProposalVersion;compositionRevision:number|null;disabled:boolean};
export function ProposalExports({apiUrl,tenderId,version,compositionRevision,disabled}:Props){
 const [page,setPage]=useState<ExportPage|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null);
 const [allowDraft,setAllowDraft]=useState(false),[formats,setFormats]=useState<Exclude<ArtifactType,"ZIP">[]>(["DOCX","XLSX","PDF"]);
 const [source,setSource]=useState("Freshness actual no consultada; los inputs permanecen fijados"),[checks,setChecks]=useState<Record<string,string>>({});
 const pending=useRef<ExportRequest|null>(null),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function run(action:()=>Promise<void>){setBusy(true);setError(null);try{await action();}catch(reason){if(mounted.current){
  const detail=axios.isAxiosError<{detail?:unknown}>(reason)?reason.response?.data?.detail:undefined;
  setError(typeof detail==="string"?detail:"No se pudo completar el export. Revisa estado, composición, referencias y storage local.");
 }}finally{if(mounted.current)setBusy(false);}}
 async function list(before?:string){const result=await exportsApi.list(apiUrl,tenderId,version.id,before);if(mounted.current)setPage(result);}
 async function generate(kinds:Exclude<ArtifactType,"ZIP">[],packageZip:boolean){
  if(compositionRevision===null)return;
  await run(async()=>{
   try{const value=await versionsApi.source(apiUrl,tenderId,version.id);if(mounted.current)setSource(value.state==="SOURCE_SNAPSHOT_STALE"?"Snapshot STALE: se exportará la propuesta histórica, sin cambiar sus inputs":"Snapshot CURRENT al comprobar; los inputs de export siguen fijados");}
   catch{if(mounted.current)setSource("Freshness no disponible. El export conservará exclusivamente los inputs fijados de esta versión.");}
   const payload=pending.current??{request_id:crypto.randomUUID(),formats:kinds,include_package:packageZip,allow_draft:allowDraft,expected_composition_revision:compositionRevision,expected_edit_revision:version.edit_revision,actor_label:null};
   pending.current=payload;
   await exportsApi.create(apiUrl,tenderId,version.id,payload);pending.current=null;await list();
  });
 }
 const blocked=disabled||busy||compositionRevision===null||(version.state==="DRAFT"&&!allowDraft);
 return <section aria-label="Exportaciones de propuesta"><h5>Exportaciones locales</h5>
 <p>Se exporta la composición guardada. Respuestas, aclaraciones y notas de propuesta incluidas pasan al documento. Se omiten costos, margen, markup y notas económicas internas.</p>
 <p>El XLSX de propuesta es editable fuera del sistema y no se importa como precios comerciales. La edición comercial autoritativa permanece en la matriz comercial.</p>
 <p>{source}</p>
 {compositionRevision===null&&<p>Consulta y guarda la composición antes de exportar.</p>}
 {version.state==="DRAFT"&&<label><input type="checkbox" disabled={disabled||busy||pending.current!==null} checked={allowDraft} onChange={e=>setAllowDraft(e.target.checked)}/>Autorizo exportar DRAFT; llevará identificación visible de borrador</label>}
 <fieldset disabled={blocked||pending.current!==null}><legend>Contenido del paquete</legend>{(["DOCX","XLSX","PDF"] as const).map(kind=><label key={kind}><input type="checkbox" checked={formats.includes(kind)} onChange={e=>setFormats(e.target.checked?[...formats,kind]:formats.filter(f=>f!==kind))}/>{kind}</label>)}</fieldset>
 {(["DOCX","XLSX","PDF"] as const).map(kind=><button key={kind} disabled={blocked||pending.current!==null} onClick={()=>void generate([kind],false)}>Generar {kind}</button>)}
 <button disabled={blocked||pending.current!==null||!formats.length} onClick={()=>void generate(formats,true)}>Generar paquete ZIP</button>
 {pending.current&&<><button disabled={disabled||busy} onClick={()=>void generate(pending.current!.formats,pending.current!.include_package)}>Reintentar solicitud de exportación</button>
 <button disabled={disabled||busy} onClick={()=>{pending.current=null;setError(null);}}>Iniciar nueva solicitud independiente</button></>}
 <button disabled={disabled||busy} onClick={()=>void run(()=>list())}>Consultar artefactos generados</button>
 {page?.items.map(receipt=><article key={receipt.request_id}><p>{receipt.created_at} · {receipt.proposal_state} · {receipt.verification_status}</p>
 <p>Identidad semántica: {receipt.semantic_sha256}</p>
 <button disabled={disabled||busy} onClick={()=>void run(async()=>{try{const value=await exportsApi.verify(apiUrl,tenderId,version.id,receipt.request_id);if(mounted.current)setChecks(current=>({...current,[receipt.request_id]:value.verification_status}));}catch(reason){if(mounted.current)setChecks(current=>({...current,[receipt.request_id]:"FAILED"}));throw reason;}})}>Verificar integridad {receipt.request_id}</button>
 {checks[receipt.request_id]&&<p>Verificación actual: {checks[receipt.request_id]}. Verificar integridad no equivale a firma digital.</p>}
 {receipt.artifacts.map(artifact=><p key={artifact.type}><a href={exportsApi.file(apiUrl,tenderId,version.id,receipt.request_id,artifact.type)}>Descargar {artifact.name}</a> · SHA-256 {artifact.sha256} · {artifact.size} bytes</p>)}</article>)}
 {page?.next_before_id&&<button disabled={disabled||busy} onClick={()=>void run(()=>list(page.next_before_id??undefined))}>Más artefactos anteriores</button>}
 {error&&<p role="alert">{error} La versión y los artefactos anteriores se conservan.</p>}
 </section>;
}
