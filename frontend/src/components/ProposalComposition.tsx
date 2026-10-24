import {commercialLabel as label} from "../ui/commercialPresentation";
import {useEffect,useRef,useState} from "react";
import {compositionApi,type Composition,type CompositionRow,type HumanResponse,type ResponseStatus,type ManualItem} from "../api/proposalComposition";

type Props={product?:boolean;apiUrl:string;tenderId:string;versionId:string;editable:boolean;disabled:boolean;onState:(value:Composition|null)=>void};
export function ProposalComposition({apiUrl,tenderId,versionId,editable,disabled,onState,product=false}:Props){
 const [value,setValue]=useState<Composition|null>(null),[section,setSection]=useState("TECHNICAL_SCOPE"),[offset,setOffset]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(false);
 const [selected,setSelected]=useState<string[]>([]),[bulkStatus,setBulkStatus]=useState<ResponseStatus>("PENDING");
 const [text,setText]=useState(""),[kind,setKind]=useState<ManualItem["kind"]>("CLARIFICATION"),[external,setExternal]=useState("");
 const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 async function load(nextSection=section,nextOffset=offset){const result=await compositionApi.get(apiUrl,tenderId,versionId,nextSection,nextOffset);if(mounted.current){setValue(result);onState(result);setSelected([]);}}
 async function run(action:()=>Promise<void>){setBusy(true);setError(false);try{await action();}catch{if(mounted.current){setError(true);onState(null);}}finally{if(mounted.current)setBusy(false);}}
 async function mutate(action:()=>Promise<Composition>){await run(async()=>{await action();await load();});}
 const blocked=disabled||busy||!editable;
 return <section aria-label="Composición de propuesta"><h5>Composición estructurada</h5>
 <p>Los datos del expediente son de sólo lectura. Declarar cumplimiento es una decisión del participante, no una certificación. Las respuestas se guardan en esta versión.</p>
 <button disabled={disabled||busy} onClick={()=>void run(()=>load())}>Consultar composición</button>
 <button disabled={blocked} onClick={()=>void mutate(()=>compositionApi.initialize(apiUrl,tenderId,versionId))}>Preparar o actualizar contenido</button>
 {value&&!value.initialized&&<p>El contenido aún no está preparado. Antes de congelar la versión, prepara su contenido y revisa las respuestas.</p>}
 {value?.initialized&&<>
 <p>Completitud de propuesta: {product?label(value.summary?.status):value.summary?.status} · Revisión {value.revision}</p>
 <details><summary>Identificación técnica de la captura</summary><pre aria-label="Identificación de propuesta">{JSON.stringify(value.identification,null,2)}</pre></details>
 {value.summary?.sections.map(s=><p key={s.section}>{product?label(s.section):s.section}: {product?label(s.status):s.status} · Pendientes {s.pending_count} · Revisar {s.review_count} · Filas {s.row_count}</p>)}
 {value.summary&&[...value.summary.hard_incomplete,...value.summary.blocking_review,...value.summary.acknowledgeable_review].map((r,i)=><p key={`${r.key}:${r.code}:${i}`}>{product?label(r.code):`${r.key} · ${r.code}`}</p>)}
 <label>Sección de propuesta <select disabled={disabled||busy} value={section} onChange={e=>{const next=e.target.value;setSection(next);setOffset(0);void run(()=>load(next,0));}}>{value.sections?.map(s=><option key={s.id} value={s.type}>{product?label(s.type):s.type}</option>)}</select></label>
 <details><summary>Orden y disposición de secciones</summary><fieldset disabled={blocked} onChange={()=>onState(null)}><legend>Disposición de secciones</legend>{value.sections?.map(s=><div key={s.id}>
 <label><input type="checkbox" checked={s.included} onChange={e=>setValue({...value,sections:value.sections?.map(x=>x.id===s.id?{...x,included:e.target.checked}:x)})}/>{product?label(s.type):s.type} incluida</label>
 <label>Orden {product?label(s.type):s.type}<input type="number" min={0} max={999} value={s.order} onChange={e=>setValue({...value,sections:value.sections?.map(x=>x.id===s.id?{...x,order:Number(e.target.value)}:x)})}/></label>
 <label>Motivo/nota {product?label(s.type):s.type}<input maxLength={4000} value={s.note??""} onChange={e=>setValue({...value,sections:value.sections?.map(x=>x.id===s.id?{...x,note:e.target.value}:x)})}/></label></div>)}
 <button onClick={()=>void mutate(()=>compositionApi.settings(apiUrl,tenderId,versionId,value.revision!,{sections:value.sections}))}>Guardar disposición</button></fieldset></details>
 <p>Monedas separadas: {value.currency_groups?.map(g=>`${g.currency}: ${g.line_count} filas`).join(" · ")}</p>
 {section==="REQUIREMENTS"&&<fieldset disabled={blocked}><legend>Acción explícita sobre seleccionados ({selected.length}, máximo 50)</legend>
 <label>Declaración seleccionada<select value={bulkStatus} onChange={e=>setBulkStatus(e.target.value as ResponseStatus)}><option value="PENDING">{product?label("PENDING"):"PENDING"}</option><option value="COMPLY">{product?label("COMPLY"):"COMPLY"}</option></select></label>
 <button disabled={!selected.length||selected.length>50} onClick={()=>void mutate(()=>compositionApi.responses(apiUrl,tenderId,versionId,value.revision!,value.rows!.filter(r=>selected.includes(r.key)).map(r=>({key:r.key,response:{...r.response,status:bulkStatus}}))))}>Aplicar declaración a seleccionados</button></fieldset>}
 {value.rows?.map(row=><div key={row.key}>
 {section==="REQUIREMENTS"&&<label><input disabled={blocked} type="checkbox" checked={selected.includes(row.key)} onChange={e=>setSelected(e.target.checked?[...selected,row.key]:selected.filter(k=>k!==row.key))}/>Seleccionar {row.key}</label>}
 <RowEditor key={`${row.key}:${value.revision}`} row={row} product={product} disabled={blocked} onDirty={()=>onState(null)} save={(response,ack)=>mutate(()=>compositionApi.responses(apiUrl,tenderId,versionId,value.revision!,[{key:row.key,response,acknowledge_source_change:ack}]))}/></div>)}
 <p>Filas en esta sección: {value.total??0}</p>
 <button disabled={disabled||busy||offset===0} onClick={()=>{setOffset(Math.max(0,offset-25));void run(()=>load(section,Math.max(0,offset-25)));}}>Página anterior de composición</button>
 <button disabled={disabled||busy||value.next_offset==null} onClick={()=>{setOffset(value.next_offset!);void run(()=>load(section,value.next_offset!));}}>Más filas de composición</button>
 <fieldset disabled={blocked} onChange={()=>onState(null)}><legend>Aclaraciones, notas y referencias de anexos</legend>
 <label>Tipo de contenido humano<select value={kind} onChange={e=>setKind(e.target.value as ManualItem["kind"])}>{["CLARIFICATION","EXCLUSION","ASSUMPTION","DEVIATION","NOTE","ANNEX_REFERENCE"].map(k=><option key={k} value={k}>{product?label(k):k}</option>)}</select></label>
 <label>Contenido humano<textarea maxLength={8000} value={text} onChange={e=>setText(e.target.value)}/></label>
 <label>Referencia externa de anexo<input maxLength={1000} value={external} onChange={e=>setExternal(e.target.value)}/></label>
 <button disabled={!text.trim()||(value.items?.length??0)>=200} onClick={()=>void mutate(()=>compositionApi.settings(apiUrl,tenderId,versionId,value.revision!,{items:[...(value.items??[]),{id:crypto.randomUUID(),kind,text,document_id:null,external_reference:external}]}))}>Añadir contenido humano</button></fieldset>
 <fieldset disabled={blocked} onChange={()=>onState(null)}><legend>Editar contenido humano existente</legend>
 {value.items?.map(item=><div key={item.id}><p>{product?label(item.kind):item.kind} · {item.id}</p>
 <label>Texto {item.id}<textarea maxLength={8000} value={item.text} onChange={e=>setValue({...value,items:value.items?.map(i=>i.id===item.id?{...i,text:e.target.value}:i)})}/></label>
 <label>Documento de anexo {item.id}<input maxLength={36} value={item.document_id??""} onChange={e=>setValue({...value,items:value.items?.map(i=>i.id===item.id?{...i,document_id:e.target.value||null}:i)})}/></label>
 <label>Referencia {item.id}<input maxLength={1000} value={item.external_reference} onChange={e=>setValue({...value,items:value.items?.map(i=>i.id===item.id?{...i,external_reference:e.target.value}:i)})}/></label></div>)}
 <button disabled={!value.items?.length} onClick={()=>void mutate(()=>compositionApi.settings(apiUrl,tenderId,versionId,value.revision!,{items:value.items}))}>Guardar contenido humano existente</button></fieldset>
 {!!value.removed_keys?.length&&<p>Fuentes retiradas (sin copiar respuesta): {value.removed_keys.join(", ")}</p>}
 </>}
 {error&&<p role="alert">No se guardó/consultó la composición. Revisa revisión vigente, fuente y referencias; vuelve a consultar antes de continuar.</p>}
 </section>;
}
function RowEditor({row,disabled,save,onDirty,product=false}:{product?:boolean;row:CompositionRow;disabled:boolean;onDirty:()=>void;save:(response:HumanResponse,ack:boolean)=>Promise<void>}){
 const [response,setResponse]=useState(row.response),[ack,setAck]=useState(false);
 const fields:({key:keyof HumanResponse;label:string;max:number})[]=row.section==="ECONOMIC"?[{key:"note",label:"Nota económica",max:4000}]:[
 {key:"text",label:"Respuesta humana",max:8000},{key:"offered_description",label:"Descripción ofrecida",max:8000},{key:"comment",label:"Comentario técnico",max:4000},
 {key:"clarification",label:"Aclaración",max:4000},{key:"note",label:"Nota",max:4000},{key:"external_reference",label:"Referencia externa",max:1000},{key:"reason",label:"Motivo de excepción/exclusión",max:4000}];
 const statuses=row.section==="REQUESTED_EVIDENCE"?["PENDING","PROVIDED","NOT_APPLICABLE","REVIEW_REQUIRED"]:["PENDING","COMPLY","PARTIAL","NOT_APPLICABLE","EXCEPTION","REVIEW_REQUIRED"];
 return <article aria-label={row.key}><h6>{product?label(row.section):row.key} · {product?label(row.source_match):row.source_match}</h6><details><summary>Datos técnicos de la fuente de sólo lectura</summary><pre>{JSON.stringify(row.canonical,null,2)}</pre></details>
 <details open={!product}><summary>Editar respuesta humana de esta fila</summary><fieldset disabled={disabled} onChange={onDirty}><legend>Contenido humano separado</legend>
 {row.section!=="ECONOMIC"&&<><label>Declaración {product?"de esta fila":row.key}<select value={response.status} onChange={e=>setResponse({...response,status:e.target.value as ResponseStatus})}>{statuses.map(s=><option key={s} value={s}>{product?label(s):s}</option>)}</select></label>
 <label><input type="checkbox" checked={response.included} onChange={e=>setResponse({...response,included:e.target.checked})}/>Incluir fila {product?"en la propuesta":row.key}</label>
 <label>Documento congelado ID {row.key}<input maxLength={36} value={response.document_id??""} onChange={e=>setResponse({...response,document_id:e.target.value||null})}/></label></>}
 {fields.map(field=><label key={field.key}>{field.label} {product?"":row.key}<textarea maxLength={field.max} value={String(response[field.key]??"")} onChange={e=>setResponse({...response,[field.key]:e.target.value})}/></label>)}
 {row.review_required&&<label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>Revisé el cambio de fuente {product?"de esta fila":row.key}</label>}
 <button onClick={()=>void save(response,ack)}>Guardar respuesta {product?"de esta fila":row.key}</button></fieldset></details></article>;
}
